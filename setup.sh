#!/bin/bash

# Crati Quick Setup Script
# This script sets up a complete development environment for Crati

set -e

echo "🚀 Crati Development Setup"
echo "=========================="
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "   https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ Created .env file"
else
    echo "ℹ️  .env file already exists, skipping..."
fi

# Generate sample data
echo ""
echo "📊 Generating sample data..."
if [ ! -d "sample-data" ]; then
    mkdir -p sample-data
fi

python3 scripts/generate_sample_data.py --output ./sample-data --count 50
echo "✅ Sample data generated"

# Pull Docker images (optional but speeds up first start)
echo ""
read -p "🐳 Do you want to pre-pull Docker images? This may take a few minutes. (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🐳 Pulling Docker images..."
    docker-compose -f docker/docker-compose.quickstart.yml pull
    echo "✅ Docker images pulled"
fi

# Start services
echo ""
read -p "🚀 Do you want to start Crati now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Starting Crati..."
    docker-compose -f docker/docker-compose.quickstart.yml up -d
    
    echo ""
    echo "⏳ Waiting for services to be ready..."
    sleep 10
    
    # Check if backend is healthy
    if curl -f http://localhost:8000/health &> /dev/null; then
        echo "✅ Backend is healthy"
    else
        echo "⚠️  Backend might still be starting. Check logs: make logs"
    fi
    
    echo ""
    echo "🎉 Crati is running!"
    echo ""
    echo "📍 Access points:"
    echo "   Frontend:  http://localhost"
    echo "   Backend:   http://localhost/api"
    echo "   RabbitMQ:  http://localhost:15672 (crati_user/crati_password)"
    echo "   OpenSearch: http://localhost:9200"
    echo ""
    echo "📊 Useful commands:"
    echo "   View logs:  make logs"
    echo "   Stop:       make stop"
    echo "   Reset DB:   make reset-db"
else
    echo ""
    echo "✅ Setup complete! When you're ready, start Crati with:"
    echo "   docker-compose -f docker/docker-compose.quickstart.yml up"
fi

echo ""
echo "📚 Next steps:"
echo "   1. Read CONTRIBUTING.md for development guidelines"
echo "   2. Check docs/ for architecture and API documentation"
echo "   3. Join our community: [link to Discord/Discussions]"
echo ""
echo "Happy coding! 🎉"
