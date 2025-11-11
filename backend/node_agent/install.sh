#!/bin/sh
# Don't use set -e because we want to handle errors explicitly
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(whoami)"

echo "PROGRESS:1:8:Creating virtual environment"
cd "${SCRIPT_DIR}"
python3 -m venv venv || {
    echo "ERROR: Failed to create virtual environment"
    exit 1
}

echo "PROGRESS:2:8:Virtual environment created at ${SCRIPT_DIR}/venv"
# Verify venv Python exists
if [ ! -f "${SCRIPT_DIR}/venv/bin/python" ]; then
    echo "ERROR: venv/bin/python not found after venv creation"
    exit 1
fi

echo "PROGRESS:3:8:Upgrading pip in venv"
"${SCRIPT_DIR}/venv/bin/python" -m pip install --upgrade pip setuptools wheel 2>&1 | tee /tmp/pip_upgrade.log
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to upgrade pip"
    cat /tmp/pip_upgrade.log
    exit 1
fi

echo "PROGRESS:4:8:Installing dependencies from requirements.txt"
"${SCRIPT_DIR}/venv/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt" 2>&1 | tee /tmp/pip_install.log
REQUIREMENTS_EXIT=$?
if [ $REQUIREMENTS_EXIT -ne 0 ]; then
    echo "WARNING: requirements.txt install had errors (exit code: $REQUIREMENTS_EXIT)"
    echo "Last 20 lines of pip install log:"
    tail -20 /tmp/pip_install.log
fi

# ALWAYS try to install critical packages explicitly
echo "PROGRESS:4.5:8:Installing critical packages (websockets, cryptography, psutil)"
"${SCRIPT_DIR}/venv/bin/pip" install --force-reinstall websockets cryptography psutil 2>&1 | tee /tmp/pip_critical.log
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install critical packages"
    cat /tmp/pip_critical.log
    exit 1
fi

# Verify critical packages are importable
echo "PROGRESS:4.7:8:Verifying critical packages work"
"${SCRIPT_DIR}/venv/bin/python" -c "import websockets; import cryptography; import psutil; print('All critical packages imported successfully')" || {
    echo "ERROR: Critical packages cannot be imported"
    echo "Python path: ${SCRIPT_DIR}/venv/bin/python"
    echo "Installed packages:"
    "${SCRIPT_DIR}/venv/bin/pip" list
    exit 1
}
echo "✓ Critical packages verified successfully"

echo "PROGRESS:4.8:8:Configuring firewall for WebSocket connections"
# Configure firewall to allow outbound HTTPS/WSS connections (port 443)
# This is needed for WebSocket connections to the panel

# Check which firewall is in use
if command -v ufw >/dev/null 2>&1; then
    # UFW (Ubuntu/Debian)
    echo "Detected UFW firewall, ensuring outbound HTTPS allowed..."
    sudo ufw allow out 443/tcp 2>/dev/null || echo "Note: Could not modify UFW (may need manual configuration)"
    echo "✓ UFW configured (or attempted)"
elif command -v firewall-cmd >/dev/null 2>&1; then
    # firewalld (RHEL/CentOS/Fedora)
    echo "Detected firewalld, ensuring HTTPS service allowed..."
    sudo firewall-cmd --permanent --add-service=https 2>/dev/null || echo "Note: Could not modify firewalld (may need manual configuration)"
    sudo firewall-cmd --reload 2>/dev/null || true
    echo "✓ firewalld configured (or attempted)"
elif command -v iptables >/dev/null 2>&1; then
    # iptables
    echo "Detected iptables, ensuring outbound HTTPS allowed..."
    # Check if rule already exists
    if ! sudo iptables -C OUTPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null; then
        sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || echo "Note: Could not modify iptables (may need manual configuration)"
    fi
    # Try to save rules (different commands for different systems)
    if command -v netfilter-persistent >/dev/null 2>&1; then
        sudo netfilter-persistent save 2>/dev/null || true
    elif command -v iptables-save >/dev/null 2>&1; then
        sudo iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
    fi
    echo "✓ iptables configured (or attempted)"
else
    echo "No firewall detected or firewall already permissive"
fi

echo "PROGRESS:5:8:Setting up systemd service"
# Try to create systemd service if systemd is available
if command -v systemctl >/dev/null 2>&1; then
    SERVICE_NAME="alterion-node-agent"
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    
    # Create service file content
    SERVICE_CONTENT="[Unit]
Description=Alterion Node Agent
After=network.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${SCRIPT_DIR}/venv/bin/python ${SCRIPT_DIR}/node_agent.py --foreground
Restart=always
RestartSec=10
StandardOutput=append:${SCRIPT_DIR}/agent.log
StandardError=append:${SCRIPT_DIR}/agent.log

[Install]
WantedBy=multi-user.target"
    
    # Check if we can write to /etc/systemd/system (need sudo)
    if [ -w "/etc/systemd/system" ]; then
        echo "$SERVICE_CONTENT" > "$SERVICE_FILE"
        systemctl daemon-reload
        systemctl enable "$SERVICE_NAME"
        systemctl start "$SERVICE_NAME"
        echo "PROGRESS:6:8:Service created and started"
    else
        # Try with sudo if available
        if command -v sudo >/dev/null 2>&1; then
            echo "$SERVICE_CONTENT" | sudo tee "$SERVICE_FILE" >/dev/null
            sudo systemctl daemon-reload
            sudo systemctl enable "$SERVICE_NAME"
            sudo systemctl start "$SERVICE_NAME"
            echo "PROGRESS:6:8:Service created and started (with sudo)"
        else
            echo "PROGRESS:6:8:Cannot create systemd service (no sudo), using nohup fallback"
            nohup python node_agent.py > agent.log 2>&1 &
        fi
    fi
else
    # No systemd, use nohup fallback with venv python
    echo "PROGRESS:6:8:No systemd detected, using nohup to start agent"
    cd "${SCRIPT_DIR}"
    nohup "${SCRIPT_DIR}/venv/bin/python" node_agent.py > agent.log 2>&1 &
fi

echo "PROGRESS:7:8:Verifying agent is running"
sleep 2

# Check if process is running (either via systemd or nohup)
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet alterion-node-agent 2>/dev/null || pgrep -f "node_agent.py" >/dev/null; then
        echo "PROGRESS:8:8:Agent successfully started"
    else
        echo "WARNING: Agent may not have started correctly"
    fi
else
    if pgrep -f "node_agent.py" >/dev/null; then
        echo "PROGRESS:8:8:Agent successfully started"
    else
        echo "WARNING: Agent may not have started correctly"
    fi
fi

echo "Installation complete! Agent is running in the background."