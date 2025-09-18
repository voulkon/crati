#!/bin/bash

# SEARCH_TERM="$1"
SEARCH_TERM="fc8sg84c008gg4g4w4wswcsc"

if [[ -z "$SEARCH_TERM" ]]; then
    echo "Usage: $0 <domain-or-app-id>"
    echo "Examples:"
    echo "  $0 reyesjewels.com"
    echo "  $0 fc8sg84c008gg4g4w4wswcsc"
    exit 1
fi

echo "=== Searching for $SEARCH_TERM references ==="

# 1. Check Traefik dynamic configuration
echo "📁 Checking Traefik dynamic configs..."
find /data/coolify -name "*.yml" -o -name "*.yaml" -o -name "*.toml" | xargs grep -l "$SEARCH_TERM" 2>/dev/null || echo "No dynamic config files found"

# 2. Check Traefik ACME storage
echo "📁 Checking ACME certificate storage..."
if [ -f "/data/coolify/proxy/acme.json" ]; then
    echo "Found ACME storage, checking for $SEARCH_TERM..."
    cat /data/coolify/proxy/acme.json | jq -r ".letsencrypt.Certificates[] | select(.domain.main | contains(\"$SEARCH_TERM\")) | .domain.main" 2>/dev/null || echo "No certificates found (or jq not available)"
fi

# 3. Check all container labels
echo "📁 Checking running container labels..."
docker ps -a --format "table {{.Names}}\t{{.Image}}" | while read name image; do
    if [[ "$name" != "NAMES" ]]; then
        labels=$(docker inspect "$name" | grep -i "$SEARCH_TERM" || echo "")
        if [[ -n "$labels" ]]; then
            echo "🔍 Found in container: $name"
            echo "$labels"
        fi
    fi
done

# 4. Check Coolify database/storage
echo "📁 Checking Coolify application data..."
find /data/coolify -type f -name "*.json" -o -name "*.env" | xargs grep -l "$SEARCH_TERM" 2>/dev/null || echo "No app config files found"

# 5. Check environment files
echo "📁 Checking environment files..."
find /data/coolify -name ".env*" | xargs grep -l "$SEARCH_TERM" 2>/dev/null || echo "No .env files found"

echo "=== Search complete ==="