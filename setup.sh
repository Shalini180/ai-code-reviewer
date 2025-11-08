#!/bin/bash

# AI Code Reviewer - Quick Setup Script
# This creates the entire project structure and initializes the service

set -e  # Exit on error

echo "🚀 AI Code Reviewer - Quick Setup"
echo "=================================="
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

echo "✅ Prerequisites satisfied"
echo ""

# Create project structure
echo "📁 Creating project structure..."

# Root directories
mkdir -p config
mkdir -p data/{repos,artifacts}
mkdir -p tests/fixtures

# Source directories
mkdir -p src/api
mkdir -p src/queue
mkdir -p src/scm
mkdir -p src/analysis
mkdir -p src/rules/cards/python
mkdir -p src/patch
mkdir -p src/verify
mkdir -p src/policy
mkdir -p src/integrations
mkdir -p src/telemetry

# Create __init__.py files
touch config/__init__.py
touch src/__init__.py
touch src/api/__init__.py
touch src/queue/__init__.py
touch src/scm/__init__.py
touch src/analysis/__init__.py
touch src/rules/__init__.py
touch src/patch/__init__.py
touch src/verify/__init__.py
touch src/policy/__init__.py
touch src/integrations/__init__.py
touch src/telemetry/__init__.py
touch tests/__init__.py

echo "✅ Project structure created"
echo ""

# Setup environment
echo "🔧 Setting up environment..."

if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file from template"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your API keys:"
    echo "   - ANTHROPIC_API_KEY (get from https://console.anthropic.com/)"
    echo "   - GITHUB_TOKEN (optional, for development)"
    echo ""
else
    echo "ℹ️  .env file already exists, skipping..."
fi

# Build and start services
echo "🐳 Building Docker images..."
docker-compose build

echo ""
echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check health
echo ""
echo "🏥 Checking service health..."

MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Services are healthy!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   Attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 3
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Services failed to start properly. Check logs with: docker-compose logs"
    exit 1
fi

echo ""
echo "=================================="
echo "✨ Setup complete!"
echo "=================================="
echo ""
echo "🌐 Service URLs:"
echo "   API:          http://localhost:8000"
echo "   Docs:         http://localhost:8000/docs"
echo "   Health:       http://localhost:8000/health"
echo ""
echo "📊 View logs:"
echo "   docker-compose logs -f"
echo ""
echo "🧪 Test the API:"
echo "   curl http://localhost:8000/health"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""
echo "📚 Next steps:"
echo "   1. Edit .env and add your ANTHROPIC_API_KEY"
echo "   2. Restart services: docker-compose restart"
echo "   3. Continue to Step 2: Git Operations"
echo ""