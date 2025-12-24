# Coolify Environment Setup

Automated environment setup for deploying your application stack to [Coolify](https://coolify.io/) with Cloudflare DNS integration.

## What This Does

This toolset automates the complete setup of isolated environments (dev, staging, preview, PR-specific, etc.) by:

1. **Generating secure secrets** - Database passwords, API keys, etc.
2. **Creating DNS records** - Cloudflare A and CNAME records for all services
3. **Generating Traefik labels** - For automatic SSL and routing
4. **Creating deployment guides** - Step-by-step instructions

## Features

- ✅ **CNAME-based DNS** - Change IP once, all services update
- ✅ **Secure secret generation** - Strong random passwords (32+ chars)
- ✅ **Multiple environments** - dev, staging, preview, pr-123, etc.
- ✅ **Flexible configuration** - Config file + CLI overrides
- ✅ **Dry-run mode** - Preview changes before applying
- ✅ **Cleanup automation** - Remove environments cleanly
- ✅ **SSL auto-provisioning** - Let's Encrypt via Traefik
- ✅ **Optional Basic Auth** - Protect auxiliary services

## Quick Start

### 1. Initial Setup

```bash
# Copy and configure
cp .env.coolify-config.example .env.coolify-config
vim .env.coolify-config  # Add your Cloudflare credentials
```

**Required configuration:**
- `CLOUDFLARE_API_TOKEN` - Get from [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens)
- `CLOUDFLARE_ZONE_ID` - Found in Cloudflare Dashboard → Your Domain → Overview
- `SERVER_IP` - IP where Coolify is running

### 2. Create Environment

```bash
cd util_scripts/coolify-setup
./setup-environment.sh preview
```

This creates:
- `.env_files/.env.preview` - All secrets
- `coolify/dns-records.preview.json` - DNS records created
- `coolify/labels.preview.yml` - Traefik configuration
- `coolify/deployment-guide.preview.md` - Deployment instructions

### 3. Deploy to Coolify

Follow the generated deployment guide at `coolify/deployment-guide.preview.md`

## Usage

### Setup Environment

```bash
./setup-environment.sh ENVIRONMENT [OPTIONS]
```

**Examples:**
```bash
# Basic usage
./setup-environment.sh preview

# Override server IP
./setup-environment.sh dev --server-ip=5.6.7.8

# PR-specific environment
./setup-environment.sh pr-12345

# Dry run (see what would happen)
./setup-environment.sh preview --dry-run

# Regenerate secrets without touching DNS
./setup-environment.sh preview --no-dns --force
```

**Options:**
- `--server-ip IP` - Override server IP
- `--domain DOMAIN` - Override base domain
- `--cloudflare-token TOKEN` - Override Cloudflare API token
- `--cloudflare-zone ZONE` - Override Zone ID
- `--no-dns` - Skip DNS creation (only generate secrets)
- `--no-secrets` - Skip secret generation (only create DNS)
- `--dry-run` - Preview without making changes
- `--force` - Overwrite existing secrets
- `-h, --help` - Show help

### Cleanup Environment

```bash
./cleanup-environment.sh ENVIRONMENT [OPTIONS]
```

**Examples:**
```bash
# Remove all resources
./cleanup-environment.sh pr-12345

# Dry run
./cleanup-environment.sh preview --dry-run

# Only remove DNS
./cleanup-environment.sh dev --no-secrets
```

## DNS Structure

Each environment gets:

**1 A Record (main):**
```
preview.crati.co → 49.13.136.52
```

**6 CNAME Records (services):**
```
jaeger-preview.crati.co → preview.crati.co
grafana-preview.crati.co → preview.crati.co
rabbitmq-preview.crati.co → preview.crati.co
redis-commander-preview.crati.co → preview.crati.co
flower-preview.crati.co → preview.crati.co
opensearch-dashboards-preview.crati.co → preview.crati.co
```

**Benefits:**
- Change IP once, all services update
- Easier to manage
- Standard practice for load balancing

## Generated Files

### Secrets (`.env_files/.env.ENVIRONMENT`)
Contains all sensitive credentials:
- PostgreSQL credentials
- RabbitMQ credentials
- Redis password
- Django secret key
- Basic Auth credentials

**⚠️ Never commit these files to git!**

### DNS Records (`coolify/dns-records.ENVIRONMENT.json`)
Audit log of all DNS records created. Used for cleanup.

### Traefik Labels (`coolify/labels.ENVIRONMENT.yml`)
Traefik/Caddy labels for routing and SSL. Reference when configuring Coolify.

### Deployment Guide (`coolify/deployment-guide.ENVIRONMENT.md`)
Complete step-by-step deployment instructions specific to your environment.

## Configuration

### Config File (`.env.coolify-config`)

```bash
# Cloudflare API
CLOUDFLARE_API_TOKEN=your_token
CLOUDFLARE_ZONE_ID=your_zone_id
CLOUDFLARE_DOMAIN=crati.co

# Server
SERVER_IP=49.13.136.52

# Services to expose
EXPOSED_SERVICES="jaeger grafana rabbitmq redis-commander flower opensearch_dashboards"

# Service ports
SERVICE_PORT_JAEGER=16686
SERVICE_PORT_GRAFANA=3000
SERVICE_PORT_RABBITMQ=15672
SERVICE_PORT_REDIS_COMMANDER=8081
SERVICE_PORT_FLOWER=5555
SERVICE_PORT_OPENSEARCH_DASHBOARDS=5601

# Naming pattern
SUBDOMAIN_PATTERN=service-env  # jaeger-preview.crati.co

# Security
ENABLE_BASIC_AUTH=true
BASIC_AUTH_USERNAME=admin
```

### CLI Overrides

CLI arguments take precedence over config file:

```bash
./setup-environment.sh preview \
  --server-ip=1.2.3.4 \
  --domain=staging.crati.co
```

## Service URLs

After deployment, services are accessible at:

| Service | URL Pattern | Example |
|---------|-------------|---------|
| Main App | `{env}.crati.co` | https://preview.crati.co |
| Jaeger | `jaeger-{env}.crati.co` | https://jaeger-preview.crati.co |
| Grafana | `grafana-{env}.crati.co` | https://grafana-preview.crati.co |
| RabbitMQ | `rabbitmq-{env}.crati.co` | https://rabbitmq-preview.crati.co |
| Flower | `flower-{env}.crati.co` | https://flower-preview.crati.co |
| Redis Commander | `redis-commander-{env}.crati.co` | https://redis-commander-preview.crati.co |
| OpenSearch Dashboards | `opensearch-dashboards-{env}.crati.co` | https://opensearch-dashboards-preview.crati.co |

## Workflow Examples

### Development Environment

```bash
# Create dev environment
./setup-environment.sh dev --server-ip=10.0.0.5

# Deploy to Coolify
# ... deploy via Coolify UI ...

# Later, cleanup
./cleanup-environment.sh dev
```

### Pull Request Preview

```bash
# PR #123 opened
./setup-environment.sh pr-123

# Deploy preview
# ... deploy via Coolify ...

# PR merged, cleanup
./cleanup-environment.sh pr-123
```

### Staging → Production

```bash
# Create staging
./setup-environment.sh staging

# Test and verify
# ...

# Create production with different IP
./setup-environment.sh prod --server-ip=20.0.0.10

# Deploy production
# ...
```

### IP Address Change

```bash
# Update IP for existing environment
./setup-environment.sh preview --server-ip=5.6.7.8

# Only updates A record, CNAMEs automatically follow
```

## Troubleshooting

### DNS Not Propagating

```bash
# Check DNS
dig preview.crati.co +short

# Force flush
# Wait 1-5 minutes for propagation
```

### Cloudflare API Errors

```bash
# Test connection
curl -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json"
```

### SSL Certificate Not Provisioning

- Wait 5-10 minutes for Let's Encrypt
- Check Traefik logs in Coolify
- Verify DNS points to correct IP
- Ensure port 80/443 are accessible

### Secrets Lost

Check archives:
```bash
ls -la .env_files/archive/preview/
```

## Security Best Practices

1. **Never commit** `.env.coolify-config` or `.env_files/.env.*` files
2. **Use Basic Auth** for auxiliary services in production (`ENABLE_BASIC_AUTH=true`)
3. **Rotate secrets** periodically with `--force` flag
4. **Limit Cloudflare token** permissions to DNS edit only
5. **Backup archives** before cleanup

## Directory Structure

```
util_scripts/coolify-setup/
├── setup-environment.sh        # Main setup script
├── cleanup-environment.sh      # Cleanup script
├── lib/
│   ├── cloudflare.sh          # Cloudflare DNS functions
│   ├── secrets.sh             # Secret generation
│   └── labels.sh              # Traefik label generation
└── README.md                  # This file

.env_files/
├── .env.preview               # Generated secrets
├── .env.preview.summary       # Human-readable summary
└── archive/                   # Archived secrets
    └── preview/
        └── .env.preview.20251226_153042

coolify/
├── dns-records.preview.json   # DNS audit log
├── labels.preview.yml         # Traefik labels
├── deployment-guide.preview.md # Deployment instructions
└── archive/                   # Archived config
    └── preview/
```

## Prerequisites

Required tools:
- `curl` - API requests
- `jq` - JSON parsing
- `openssl` - Password generation
- `dig` - DNS verification

Install on macOS:
```bash
brew install curl jq openssl bind
```

## Support

For issues or questions:
1. Check the generated deployment guide
2. Review DNS records in `coolify/dns-records.*.json`
3. Check secrets summary in `.env_files/.env.*.summary`
4. Run with `--dry-run` to debug

## Future Enhancements

Potential additions (not yet implemented):
- Data restoration scripts for PostgreSQL/OpenSearch
- Automated Coolify API integration
- Multi-region support
- Database migration automation
- Health check automation

## License

Part of the crati project.
