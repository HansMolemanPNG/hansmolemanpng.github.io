---
title: XXE Injection Deep Dive
type: writeup
tags: XXE, XML, Web
excerpt: Attack surface, blind XXE, OOB exfil and mitigations.
kb_ref: web-security
---

# XXE Injection Deep Dive

## Overview

XML External Entity (XXE) is a vulnerability that occurs when XML parsers process external entities without proper restrictions.

## Impact

- Local file disclosure
- SSRF
- Denial of Service

## Example payload

```xml
<!DOCTYPE foo [
<!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<foo>&xxe;</foo>
```
