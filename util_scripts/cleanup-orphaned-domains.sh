#!/bin/bash

DOMAIN_TO_REMOVE="$1"
DRY_RUN=0

if [[ "$2" == "--dry-run" ]]; then
    DRY_RUN=1
fi

if [[ -z "$DOMAIN_TO_REMOVE" ]]; then
    echo "Usage: $0 <domain-to-remove>"
    exit 1
fi


echo "=== Cleaning up orphaned domain: $DOMAIN_TO_REMOVE ==="

# 1. Remove from ACME certificate storage
if [ -f "/data/coolify/proxy/acme.json" ]; then
    echo "🧹 Backing up and cleaning ACME storage..."
    cp /data/coolify/proxy/acme.json /data/coolify/proxy/acme.json.backup
    
    # Remove certificates for the domain (requires jq)
    if command -v jq >/dev/null; then
        jq "del(.letsencrypt.Certificates[] | select(.domain.main | contains(\"${DOMAIN_TO_REMOVE}\")))" /data/coolify/proxy/acme.json > /tmp/acme_clean.json
        mv /tmp/acme_clean.json /data/coolify/proxy/acme.json
        echo "✅ Cleaned ACME storage"
    else
        echo "⚠️  jq not available, manual ACME cleanup needed"
    fi
fi

# 2. Remove dynamic configuration files
echo "🧹 Removing dynamic config files..."
if [[ -n "$file" ]]; then

    find /data/coolify -name "*.yml" -o -name "*.yaml" -o -name "*.toml" | xargs grep -l "${DOMAIN_TO_REMOVE}" | while read file; do
        echo "🗑️  Removing: $file"
        rm -f "$file"
    done
fi
# 3. Stop and remove containers with the domain
echo "🧹 Checking for containers with orphaned domain..."
docker ps -a --format "{{.Names}}" | while read container; do
    if docker inspect "$container" | grep -q "${DOMAIN_TO_REMOVE}"; then
        echo "🗑️  Found container with orphaned domain: $container"
        echo "   Stopping and removing..."
        docker stop "$container" 2>/dev/null || true
        docker rm "$container" 2>/dev/null || true
    fi
done

# 4. Clean up application directories
echo "🧹 Cleaning application directories..."
if [[ -n "$file" ]]; then

    find /data/coolify -type f -name "*.json" -o -name "*.env" | xargs grep -l "${DOMAIN_TO_REMOVE}" | while read file; do
        echo "🗑️  Found reference in: $file"
        # Backup before cleaning
        cp "$file" "$file.backup"
        sed -i  "/${DOMAIN_TO_REMOVE}/d" "$file"
    done
fi

echo "✅ Cleanup complete"
echo "🔄 Restarting Traefik to apply changes..."
docker restart coolify-proxy

echo "=== Cleanup finished ==="