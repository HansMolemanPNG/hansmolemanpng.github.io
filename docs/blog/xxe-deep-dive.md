---
title: XXE Injection Deep Dive
date: 2024-03-01
tags: XXE, XML, Web
excerpt: Attack surface, blind XXE, OOB exfil and mitigations.
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
