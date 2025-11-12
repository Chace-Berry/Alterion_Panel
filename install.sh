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
SERVICE_USER="www-data"
SERVICE_GROUP="www-data"
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

# Create service user if it doesn't exist
if ! id "$SERVICE_USER" &>/dev/null; then
    echo -e "${YELLOW}Creating service user: $SERVICE_USER${NC}"
    useradd -r -s /bin/bash -d $INSTALL_DIR $SERVICE_USER
fi
echo -e "${GREEN}✓${NC} Service user $SERVICE_USER exists"

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
    SECRET_KEY=$(sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
    
    sudo -u $SERVICE_USER tee "$ENV_FILE" > /dev/null << EOF
# Django Settings
SECRET_KEY='$SECRET_KEY'
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQLite)
DATABASE_URL=sqlite:///$INSTALL_DIR/backend/backend/db.sqlite3

# Redis Cache
REDIS_URL=redis://localhost:6379/0

# Security
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
EOF
    chmod 600 "$ENV_FILE"
    echo -e "${GREEN}✓${NC} .env file created"
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
echo -e "  Port:     ${YELLOW}$PORT${NC}"
echo -e "  URL:      ${YELLOW}http://localhost:$PORT${NC}"
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
echo -e "  1. Update ALLOWED_HOSTS in: ${YELLOW}$ENV_FILE${NC}"
echo -e "     Add your server IP or domain name"
echo ""
echo -e "  2. Configure firewall:"
echo -e "     ${YELLOW}ufw allow $PORT${NC}"
echo ""
echo -e "  3. Access panel at: ${YELLOW}http://your-server-ip:$PORT${NC}"
echo -e "     Login with the admin credentials you just created"
echo ""
echo -e "${YELLOW}For production use, consider setting up Nginx as a reverse proxy with SSL${NC}"
echo ""
