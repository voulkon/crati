#!/usr/bin/env bash
# Coolify/Traefik labels generation functions

# Colors for output
LBL_GREEN='\033[0;32m'
LBL_YELLOW='\033[1;33m'
LBL_RED='\033[0;31m'
LBL_BLUE='\033[0;34m'
LBL_NC='\033[0m' # No Color

# Generate Traefik labels for a service
generate_service_labels() {
    local service_name="$1"
    local subdomain="$2"
    local port="$3"
    local env_name="$4"
    local enable_basic_auth="${5:-false}"
    local resource_uuid="${6:-lgwgsc00gcgoo4wscogwswkk}"
    
    local router_name="${service_name}-${env_name}"
    
    cat << EOF
  ${service_name}:
    labels:
      # Traefik routing
      - traefik.enable=true
      - traefik.http.routers.${router_name}.rule=Host(\`${subdomain}\`)
      - traefik.http.routers.${router_name}.entrypoints=https
      - traefik.http.routers.${router_name}.tls=true
      - traefik.http.routers.${router_name}.tls.certresolver=letsencrypt
      - traefik.http.services.${router_name}.loadbalancer.server.port=${port}
      
      # HTTP to HTTPS redirect
      - traefik.http.routers.${router_name}-http.rule=Host(\`${subdomain}\`)
      - traefik.http.routers.${router_name}-http.entrypoints=http
      - traefik.http.routers.${router_name}-http.middlewares=redirect-to-https
      
      # Compression middleware
      - traefik.http.routers.${router_name}.middlewares=gzip
EOF

    if [[ "$enable_basic_auth" == "true" ]]; then
        cat << EOF
      
      # Basic Authentication
      - traefik.http.middlewares.${router_name}-auth.basicauth.users=\${BASIC_AUTH_HASH}
      - traefik.http.routers.${router_name}.middlewares=gzip,${router_name}-auth
EOF
    fi
    
    echo ""
}

# Generate Caddy labels (alternative to Traefik)
generate_caddy_labels() {
    local service_name="$1"
    local subdomain="$2"
    local port="$3"
    
    cat << EOF
      # Caddy labels
      - caddy_0.encode=zstd gzip
      - caddy_0.handle_path.0_reverse_proxy={{upstreams}}
      - caddy_0.handle_path=/*
      - caddy_0.header=-Server
      - caddy_0.try_files={path} /index.html /index.php
      - caddy_0=https://${subdomain}
EOF
}

# Generate complete labels file for all services
generate_labels_file() {
    local env_name="$1"
    local domain="$2"
    local services="$3"
    local pattern="$4"
    local enable_basic_auth="${5:-false}"
    
    local labels_file="${PROJECT_ROOT}/coolify/labels.${env_name}.yml"
    
    echo -e "\n${LBL_BLUE}🏷️  Generating Coolify labels for environment: $env_name${LBL_NC}"
    
    # Start the labels file
    cat > "$labels_file" << EOF
# Coolify/Traefik Labels for Environment: ${env_name}
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# ============================================
# These labels should be merged into your docker-compose.prod.yml
# OR set in Coolify UI under each service's configuration

# Global middlewares (add to any service or in Traefik config)
x-middlewares:
  redirect-to-https:
    redirectscheme:
      scheme: https
      permanent: true
  gzip:
    compress: true

# Service-specific labels:
services:
EOF

    # Get port for each service
    local port
    for service in $services; do
        local subdomain
        if [[ "$pattern" == "env-service" ]]; then
            subdomain="${env_name}-${service}.${domain}"
        else
            subdomain="${service}-${env_name}.${domain}"
        fi
        
        # Get port based on service name
        case "$service" in
            jaeger)
                port="${SERVICE_PORT_JAEGER:-16686}"
                ;;
            grafana)
                port="${SERVICE_PORT_GRAFANA:-3000}"
                ;;
            rabbitmq)
                port="${SERVICE_PORT_RABBITMQ:-15672}"
                ;;
            redis-commander)
                port="${SERVICE_PORT_REDIS_COMMANDER:-8081}"
                ;;
            flower)
                port="${SERVICE_PORT_FLOWER:-5555}"
                ;;
            opensearch_dashboards)
                port="${SERVICE_PORT_OPENSEARCH_DASHBOARDS:-5601}"
                ;;
            *)
                port="8080"
                ;;
        esac
        
        generate_service_labels "$service" "$subdomain" "$port" "$env_name" "$enable_basic_auth" >> "$labels_file"
    done
    
    echo -e "${LBL_GREEN}✓ Labels saved to $labels_file${LBL_NC}"
    
    return 0
}

# Generate deployment guide
generate_deployment_guide() {
    local env_name="$1"
    local domain="$2"
    local services="$3"
    local pattern="$4"
    
    local guide_file="${PROJECT_ROOT}/coolify/deployment-guide.${env_name}.md"
    
    echo -e "\n${LBL_BLUE}📝 Generating deployment guide${LBL_NC}"
    
    # Build service URLs
    local main_url="https://${env_name}.${domain}"
    local service_urls=""
    
    for service in $services; do
        local subdomain
        if [[ "$pattern" == "env-service" ]]; then
            subdomain="${env_name}-${service}.${domain}"
        else
            subdomain="${service}-${env_name}.${domain}"
        fi
        
        local service_display=$(echo "$service" | tr '_' ' ' | sed 's/.*/\u&/')
        service_urls="${service_urls}\n   - **${service_display}**: https://${subdomain}"
    done
    
    cat > "$guide_file" << EOF
# Deployment Guide: ${env_name}

## Overview
This guide will help you deploy the **${env_name}** environment to Coolify.

**Generated**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

---

## Prerequisites

- [ ] Coolify instance running and accessible
- [ ] Docker Compose file ready (\`docker-compose.prod.yml\`)
- [ ] DNS records propagated (check with \`dig ${env_name}.${domain}\`)
- [ ] Environment secrets generated (check \`.env_files/.env.${env_name}\`)

---

## Step 1: Verify DNS Records

All DNS records have been created in Cloudflare. Verify propagation:

\`\`\`bash
# Check main A record
dig ${env_name}.${domain} +short

# Check CNAME records (should return ${env_name}.${domain})
$(for service in $services; do
    local subdomain
    if [[ "$pattern" == "env-service" ]]; then
        subdomain="${env_name}-${service}.${domain}"
    else
        subdomain="${service}-${env_name}.${domain}"
    fi
    echo "dig ${subdomain} +short"
done)
\`\`\`

⏰ DNS propagation typically takes 1-5 minutes.

---

## Step 2: Create Project in Coolify

1. Log in to your Coolify dashboard
2. Click **"+ New Resource"**
3. Select **"Docker Compose"**
4. Name: \`${env_name}\`
5. Upload \`docker-compose.prod.yml\`

---

## Step 3: Configure Environment Variables

In Coolify, go to your project → **Environment Variables** → Add the following:

### Copy from \`.env_files/.env.${env_name}\`:

\`\`\`bash
# Database
POSTGRES_USER=<from .env file>
POSTGRES_PASSWORD=<from .env file>
POSTGRES_DB=<from .env file>

# RabbitMQ
RABBITMQ_USER=<from .env file>
RABBITMQ_PASSWORD=<from .env file>

# Redis
REDIS_PASSWORD=<from .env file>

# Django
DJANGO_SECRET_KEY=<from .env file>
ALLOWED_HOSTS=${env_name}.${domain}

# Jaeger
JAEGER_HOST=jaeger
JAEGER_PORT=4317

# OpenSearch
OPENSEARCH_URL=http://opensearch:9200
\`\`\`

💡 **Tip**: You can copy-paste the entire \`.env.${env_name}\` file content into Coolify's bulk environment variable editor.

---

## Step 4: Configure Service Domains

For each service that needs external access, set the domain in Coolify:

### Main Application (nginx):
- Domain: \`${env_name}.${domain}\`
- Port: \`80\`
- ✅ Enable HTTPS (Let's Encrypt)

### Auxiliary Services:
${service_urls}

For each service:
1. Go to service settings in Coolify
2. Add domain (as listed above)
3. Enable HTTPS/Let's Encrypt
4. (Optional) Enable HTTP Basic Auth for security

---

## Step 5: Deploy

1. Click **"Deploy"** in Coolify
2. Monitor logs for any errors
3. Wait for all services to be healthy (check health checks)
4. Wait for SSL certificates to be provisioned (~2-3 minutes)

---

## Step 6: Verify Deployment

### Check Service Health:

\`\`\`bash
# Main application
curl -I ${main_url}

# Individual services
$(for service in $services; do
    local subdomain
    if [[ "$pattern" == "env-service" ]]; then
        subdomain="${env_name}-${service}.${domain}"
    else
        subdomain="${service}-${env_name}.${domain}"
    fi
    echo "curl -I https://${subdomain}"
done)
\`\`\`

### Access Services:

- **Main App**: ${main_url}
${service_urls}

---

## Step 7: Post-Deployment

### Database Initialization

If this is a fresh environment, you may need to:

\`\`\`bash
# Run migrations
docker exec -it <backend-container> poetry run python manage.py migrate

# Create superuser
docker exec -it <backend-container> poetry run python manage.py createsuperuser
\`\`\`

### Data Restoration (Optional)

If you need to restore data from backups:

\`\`\`bash
# See separate restoration scripts
./util_scripts/restore-data.sh ${env_name}
\`\`\`

---

## Troubleshooting

### SSL Certificate Issues
- Wait 5-10 minutes for Let's Encrypt provisioning
- Check Traefik logs in Coolify
- Verify DNS records are correct

### Service Not Accessible
- Check service logs in Coolify
- Verify port configuration matches docker-compose
- Check firewall rules on server

### Database Connection Issues
- Verify DATABASE_URL environment variable
- Check if PostgreSQL container is running
- Review PostgreSQL logs

---

## Useful Commands

\`\`\`bash
# View all containers
docker ps

# Check specific service logs
docker logs <container-name> --tail=100 -f

# Execute command in backend
docker exec -it <backend-container> bash

# Check network connectivity
docker exec -it <backend-container> ping db
\`\`\`

---

## Cleanup

To remove this environment:

\`\`\`bash
./util_scripts/coolify-setup/cleanup-environment.sh ${env_name}
\`\`\`

This will:
- Remove DNS records from Cloudflare
- Archive environment secrets
- Provide instructions for Coolify cleanup

---

## Support

For issues:
1. Check Coolify logs
2. Review this deployment guide
3. Check \`coolify/dns-records.${env_name}.json\` for DNS configuration
4. Review \`.env_files/.env.${env_name}.summary\` for secrets summary

EOF

    echo -e "${LBL_GREEN}✓ Deployment guide saved to $guide_file${LBL_NC}"
    
    return 0
}
