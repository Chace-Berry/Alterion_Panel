#!/bin/bash
set -e

echo "=========================================="
echo "Alterion Panel - Container Initialization"
echo "=========================================="

# Navigate to the backend directory
cd /app/backend

# Step 1: Generate Server ID if it doesn't exist
echo ""
echo "[1/4] Checking Server ID..."
if [ ! -f "dashboard/serverid.dat" ]; then
    echo "⚠ Server ID not found. Generating new server ID..."
    python -c "
import sys
sys.path.insert(0, '/app/backend')
from dashboard.views import get_stable_server_id
server_id = get_stable_server_id()
print(f'✓ Server ID generated: {server_id}')
"
else
    echo "✓ Server ID already exists"
    cat dashboard/serverid.dat
fi

# Step 2: Generate encryption keys if they don't exist
echo ""
echo "[2/4] Checking Encryption Keys..."
if [ ! -f "services/private-key.pem" ] || [ ! -f "services/public-key.pem" ]; then
    echo "⚠ Encryption keys not found. Generating RSA key pair..."
    python -m services.pem --force
else
    echo "✓ Encryption keys already exist"
fi

# Step 3: Run database migrations
echo ""
echo "[3/4] Running database migrations..."
python manage.py migrate --noinput || true

# Step 4: Collect static files
echo ""
echo "[4/4] Collecting static files..."
python manage.py collectstatic --noinput || true

# Step 5: Configure Nginx
echo ""
echo "[5/5] Configuring Nginx..."
SERVER_NAME=${SERVER_NAME:-localhost}
sed -i "s/{{SERVER_NAME}}/$SERVER_NAME/g" /etc/nginx/nginx.conf
echo "✓ Nginx configured for $SERVER_NAME"

echo ""
echo "=========================================="
echo "✓ Initialization complete!"
echo "=========================================="
echo ""

# Execute the main command (passed as arguments to this script)
exec "$@"
