#!/bin/bash

# Alterion Panel Setup Script
# This script sets up the integrated React + Django application

echo "🚀 Setting up Alterion Panel..."

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

echo "📦 Installing backend dependencies..."
cd backend/backend
pip install -r requirements.txt

echo "� Setting up Server ID and Encryption Keys..."
# Generate Server ID
python -c "
import sys
sys.path.insert(0, '.')
from dashboard.views import get_stable_server_id
server_id = get_stable_server_id()
print(f'✓ Server ID: {server_id}')
"

# Generate encryption keys
python -m services.pem --force

echo "�🗄️ Setting up database..."
python manage.py migrate

echo "👤 Creating superuser..."
python manage.py createsuperuser --noinput --username admin --email admin@example.com || echo "User may already exist"

echo "📂 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  cd backend/backend && python manage.py runserver"
echo ""
echo "Or use Docker: cd docker && docker-compose up --build"
echo ""
echo "Default admin credentials: admin / (set during createsuperuser)"