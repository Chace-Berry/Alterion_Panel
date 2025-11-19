#!/bin/bash

#######################################
# Alterion Panel Installation Script
# Installs and configures the service
#######################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/alterion-panel"
LOG_DIR="/var/log/alterion-panel"
SERVICE_USER="alterion-panel"
SERVICE_GROUP="alterion-panel"
PYTHON_VERSION="python3"
PORT=13527

# Script must be run as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
   exit 1
fi

echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Alterion Panel Installation Script  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo ""

# Check if Python 3 is installed
if ! command -v $PYTHON_VERSION &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.8 or higher first"
    exit 1
fi

PYTHON_VER=$($PYTHON_VERSION --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓${NC} Found Python $PYTHON_VER"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo -e "${YELLOW}Installing pip...${NC}"
    apt-get update
    apt-get install -y python3-pip python3-venv
fi
echo -e "${GREEN}✓${NC} pip is available"

# Check if Redis is installed
if ! command -v redis-server &> /dev/null; then
    echo -e "${YELLOW}Redis not found. Installing Redis...${NC}"
    apt-get update
    apt-get install -y redis-server
    systemctl enable redis-server
    systemctl start redis-server
fi
echo -e "${GREEN}✓${NC} Redis is installed and running"

# Install rsync if not present
if ! command -v rsync &> /dev/null; then
    echo -e "${YELLOW}Installing rsync...${NC}"
    apt-get install -y rsync
fi

# Create service user/group if it doesn't exist
if ! id "$SERVICE_USER" &>/dev/null; then
    echo -e "${YELLOW}Creating service user: $SERVICE_USER as a regular user${NC}"
    useradd --create-home --shell /bin/bash $SERVICE_USER
fi
if ! getent group "$SERVICE_GROUP" &>/dev/null; then
    echo -e "${YELLOW}Creating service group: $SERVICE_GROUP${NC}"
    groupadd --system $SERVICE_GROUP
fi
echo -e "${GREEN}✓${NC} Service user/group $SERVICE_USER/$SERVICE_GROUP exists"

# Create directories
echo -e "${BLUE}Creating directories...${NC}"
mkdir -p $INSTALL_DIR
mkdir -p $LOG_DIR

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Copy application files
echo -e "${BLUE}Copying application files...${NC}"
rsync -av --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='node_modules' --exclude='build' --exclude='dist' "$SCRIPT_DIR/" "$INSTALL_DIR/"
echo -e "${GREEN}✓${NC} Application files copied"

# Set ownership
echo -e "${BLUE}Setting permissions...${NC}"
chown -R $SERVICE_USER:$SERVICE_GROUP $INSTALL_DIR
chown -R $SERVICE_USER:$SERVICE_GROUP $LOG_DIR
chmod -R 755 $INSTALL_DIR
chmod -R 755 $LOG_DIR
echo -e "${GREEN}✓${NC} Permissions set"

# Create virtual environment
echo -e "${BLUE}Creating Python virtual environment...${NC}"
sudo -u $SERVICE_USER $PYTHON_VERSION -m venv $INSTALL_DIR/venv
echo -e "${GREEN}✓${NC} Virtual environment created"

# Upgrade pip in venv
echo -e "${BLUE}Upgrading pip...${NC}"
sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/pip install --upgrade pip
echo -e "${GREEN}✓${NC} pip upgraded"

# Install Python dependencies
echo -e "${BLUE}Installing Python dependencies (this may take a few minutes)...${NC}"
sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/pip install -r $INSTALL_DIR/backend/backend/requirements.txt
echo -e "${GREEN}✓${NC} Dependencies installed"

# Create .env file if it doesn't exist
ENV_FILE="$INSTALL_DIR/backend/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${BLUE}Creating .env configuration file...${NC}"
    
    # Generate Fernet key for encryption
    FERNET_KEY=$(sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
    
    sudo -u $SERVICE_USER tee "$ENV_FILE" > /dev/null << EOF
ALTERION_PK_KEY=$FERNET_KEY
EOF
    chmod 600 "$ENV_FILE"
    chown $SERVICE_USER:$SERVICE_GROUP "$ENV_FILE"
    sync  # Force write to disk
    
    # Verify the file was created and has content
    if [ -s "$ENV_FILE" ]; then
        echo -e "${GREEN}✓${NC} .env file created with encryption key"
    else
        echo -e "${RED}✗${NC} Failed to create .env file"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠${NC} .env file already exists, skipping..."
fi

# Run Django migrations
echo -e "${BLUE}Running database migrations...${NC}"
cd $INSTALL_DIR/backend/backend
sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/python manage.py migrate --noinput
echo -e "${GREEN}✓${NC} Migrations completed"

# Collect static files
echo -e "${BLUE}Collecting static files...${NC}"
sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/python manage.py collectstatic --noinput --clear
echo -e "${GREEN}✓${NC} Static files collected"

# Set proper permissions for SQLite database
if [ -f "$INSTALL_DIR/backend/backend/db.sqlite3" ]; then
    chown $SERVICE_USER:$SERVICE_GROUP "$INSTALL_DIR/backend/backend/db.sqlite3"
    chmod 664 "$INSTALL_DIR/backend/backend/db.sqlite3"
fi

# Ensure the backend/backend directory is writable for SQLite
chmod 775 "$INSTALL_DIR/backend/backend"

# Create superuser
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Admin Account Setup                  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo ""

# Prompt for admin credentials
read -p "Enter admin username: " ADMIN_USERNAME
while [[ -z "$ADMIN_USERNAME" ]]; do
    echo -e "${RED}Username cannot be empty${NC}"
    read -p "Enter admin username: " ADMIN_USERNAME
done

read -p "Enter admin email: " ADMIN_EMAIL
while [[ -z "$ADMIN_EMAIL" ]]; do
    echo -e "${RED}Email cannot be empty${NC}"
    read -p "Enter admin email: " ADMIN_EMAIL
done

# Validate email format
while [[ ! "$ADMIN_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; do
    echo -e "${RED}Invalid email format${NC}"
    read -p "Enter admin email: " ADMIN_EMAIL
done

read -sp "Enter admin password: " ADMIN_PASSWORD
echo ""
while [[ -z "$ADMIN_PASSWORD" ]]; do
    echo -e "${RED}Password cannot be empty${NC}"
    read -sp "Enter admin password: " ADMIN_PASSWORD
    echo ""
done

read -sp "Confirm admin password: " ADMIN_PASSWORD_CONFIRM
echo ""
while [[ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]]; do
    echo -e "${RED}Passwords do not match${NC}"
    read -sp "Enter admin password: " ADMIN_PASSWORD
    echo ""
    read -sp "Confirm admin password: " ADMIN_PASSWORD_CONFIRM
    echo ""
done

# Create superuser using Django shell
echo -e "${BLUE}Creating admin user...${NC}"
sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/python $INSTALL_DIR/backend/backend/manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$ADMIN_USERNAME').exists():
    User.objects.create_superuser('$ADMIN_USERNAME', '$ADMIN_EMAIL', '$ADMIN_PASSWORD')
    print('Superuser created successfully')
else:
    print('User already exists')
EOF
echo -e "${GREEN}✓${NC} Admin user created"

# Create OAuth2 Provider Application
echo -e "${BLUE}Setting up OAuth2 provider application...${NC}"
sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/python $INSTALL_DIR/backend/backend/manage.py shell << 'EOF'
from oauth2_provider.models import Application
from django.contrib.auth import get_user_model
import secrets

User = get_user_model()

# Get the first superuser
user = User.objects.filter(is_superuser=True).first()

if user:
    # Fixed client_id for consistency across installations
    client_id = "XpjXSgFQQ30AQ9RWpm8NsMULl3pcwIt5i9QfdksJ"
    
    # Generate unique client_secret for this server
    client_secret = secrets.token_urlsafe(64)
    
    # Check if application already exists
    app, created = Application.objects.get_or_create(
        client_id=client_id,
        defaults={
            'user': user,
            'redirect_uris': '',
            'client_type': Application.CLIENT_PUBLIC,
            'authorization_grant_type': Application.GRANT_PASSWORD,
            'name': 'Alterion Panel',
            'skip_authorization': True,
        }
    )
    
    if created:
        # Set the client_secret (it will be hashed automatically)
        app.client_secret = client_secret
        app.save()
        print(f'OAuth2 Application created')
        print(f'Client ID: {client_id}')
        print(f'Client Secret: {client_secret}')
    else:
        print('OAuth2 Application already exists')
        print(f'Client ID: {client_id}')
else:
    print('No superuser found to assign OAuth2 application')
EOF
echo -e "${GREEN}✓${NC} OAuth2 provider configured"

# Setup Domain Configuration
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Domain Configuration                 ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo ""

read -p "Enter your domain name (e.g., example.com): " USER_DOMAIN

while [[ -z "$USER_DOMAIN" ]]; do
    echo -e "${RED}Domain cannot be empty${NC}"
    read -p "Enter your domain name: " USER_DOMAIN
done

DOMAIN="$USER_DOMAIN"
ALTERION_SUBDOMAIN="alterion.$DOMAIN"

echo ""
echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║   DNS Configuration Required                               ║${NC}"
echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════╝${NC}"
echo -e "${YELLOW}Please add the following DNS record to your domain:${NC}"
echo ""
echo -e "  Type: ${GREEN}A${NC}"
echo -e "  Name: ${GREEN}alterion${NC}"
echo -e "  Value: ${GREEN}$(curl -s ifconfig.me)${NC} (your server IP)"
echo ""
echo -e "Or:"
echo ""
echo -e "  Type: ${GREEN}CNAME${NC}"
echo -e "  Name: ${GREEN}alterion${NC}"
echo -e "  Value: ${GREEN}$DOMAIN${NC}"
echo ""
read -p "Press Enter after you've configured DNS..."

# Install Nginx if not present
if ! command -v nginx &> /dev/null; then
    echo -e "${YELLOW}Installing Nginx...${NC}"
    apt-get update
    apt-get install -y nginx
fi
echo -e "${GREEN}✓${NC} Nginx is installed"

# Install Certbot for Let's Encrypt
if ! command -v certbot &> /dev/null; then
    echo -e "${YELLOW}Installing Certbot...${NC}"
    apt-get install -y certbot python3-certbot-nginx
fi
echo -e "${GREEN}✓${NC} Certbot is installed"

# Get SSL certificate
echo -e "${BLUE}Obtaining SSL certificate for $ALTERION_SUBDOMAIN...${NC}"
certbot certonly --nginx -d $ALTERION_SUBDOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
    echo -e "${RED}✗${NC} Failed to obtain SSL certificate."
    echo -e "${RED}Please ensure DNS is configured correctly and try again.${NC}"
    exit 1
}

SSL_CERT="/etc/letsencrypt/live/$ALTERION_SUBDOMAIN/fullchain.pem"
SSL_KEY="/etc/letsencrypt/live/$ALTERION_SUBDOMAIN/privkey.pem"
echo -e "${GREEN}✓${NC} SSL certificate obtained"

# Create Nginx configuration
echo -e "${BLUE}Configuring Nginx...${NC}"
NGINX_CONF="/etc/nginx/sites-available/alterion-panel"

cat > "$NGINX_CONF" << 'NGINXEOF'
upstream alterion_backend {
    server 127.0.0.1:13527;
}

server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name DOMAIN_PLACEHOLDER;

    ssl_certificate SSL_CERT_PLACEHOLDER;
    ssl_certificate_key SSL_KEY_PLACEHOLDER;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;

    client_max_body_size 100M;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Static files
    location /static/ {
        alias /opt/alterion-panel/backend/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /opt/alterion-panel/backend/backend/media/;
        expires 7d;
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://alterion_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # Regular HTTP
    location / {
        proxy_pass http://alterion_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
NGINXEOF

# Replace placeholders
sed -i "s|DOMAIN_PLACEHOLDER|$ALTERION_SUBDOMAIN|g" "$NGINX_CONF"
sed -i "s|SSL_CERT_PLACEHOLDER|$SSL_CERT|g" "$NGINX_CONF"
sed -i "s|SSL_KEY_PLACEHOLDER|$SSL_KEY|g" "$NGINX_CONF"

# Enable site
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t || {
    echo -e "${RED}✗${NC} Nginx configuration test failed"
    exit 1
}

# Reload Nginx
systemctl restart nginx
echo -e "${GREEN}✓${NC} Nginx configured and running"

# Install systemd service
echo ""
echo -e "${BLUE}Installing systemd service...${NC}"
cp $INSTALL_DIR/alterion-panel.service /etc/systemd/system/
systemctl daemon-reload
echo -e "${GREEN}✓${NC} Service installed"

# Start and enable service
echo -e "${BLUE}Starting Alterion Panel service...${NC}"
systemctl enable alterion-panel
systemctl restart alterion-panel

# Wait a moment for service to start
sleep 3

# Check service status
if systemctl is-active --quiet alterion-panel; then
    echo -e "${GREEN}✓${NC} Service is running"
else
    echo -e "${RED}✗${NC} Service failed to start"
    echo "Check logs with: journalctl -u alterion-panel -n 50"
    exit 1
fi

# Check if port is listening
if ss -tlnp | grep -q ":$PORT "; then
    echo -e "${GREEN}✓${NC} Service is listening on port $PORT"
else
    echo -e "${YELLOW}⚠${NC} Service may not be listening on port $PORT yet"
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Installation Complete! 🎉            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Service Information:${NC}"
echo -e "  Status:   ${GREEN}Active${NC}"
echo -e "  Backend:  ${YELLOW}Port $PORT${NC}"
echo -e "  URL:      ${GREEN}https://$ALTERION_SUBDOMAIN${NC}"
echo ""
echo -e "${BLUE}Management Commands:${NC}"
echo -e "  Start:    ${YELLOW}systemctl start alterion-panel${NC}"
echo -e "  Stop:     ${YELLOW}systemctl stop alterion-panel${NC}"
echo -e "  Restart:  ${YELLOW}systemctl restart alterion-panel${NC}"
echo -e "  Status:   ${YELLOW}systemctl status alterion-panel${NC}"
echo -e "  Logs:     ${YELLOW}journalctl -u alterion-panel -f${NC}"
echo ""
echo -e "${BLUE}Database:${NC}"
echo -e "  Type:     ${YELLOW}SQLite${NC}"
echo -e "  Location: ${YELLOW}$INSTALL_DIR/backend/backend/db.sqlite3${NC}"
echo ""
echo -e "${BLUE}Admin Credentials:${NC}"
echo -e "  Username: ${GREEN}$ADMIN_USERNAME${NC}"
echo -e "  Email:    ${GREEN}$ADMIN_EMAIL${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Configure firewall:"
echo -e "     ${YELLOW}ufw allow 80/tcp${NC}"
echo -e "     ${YELLOW}ufw allow 443/tcp${NC}"
echo ""
echo -e "  2. Access panel at: ${GREEN}https://$ALTERION_SUBDOMAIN${NC}"
echo -e "     Login with username: ${GREEN}$ADMIN_USERNAME${NC}"
echo ""
echo -e "${GREEN}SSL Certificate auto-renewal is configured via Certbot${NC}"
echo ""
