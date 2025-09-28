#!/bin/bash

# Test script to verify logging stack setup
echo "🧪 Testing Logging Stack Setup..."
echo "================================="

# Test Loki
echo "🔍 Testing Loki..."
LOKI_PORT=${LOKI_PORT:-3100}
if curl -s http://localhost:$LOKI_PORT/ready > /dev/null; then
    echo "✅ Loki is ready at http://localhost:$LOKI_PORT"
else
    echo "❌ Loki not accessible at http://localhost:$LOKI_PORT"
fi

# Test Grafana
echo "🔍 Testing Grafana..."
GRAFANA_PORT=${GRAFANA_PORT:-3000}
if curl -s http://localhost:$GRAFANA_PORT/api/health > /dev/null; then
    echo "✅ Grafana is ready at http://localhost:$GRAFANA_PORT"
else
    echo "❌ Grafana not accessible at http://localhost:$GRAFANA_PORT"
fi

# Test Docker network connectivity
echo "🔍 Testing Docker network connectivity..."
docker exec diavgeia_backend ping -c 1 loki > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Backend can reach Loki via Docker network"
else
    echo "❌ Backend cannot reach Loki via Docker network"
fi

docker exec diavgeia_backend ping -c 1 grafana > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Backend can reach Grafana via Docker network"
else
    echo "❌ Backend cannot reach Grafana via Docker network"
fi

# Test Loki API from within containers
echo "🔍 Testing Loki API from backend container..."
docker exec diavgeia_backend curl -s http://loki:3100/ready > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Backend can access Loki API"
else
    echo "❌ Backend cannot access Loki API"
fi

echo "================================="
echo "🎯 Test Summary:"
echo "If all tests pass, your logging stack is properly configured!"
echo "If tests fail, check:"
echo "1. All services are running: docker-compose ps"
echo "2. Network connectivity: docker network ls"
echo "3. Service logs: docker logs diavgeia_loki"
echo ""
echo "Next steps:"
echo "1. Access Grafana: http://localhost:$GRAFANA_PORT (admin/admin)"
echo "2. Check the 'Diavgeia Application Logs' dashboard"
echo "3. Start generating logs by using your application"