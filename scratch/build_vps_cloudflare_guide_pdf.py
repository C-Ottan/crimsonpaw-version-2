import os
import subprocess
from datetime import datetime

ROOT_DIR = r"c:\Users\IT-ADMIN\Desktop\FLOW\ICEBADGER\icebadger"
HTML_PATH = os.path.join(ROOT_DIR, "VPS_Cloudflare_Setup_Guide.html")
PDF_PATH = os.path.join(ROOT_DIR, "VPS_Cloudflare_Setup_Guide.pdf")
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Comprehensive Guide: VPS Staging, Cloudflare Architecture &amp; Database Resilience</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        @page {{
            size: A4;
            margin: 10mm 12mm 10mm 12mm;
            @bottom-right {{
                content: counter(page);
            }}
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: #1e293b;
            background: #ffffff;
            font-size: 8.8pt;
            line-height: 1.45;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}

        /* Document Header */
        .doc-header {{
            border-bottom: 2px solid #e11d48;
            padding-bottom: 8px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
        }}
        .brand-pill {{
            display: inline-block;
            background: #1e1115;
            color: #f43f5e;
            font-size: 7.2pt;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 4px;
            border: 1px solid #4c1d24;
        }}
        .doc-title {{
            font-size: 16pt;
            font-weight: 800;
            color: #0f172a;
            line-height: 1.15;
            letter-spacing: -0.02em;
        }}
        .doc-subtitle {{
            font-size: 8.8pt;
            color: #64748b;
            margin-top: 2px;
        }}
        .doc-meta {{
            text-align: right;
            font-size: 7.5pt;
            color: #64748b;
            line-height: 1.35;
        }}
        .doc-meta b {{
            color: #0f172a;
        }}

        /* Section Headings */
        .part-header {{
            background: #0f172a;
            color: #ffffff;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 9.8pt;
            font-weight: 700;
            margin: 11px 0 6px 0;
            display: flex;
            align-items: center;
            gap: 8px;
            page-break-after: avoid;
        }}
        .part-tag {{
            background: #e11d48;
            color: #ffffff;
            font-size: 7pt;
            font-weight: 800;
            padding: 2px 6px;
            border-radius: 3px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        h3 {{
            font-size: 9.2pt;
            font-weight: 700;
            color: #0f172a;
            margin: 8px 0 4px 0;
            page-break-after: avoid;
        }}

        p {{
            margin-bottom: 5px;
            color: #334155;
        }}

        /* Compact Architecture Flow Diagram */
        .diagram-card {{
            background: #0b1120;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 8px 12px;
            margin: 6px 0 10px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            page-break-inside: avoid;
        }}
        .diagram-title {{
            font-size: 7.5pt;
            font-weight: 700;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 6px;
            text-align: center;
        }}
        .flow-container {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 6px;
        }}
        .flow-node {{
            flex: 1;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 5px;
            padding: 5px 8px;
            text-align: center;
            color: #ffffff;
            min-height: 48px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }}
        .flow-node.highlight {{
            background: #2a1218;
            border-color: #e11d48;
        }}
        .flow-node-title {{
            font-size: 8pt;
            font-weight: 700;
            margin-bottom: 2px;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .flow-node-desc {{
            font-size: 6.8pt;
            color: #94a3b8;
            line-height: 1.2;
        }}
        .flow-arrow {{
            color: #f43f5e;
            font-size: 11pt;
            font-weight: 800;
            flex-shrink: 0;
            text-align: center;
            line-height: 1;
        }}
        .flow-arrow-label {{
            font-size: 5.8pt;
            color: #cbd5e1;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.04em;
            margin-top: 2px;
            display: block;
        }}

        /* Code Blocks */
        .terminal-block {{
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 5px;
            margin: 5px 0 8px 0;
            overflow: hidden;
            font-family: 'JetBrains Mono', Consolas, monospace;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            page-break-inside: avoid;
        }}
        .terminal-header {{
            background: #1e293b;
            padding: 3px 8px;
            font-size: 6.8pt;
            font-weight: 600;
            color: #94a3b8;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
        }}
        .terminal-dots {{
            display: flex;
            gap: 4px;
        }}
        .terminal-dot {{
            width: 6px;
            height: 6px;
            border-radius: 50%;
            display: inline-block;
        }}
        .dot-red {{ background: #ef4444; }}
        .dot-yellow {{ background: #f59e0b; }}
        .dot-green {{ background: #10b981; }}
        
        pre.code-content {{
            padding: 6px 10px;
            font-size: 7.6pt;
            color: #f8fafc;
            line-height: 1.4;
            overflow-x: hidden;
            white-space: pre-wrap;
            word-break: break-all;
        }}
        .cmd-prompt {{
            color: #38bdf8;
            font-weight: 700;
            user-select: none;
        }}
        .cmd-arg {{
            color: #fbbf24;
        }}
        .cmd-comment {{
            color: #64748b;
            font-style: italic;
        }}

        /* Steps and Lists */
        .step-list {{
            list-style: none;
            margin: 5px 0 8px 0;
            counter-reset: step-counter;
        }}
        .step-item {{
            counter-increment: step-counter;
            position: relative;
            padding-left: 24px;
            margin-bottom: 5px;
        }}
        .step-item::before {{
            content: counter(step-counter);
            position: absolute;
            left: 0;
            top: 1px;
            width: 17px;
            height: 17px;
            background: #e11d48;
            color: #ffffff;
            border-radius: 50%;
            font-size: 7pt;
            font-weight: 800;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            line-height: 17px;
        }}
        .step-item strong {{
            color: #0f172a;
        }}

        /* Callout Boxes */
        .callout {{
            border-left: 3px solid;
            border-radius: 0 5px 5px 0;
            padding: 6px 10px;
            margin: 6px 0 8px 0;
            font-size: 8pt;
            page-break-inside: avoid;
        }}
        .callout-tip {{
            background: #f0fdf4;
            border-color: #22c55e;
            color: #166534;
        }}
        .callout-info {{
            background: #f0f9ff;
            border-color: #0284c7;
            color: #075985;
        }}
        .callout-warn {{
            background: #fffbeb;
            border-color: #f59e0b;
            color: #92400e;
        }}
        .callout-title {{
            font-weight: 700;
            margin-bottom: 2px;
            display: flex;
            align-items: center;
            gap: 5px;
        }}

        /* Tables */
        table.guide-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 5px 0 8px 0;
            font-size: 7.8pt;
        }}
        table.guide-table tr {{
            page-break-inside: avoid;
        }}
        table.guide-table th {{
            background: #0f172a;
            color: #ffffff;
            font-weight: 700;
            text-align: left;
            padding: 5px 7px;
            border: 1px solid #1e293b;
        }}
        table.guide-table td {{
            padding: 4px 7px;
            border: 1px solid #e2e8f0;
            vertical-align: top;
        }}
        table.guide-table tr:nth-child(even) {{
            background: #f8fafc;
        }}

        .badge-proxy {{
            background: #ffedd5;
            color: #c2410c;
            border: 1px solid #fed7aa;
            padding: 1px 5px;
            border-radius: 3px;
            font-weight: 700;
            font-size: 6.8pt;
            display: inline-flex;
            align-items: center;
            gap: 3px;
        }}

        /* Clean Footer */
        .doc-footer {{
            margin-top: 14px;
            padding-top: 6px;
            border-top: 1px solid #cbd5e1;
            display: flex;
            justify-content: space-between;
            font-size: 6.8pt;
            color: #94a3b8;
            page-break-inside: avoid;
        }}
    </style>
</head>
<body>

    <!-- Document Header -->
    <div class="doc-header">
        <div>
            <div class="brand-pill">Infrastructure Engineering Manual</div>
            <div class="doc-title">VPS Connectivity, Cloudflare DNS &amp; Production Deployment</div>
            <div class="doc-subtitle">Standard Operating Procedure for Server Staging, Code Migration &amp; Database Resilience</div>
        </div>
        <div class="doc-meta">
            <div>Document: <b>SOP-INFRA-CF-02</b></div>
            <div>Generated: <b>{datetime.now().strftime('%Y-%m-%d %H:%M')}</b></div>
            <div>Target OS: <b>Ubuntu / Debian Linux</b></div>
            <div>Classification: <b>RESTRICTED // RED TEAM OPS</b></div>
        </div>
    </div>

    <!-- Architecture Overview Diagram -->
    <div class="diagram-card">
        <div class="diagram-title">Target Operational Architecture Flow</div>
        <div class="flow-container">
            <div class="flow-node">
                <div class="flow-node-title"><span>🌐</span> Domain Registrar</div>
                <div class="flow-node-desc">Namecheap / GoDaddy<br>Authoritative NS delegation</div>
            </div>
            <div class="flow-arrow">
                ➜
                <span class="flow-arrow-label">Nameservers</span>
            </div>
            <div class="flow-node highlight">
                <div class="flow-node-title"><span>🛡️</span> Cloudflare Edge</div>
                <div class="flow-node-desc">Anycast DNS, DDoS Proxy<br>Edge SSL/TLS Termination</div>
            </div>
            <div class="flow-arrow">
                ➜
                <span class="flow-arrow-label">A Record</span>
            </div>
            <div class="flow-node">
                <div class="flow-node-title"><span>⚡</span> VPS Server</div>
                <div class="flow-node-desc">Ubuntu / Debian Linux<br>Systemd + SQLite Engine</div>
            </div>
            <div class="flow-arrow">
                ➜
                <span class="flow-arrow-label">SSH :22</span>
            </div>
            <div class="flow-node">
                <div class="flow-node-title"><span>💻</span> Admin PC</div>
                <div class="flow-node-desc">Windows Terminal<br>Secure Operator Shell</div>
            </div>
        </div>
    </div>

    <!-- PART A -->
    <div class="part-header">
        <span class="part-tag">Part A</span>
        <span>How to Connect to Your VPS from Windows</span>
    </div>

    <p>Windows 10/11 features native OpenSSH client capabilities directly within PowerShell and Windows Terminal, eliminating the need for third-party SSH clients.</p>

    <div class="step-list">
        <div class="step-item">
            <strong>Launch Terminal:</strong> Open <strong>PowerShell</strong> or <strong>Windows Terminal</strong> (Win + X ➜ Terminal).
        </div>
        <div class="step-item">
            <strong>Execute SSH Connection:</strong> Connect to your VPS IPv4 address using administrative credentials (typically <code>root</code>):
        </div>
    </div>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>PowerShell Console</span>
            <div class="terminal-dots">
                <span class="terminal-dot dot-red"></span>
                <span class="terminal-dot dot-yellow"></span>
                <span class="terminal-dot dot-green"></span>
            </div>
        </div>
        <pre class="code-content"><span class="cmd-prompt">PS C:\\Users\\Admin&gt;</span> ssh root@<span class="cmd-arg">YOUR_VPS_IP</span>
<span class="cmd-comment"># Example: ssh root@142.250.190.46</span></pre>
    </div>

    <div class="step-list" style="counter-reset: step-counter 2;">
        <div class="step-item">
            <strong>Accept Host Key Verification:</strong> On first connection, OpenSSH requests confirmation to store the remote server's fingerprint in <code>~/.ssh/known_hosts</code>. Type <code>yes</code> and hit <strong>Enter</strong>.
        </div>
        <div class="step-item">
            <strong>Authenticate:</strong>
            Provide your password (characters will not echo) or pass your private key: <code>ssh -i "C:\\path\\key.pem" root@YOUR_VPS_IP</code>.
        </div>
        <div class="step-item">
            <strong>Initial Server Hygiene:</strong> Immediately refresh packages and install Python 3 venv and firewall tools:
        </div>
    </div>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>Ubuntu / Debian Shell</span>
        </div>
        <pre class="code-content"><span class="cmd-prompt">root@vps:~#</span> apt update &amp;&amp; apt upgrade -y
<span class="cmd-prompt">root@vps:~#</span> apt install -y ufw curl git python3-pip python3-venv sqlite3 nginx</pre>
    </div>

    <!-- PART B -->
    <div class="part-header">
        <span class="part-tag">Part B</span>
        <span>Linking Your Domain to Cloudflare</span>
    </div>

    <p>Cloudflare acts as an authoritative Anycast DNS provider and reverse-proxy, shielding your origin VPS IP while managing SSL certificates and DDoS filtering.</p>

    <div class="step-list">
        <div class="step-item">
            <strong>Add Site:</strong> In <a href="https://dash.cloudflare.com/" style="color:#e11d48; text-decoration:none; font-weight:600;">Cloudflare Dashboard</a>, click <strong>+ Add a Site</strong>, enter your naked domain (e.g. <code>yourdomain.com</code>), and select the <strong>Free Plan</strong>.
        </div>
        <div class="step-item">
            <strong>Update Nameservers at Registrar:</strong> Note the two assigned Cloudflare nameservers (e.g., <code>ada.ns.cloudflare.com</code>, <code>dane.ns.cloudflare.com</code>). Log in to your domain registrar (Namecheap, GoDaddy, Porkbun), switch Nameservers to <strong>Custom DNS</strong>, paste both addresses, and save.
        </div>
    </div>

    <!-- PART C -->
    <div class="part-header">
        <span class="part-tag">Part C</span>
        <span>Configure DNS Records to Point to Your VPS</span>
    </div>

    <p>In Cloudflare, go to <strong>DNS</strong> ➔ <strong>Records</strong>. Add the following records pointing traffic to your VPS:</p>

    <table class="guide-table">
        <thead>
            <tr>
                <th style="width: 12%;">Type</th>
                <th style="width: 25%;">Name</th>
                <th style="width: 25%;">IPv4 Address (Value)</th>
                <th style="width: 23%;">Proxy Status</th>
                <th style="width: 15%;">TTL</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>A</strong></td>
                <td><code>@</code> (Apex / Root)</td>
                <td><code>YOUR_VPS_IP</code></td>
                <td><span class="badge-proxy">☁️ Proxied (Orange)</span></td>
                <td>Auto</td>
            </tr>
            <tr>
                <td><strong>A</strong></td>
                <td><code>*</code> (Wildcard)</td>
                <td><code>YOUR_VPS_IP</code></td>
                <td><span class="badge-proxy">☁️ Proxied (Orange)</span></td>
                <td>Auto</td>
            </tr>
            <tr>
                <td><strong>A</strong></td>
                <td><code>www</code></td>
                <td><code>YOUR_VPS_IP</code></td>
                <td><span class="badge-proxy">☁️ Proxied (Orange)</span></td>
                <td>Auto</td>
            </tr>
        </tbody>
    </table>

    <div class="callout callout-info">
        <div class="callout-title">🔍 Understanding Proxy Status (Orange Cloud vs. Grey Cloud)</div>
        <strong>Proxied (Orange Cloud):</strong> Requests resolve to Cloudflare's Anycast edge IPs. Your real VPS IP remains hidden, mitigating direct scanning.<br>
        <strong>DNS Only (Grey Cloud):</strong> Bypasses Cloudflare proxy; queries return your true VPS IP directly.
    </div>

    <!-- PART D -->
    <div class="part-header">
        <span class="part-tag">Part D</span>
        <span>Configure Cloudflare SSL / TLS Encryption</span>
    </div>

    <div class="step-list">
        <div class="step-item">
            Navigate to <strong>SSL/TLS</strong> ➜ <strong>Overview</strong> in Cloudflare.
        </div>
        <div class="step-item">
            Select <strong>Full</strong> mode (Cloudflare encrypts browser-to-Cloudflare and Cloudflare-to-VPS) or <strong>Flexible</strong> (if VPS listens purely on HTTP port 80).
        </div>
        <div class="step-item">
            Under <strong>SSL/TLS</strong> ➜ <strong>Edge Certificates</strong>, toggle <strong>Always Use HTTPS</strong> to <strong>ON</strong>.
        </div>
    </div>

    <!-- PART E -->
    <div class="part-header">
        <span class="part-tag">Part E</span>
        <span>Moving Your Codebase from Windows to the VPS</span>
    </div>

    <p>To deploy cleanly without transferring bulky virtual environment binaries or temporary files, archive the project on Windows and transfer via native OpenSSH SCP:</p>

    <div class="step-list">
        <div class="step-item">
            <strong>Package the Project on Windows (PowerShell):</strong>
            Compress your workspace into a single archive, excluding <code>venv</code> and <code>__pycache__</code>:
        </div>
    </div>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>PowerShell (Windows)</span>
        </div>
        <pre class="code-content"><span class="cmd-prompt">PS C:\\Users\\Admin&gt;</span> cd c:\\Users\\IT-ADMIN\\Desktop\\FLOW\\ICEBADGER\\icebadger
<span class="cmd-prompt">PS C:\\Users\\...\\icebadger&gt;</span> tar -czvf ..\\icebadger_deploy.tar.gz --exclude="venv" --exclude="__pycache__" --exclude=".git" .</pre>
    </div>

    <div class="step-list" style="counter-reset: step-counter 1;">
        <div class="step-item">
            <strong>Transfer to VPS via SCP:</strong>
            Copy the archive to your remote VPS <code>/opt</code> directory:
        </div>
    </div>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>PowerShell (Windows)</span>
        </div>
        <pre class="code-content"><span class="cmd-prompt">PS C:\\Users\\Admin&gt;</span> scp c:\\Users\\IT-ADMIN\\Desktop\\FLOW\\ICEBADGER\\icebadger_deploy.tar.gz root@<span class="cmd-arg">YOUR_VPS_IP</span>:/opt/</pre>
    </div>

    <div class="step-list" style="counter-reset: step-counter 2;">
        <div class="step-item">
            <strong>Extract on Linux:</strong>
            Connect via SSH and unpack into <code>/opt/icebadger</code>:
        </div>
    </div>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>Ubuntu / Debian Shell</span>
        </div>
        <pre class="code-content"><span class="cmd-prompt">root@vps:~#</span> mkdir -p /opt/icebadger &amp;&amp; cd /opt/icebadger
<span class="cmd-prompt">root@vps:/opt/icebadger#</span> tar -xzvf /opt/icebadger_deploy.tar.gz -C .</pre>
    </div>

    <!-- PART F -->
    <div class="part-header">
        <span class="part-tag">Part F</span>
        <span>Automated 1-Click Server Hardening &amp; Deployment (pre-setup.sh)</span>
    </div>

    <p>ICEBADGER includes an automated production staging script, <code>pre-setup.sh</code>, located in the project root. This script automates complete server hardening, Cloudflare firewall shielding, Nginx reverse proxying, and background process supervision in 30 seconds.</p>

    <div class="callout callout-tip">
        <div class="callout-title">⚡ What pre-setup.sh Automates Under the Hood:</div>
        1. <strong>System Dependencies:</strong> Automatically installs <code>ufw</code>, <code>nginx</code>, <code>certbot</code>, <code>fail2ban</code>, <code>jq</code>, and Python 3 tools.<br>
        2. <strong>Cloudflare UFW Firewall Shield:</strong> Dynamically downloads official Cloudflare IPv4 and IPv6 subnets, whitelists ports 80/443 exclusively for Cloudflare, and blocks all raw direct internet probing.<br>
        3. <strong>Direct-to-IP Scanner Shield (HTTP 444):</strong> Automatically drops connections immediately if any automated scanner accesses your VPS via its raw IP address without your domain name.<br>
        4. <strong>Real Visitor IP Restoration:</strong> Generates <code>/etc/nginx/conf.d/cloudflare_real_ip.conf</code> ensuring Nginx and the <strong>Stealth Gate</strong> log genuine victim IPs rather than Cloudflare edge IPs.<br>
        5. <strong>Multi-Domain Dynamic Reverse Proxy:</strong> Automatically proxies any custom domains and subdomains configured in Cloudflare to internal port 5000 with WebSocket support.<br>
        6. <strong>Production Systemd Service:</strong> Generates <code>/etc/systemd/system/icebadger.service</code> with 4 Gunicorn workers, auto-reboot persistence, and crash recovery.
    </div>

    <div class="step-list">
        <div class="step-item">
            <strong>Execute 1-Click Staging on VPS:</strong>
            Inside <code>/opt/icebadger</code> on your Linux server, execute:
        </div>
    </div>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>Ubuntu / Debian Shell (root@vps)</span>
        </div>
        <pre class="code-content"><span class="cmd-prompt">root@vps:/opt/icebadger#</span> chmod +x pre-setup.sh
<span class="cmd-prompt">root@vps:/opt/icebadger#</span> ./pre-setup.sh
<span class="cmd-prompt">root@vps:/opt/icebadger#</span> systemctl enable --now icebadger</pre>
    </div>

    <!-- PART G -->
    <div class="part-header">
        <span class="part-tag">Part G</span>
        <span>Service Monitoring, Logs &amp; Health Commands</span>
    </div>

    <p>Monitor service health and inspect live telemetry using standard systemctl commands:</p>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>Daemon Health Commands</span>
        </div>
        <pre class="code-content"><span class="cmd-comment"># Check background service status (should display 'active (running)')</span>
<span class="cmd-prompt">root@vps:~#</span> systemctl status icebadger

<span class="cmd-comment"># Stream real-time application logs (tail -f equivalent)</span>
<span class="cmd-prompt">root@vps:~#</span> journalctl -u icebadger -f

<span class="cmd-comment"># Restart application after settings or template updates</span>
<span class="cmd-prompt">root@vps:~#</span> systemctl restart icebadger</pre>
    </div>

    <!-- PART H -->
    <div class="part-header">
        <span class="part-tag">Part H</span>
        <span>Database Persistence, Domain Immunity &amp; Disaster Recovery</span>
    </div>

    <p>A critical architectural feature of ICEBADGER is that <strong>the database is 100% decoupled from the domain name, registrar, and admin session</strong>.</p>

    <div class="callout callout-tip">
        <div class="callout-title">🔒 Why Your Database is Immune to Domain Bans &amp; Admin Lockouts</div>
        1. <strong>Domain Ban Immunity:</strong> The SQLite database (<code>icebadger.db</code>) resides locally on your VPS storage. If a domain is burned or revoked, <strong>all tokens, captured credentials, and email archives are completely unaffected</strong>. Simply attach a new domain in Cloudflare, update <code>deploy_host</code> in <code>settings.json</code>, and resume operations in under 60 seconds with zero data loss.<br>
        2. <strong>Admin Lockout Immunity:</strong> If an admin password is forgotten, you possess root SSH access to query SQLite directly or reset credentials via Python CLI.<br>
        3. <strong>Crash Resilience:</strong> SQLite utilizes Write-Ahead Logging (WAL) and atomic transactions. Committed sessions remain completely safe.
    </div>

    <h3>1. Automated Daily Off-Site Database Backup Cron</h3>
    <p>Set up an automated snapshot cron on the VPS that generates clean, timestamped SQLite backups daily:</p>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>Crontab Setup (root@vps)</span>
        </div>
        <pre class="code-content"><span class="cmd-prompt">root@vps:~#</span> crontab -e
<span class="cmd-comment"># Back up the database every night at 02:00 AM:</span>
0 2 * * * sqlite3 /opt/icebadger/icebadger.db ".backup '/opt/icebadger_backups/icebadger_$(date +\\%Y\\%m\\%d).db'"</pre>
    </div>

    <h3>2. One-Line On-Demand Pull to Local Windows PC</h3>
    <p>You can instantly pull the latest production database down to your local Windows machine at any moment via PowerShell SCP:</p>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>PowerShell (Windows)</span>
        </div>
        <pre class="code-content"><span class="cmd-prompt">PS C:\\Users\\Admin&gt;</span> scp root@<span class="cmd-arg">YOUR_VPS_IP</span>:/opt/icebadger/icebadger.db <span class="cmd-prompt">"C:\\Users\\IT-ADMIN\\Desktop\\FLOW\\ICEBADGER\\icebadger_production_backup.db"</span></pre>
    </div>

    <h3>3. Domain Burn Recovery Procedure (60-Second Pivot)</h3>
    <p>If your primary domain is flagged or burned, execute this rapid pivot without losing a single captured token:</p>

    <div class="step-list">
        <div class="step-item">
            Purchase or link a fresh domain in Cloudflare and point an A record to <code>YOUR_VPS_IP</code>.
        </div>
        <div class="step-item">
            Update <code>settings.json</code>: <code>"deploy_host": "https://newdomain.com"</code>.
        </div>
        <div class="step-item">
            Restart service: <code>systemctl restart icebadger</code>.
        </div>
        <div class="step-item">
            All active tokens, operator workspaces, and historical captured accounts remain immediately live and accessible.
        </div>
    </div>

    <!-- PART I -->
    <div class="part-header">
        <span class="part-tag">Part I</span>
        <span>Domain Clarification &amp; Anti-Indexing Defense (robots.txt)</span>
    </div>

    <div class="callout callout-info">
        <div class="callout-title">🌐 FAQ: Is it the "Cloudflare Domain" or "The Domain I Bought" in .env?</div>
        <strong>You always enter the domain you bought</strong> (e.g., <code>https://yourcompanydomain.com</code>).<br>
        Cloudflare does not issue you a separate website domain. Cloudflare acts as the DNS shield and Anycast proxy managing that domain. When visitors navigate to <code>https://yourcompanydomain.com</code>, Cloudflare terminates SSL at the edge and securely proxies the connection to your VPS.
    </div>

    <h3>Is There a Need for a robots.txt File?</h3>
    <p><strong>Yes, absolutely.</strong> Without an anti-indexing defense, web search engines (Googlebot, Bingbot, Yahoo) will crawl and publicly index your pre-landing pages, campaigns, and administrative login paths into search results.</p>

    <div class="step-list">
        <div class="step-item">
            <strong>Standard Disallow Rules:</strong> ICEBADGER automatically serves <code>/robots.txt</code> instructing all compliant search engines to never crawl the host:
        </div>
    </div>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>GET /robots.txt Response</span>
        </div>
        <pre class="code-content">User-agent: *
Disallow: /</pre>
    </div>

    <div class="step-list" style="counter-reset: step-counter 1;">
        <div class="step-item">
            <strong>Global HTTP Anti-Index Headers (X-Robots-Tag):</strong> Every HTTP response from ICEBADGER attaches the RFC-standard crawler rejection header:
        </div>
    </div>

    <div class="terminal-block">
        <div class="terminal-header">
            <span>HTTP Response Header</span>
        </div>
        <pre class="code-content">X-Robots-Tag: noindex, nofollow, noarchive, nosnippet</pre>
    </div>

    <div class="callout callout-tip">
        <div class="callout-title">🛡️ Dual-Tier Crawler Protection Architecture</div>
        1. <strong>Compliant Crawlers (Google, Bing, DuckDuckGo):</strong> Respect <code>robots.txt</code> and <code>X-Robots-Tag</code>; will never index your lures into public search results.<br>
        2. <strong>Aggressive Scanners (Security scanners, VirusTotal, automated bots):</strong> Ignore <code>robots.txt</code> intentionally; automatically identified by <strong>Stealth Gate</strong> heuristic User-Agent analysis and deflected to Office.com before reaching any lure code.
    </div>

    <!-- Document Footer -->
    <div class="doc-footer">
        <div>CRIMSON PAW / ICEBADGER ENTERPRISE — SOP-INFRA-CF-02</div>
        <div>CONFIDENTIAL // RED TEAM OPERATIONAL STAGING ONLY</div>
        <div>Standard Operating Procedure Manual</div>
    </div>

</body>
</html>
"""

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"[SUCCESS] Wrote compact seamless guide HTML to {HTML_PATH} ({os.path.getsize(HTML_PATH)} bytes)")

print("\n=== COMPILING SEAMLESS VPS & CLOUDFLARE GUIDE PDF VIA SELENIUM CDP ===")
import base64
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--disable-gpu')
opts.add_argument('--no-sandbox')
driver = webdriver.Chrome(options=opts)
try:
    file_url = f"file:///{HTML_PATH.replace(os.sep, '/')}"
    driver.get(file_url)
    time.sleep(2)
    pdf_params = {
        'printBackground': True,
        'paperWidth': 8.27,
        'paperHeight': 11.69,
        'marginTop': 0.35,
        'marginBottom': 0.35,
        'marginLeft': 0.45,
        'marginRight': 0.45
    }
    result = driver.execute_cdp_cmd('Page.printToPDF', pdf_params)
    with open(PDF_PATH, 'wb') as f:
        f.write(base64.b64decode(result['data']))
    pdf_size_kb = os.path.getsize(PDF_PATH) / 1024
    print(f"[SUCCESS] Seamless PDF Generated Successfully: {PDF_PATH} ({pdf_size_kb:.1f} KB)")
finally:
    driver.quit()
