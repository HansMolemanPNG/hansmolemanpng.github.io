---
title: "JWT Algorithm Confusion Attacks"
type: research
tags: JWT, Auth, Cryptography, Web
excerpt: How RS256 to HS256 algorithm confusion works, why it's still found in the wild, and how to test for it.
kb_ref: cryptography
---

# JWT Algorithm Confusion Attacks

Algorithm confusion (also called key confusion) is one of the most dangerous JWT vulnerabilities. When exploitable, it typically gives you the ability to forge arbitrary tokens and impersonate any user, including admins. Despite being well-documented since 2015, it still shows up regularly.

---

## Background: RS256 vs HS256

JWTs can be signed with different algorithms:

- **HS256** — HMAC-SHA256, symmetric. The same secret key is used to sign and verify.
- **RS256** — RSA-SHA256, asymmetric. A private key signs; the public key verifies.

The algorithm is specified in the token header:

```json
{
  "alg": "RS256",
  "typ": "JWT"
}
```

---

## The Vulnerability

The attack works when:

1. The server signs tokens with **RS256** (private key)
2. The server's JWT library accepts both RS256 and HS256
3. The library uses the public key as-is when HS256 is specified

If an attacker changes `alg` from `RS256` to `HS256`, some libraries will verify the signature using the **public key as the HMAC secret**. Since the public key is, well, public — the attacker can sign arbitrary tokens.

```
Server expects RS256:   verify(token, publicKey)
Attacker sends HS256:   verify(token, publicKey)  ← same call, different interpretation
```

The root cause is usually a verification function like:

```python
# Vulnerable
jwt.decode(token, public_key)  # trusts the header's alg field
```

```python
# Safe
jwt.decode(token, public_key, algorithms=["RS256"])  # explicitly restrict algorithms
```

---

## Finding the Public Key

To forge a token you need the server's RSA public key. Common sources:

1. **JWKS endpoint** — `/.well-known/jwks.json`, `/api/auth/jwks`
2. **Embedded in responses** — some apps return it in auth flows
3. **Derivation from two tokens** — using `rsa_sign2n` or similar tools, you can derive the public key from two RS256-signed tokens

```bash
# Derive public key from two tokens
git clone https://github.com/silentsignal/rsa_sign2n
python3 rsa_sign2n/standalone/jwt_forgery.py token1 token2
```

---

## Exploitation

Once you have the public key, forge a token with an elevated role:

```python
import jwt

public_key = open("public.pem").read()

payload = {
    "sub": "1337",
    "username": "admin",
    "role": "administrator",
    "iat": 1700000000,
    "exp": 9999999999
}

forged = jwt.encode(payload, public_key, algorithm="HS256")
print(forged)
```

Use the forged token in the `Authorization: Bearer` header and observe the response.

---

## Testing Checklist

When assessing a JWT implementation:

- [ ] Check the `alg` header — is it RS256/ES256 or symmetric?
- [ ] Try changing `alg` to `HS256` and re-signing with the public key
- [ ] Try `alg: none` (no signature required)
- [ ] Look for a JWKS endpoint and retrieve the public key
- [ ] Test if the `kid` header allows path traversal or SQL injection
- [ ] Check token expiry is enforced (`exp` claim)
- [ ] Verify the `aud` (audience) claim is validated

---

## Mitigation

**For developers:**

- Always explicitly specify allowed algorithms when verifying:
  ```python
  jwt.decode(token, key, algorithms=["RS256"])
  ```
- Use a well-maintained JWT library and keep it updated
- Reject tokens with `alg: none`
- Pin the expected algorithm in config, not at runtime

**Detection:**
- Log JWT verification failures including the algorithm claimed
- Alert on `alg: none` or unexpected algorithm changes from the same client

---

## Tools

| Tool | Use |
|---|---|
| [jwt.io](https://jwt.io) | Decode and inspect JWTs |
| [jwt_tool](https://github.com/ticarpi/jwt_tool) | Automated JWT attack testing |
| [rsa_sign2n](https://github.com/silentsignal/rsa_sign2n) | Derive public key from token pairs |
| Burp Suite JWT Editor | In-proxy token manipulation |

---

## References

- [PortSwigger Web Security Academy — JWT attacks](https://portswigger.net/web-security/jwt)
- [RFC 7518 — JSON Web Algorithms](https://www.rfc-editor.org/rfc/rfc7518)
- [Auth0 — Critical vulnerabilities in JWT libraries (2015)](https://auth0.com/blog/critical-vulnerabilities-in-json-web-token-libraries/)
