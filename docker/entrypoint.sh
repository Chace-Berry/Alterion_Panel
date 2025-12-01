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

# Step 3: Wait for PostgreSQL to be ready (without loading Django)
echo ""
echo "[3/5] Waiting for PostgreSQL..."
MAX_RETRIES=30
RETRY_COUNT=0
until python -c "import psycopg2; psycopg2.connect(host='${POSTGRES_HOST:-db}', port=${POSTGRES_PORT:-5432}, user='postgres', password='${POSTGRES_PASSWORD}', dbname='postgres')" > /dev/null 2>&1 || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "⏳ Waiting for PostgreSQL... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ PostgreSQL connection failed after $MAX_RETRIES attempts"
    exit 1
fi
echo "✓ PostgreSQL is ready"

# Step 4: Initialize PostgreSQL database (create DB user and database only)
# This MUST run before Django tries to connect to the database
echo ""
echo "[4/7] Initializing PostgreSQL..."
python manage.py init_system --db-only || {
    echo "❌ PostgreSQL initialization failed!"
    exit 1
}

# Step 5: Run database migrations
echo ""
echo "[5/7] Running database migrations..."
python manage.py migrate --noinput || true

# Step 6: Create OAuth application (after migrations)
echo ""
echo "[6/7] Setting up OAuth application..."
python manage.py init_system --oauth-only || echo "⚠ OAuth setup had issues, continuing..."

# Step 7: Collect static files
echo ""
echo "[7/8] Collecting static files..."
python manage.py collectstatic --noinput || true

# Step 8: Configure Nginx
echo ""
echo "[8/8] Configuring Nginx..."
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
