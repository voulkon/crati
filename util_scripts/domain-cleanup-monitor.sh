#!/bin/bash

# This script should be run periodically (e.g., via cron) to clean up orphaned domains

echo "=== Domain Cleanup Monitor ==="

# Get list of all active applications from Coolify
ACTIVE_DOMAINS=$(docker ps --format "{{.Names}}" | while read container; do
    docker inspect "$container" | grep -o '"traefik.http.routers[^"]*Host[^"]*`[^`]*`' | grep -o '`[^`]*`' | tr -d '`'
done | sort -u)

echo "Active domains found: $(echo "$ACTIVE_DOMAINS" | wc -l)"

# Check ACME storage for domains not in active list
if [ -f "/data/coolify/proxy/acme.json" ] && command -v jq >/dev/null; then
    echo "🔍 Checking for orphaned certificates..."
    
    ACME_DOMAINS=$(cat /data/coolify/proxy/acme.json | jq -r '.letsencrypt.Certificates[]?.domain.main' 2>/dev/null | sort -u)
    
    for acme_domain in $ACME_DOMAINS; do
        if ! echo "$ACTIVE_DOMAINS" | grep -q "^$acme_domain$"; then
            echo "🗑️  Orphaned certificate found: $acme_domain"
            # Add to cleanup list or remove immediately
            echo "$acme_domain" >> /tmp/orphaned_domains.txt
        fi
    done
    
    if [ -f "/tmp/orphaned_domains.txt" ]; then
        echo "📋 Orphaned domains to clean:"
        cat /tmp/orphaned_domains.txt
        
        # Optionally auto-clean (uncomment next lines)
        # echo "🧹 Auto-cleaning orphaned certificates..."
        # while read domain; do
        #     jq "del(.letsencrypt.Certificates[] | select(.domain.main == \"$domain\"))" /data/coolify/proxy/acme.json > /tmp/acme_temp.json
        #     mv /tmp/acme_temp.json /data/coolify/proxy/acme.json
        # done < /tmp/orphaned_domains.txt
        # docker restart coolify-proxy
    fi
fi

echo "=== Monitor complete ==="