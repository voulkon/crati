#!/usr/bin/env bash
# Secret generation functions

# Colors for output
SEC_GREEN='\033[0;32m'
SEC_YELLOW='\033[1;33m'
SEC_RED='\033[0;31m'
SEC_BLUE='\033[0;34m'
SEC_NC='\033[0m' # No Color

# Generate a secure random password
generate_password() {
    local length="${1:-32}"
    
    # Use openssl for secure random generation
    openssl rand -base64 48 | tr -d "=+/" | cut -c1-${length}
}

# Generate a secure alphanumeric password (no special chars)
generate_alphanumeric_password() {
    local length="${1:-32}"
    
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c ${length}
}

# Generate Basic Auth password hash
generate_htpasswd() {
    local username="$1"
    local password="$2"
    
    # Use openssl to generate bcrypt hash
    echo "$password" | openssl passwd -apr1 -stdin | sed "s/^/${username}:/"
}

# Generate all secrets for an environment
generate_environment_secrets() {
    local env_name="$1"
    local postgres_user="${2:-crati_user}"
    local postgres_db="${3:-crati_${env_name}}"
    local rabbitmq_user="${4:-crati_rabbitmq}"
    local basic_auth_user="${5:-admin}"
    local basic_auth_pass="${6:-}"
    
    echo -e "\n${SEC_BLUE}🔐 Generating secrets for environment: $env_name${SEC_NC}\n"
    
    # Generate passwords
    local postgres_password=$(generate_password 32)
    local rabbitmq_password=$(generate_password 32)
    local redis_password=$(generate_password 32)
    local opensearch_password=$(generate_password 32)
    local django_secret_key=$(generate_password 50)
    
    # Generate Basic Auth password if not provided
    if [[ -z "$basic_auth_pass" ]]; then
        basic_auth_pass=$(generate_password 24)
    fi
    
    # Generate htpasswd hash
    local basic_auth_hash=$(generate_htpasswd "$basic_auth_user" "$basic_auth_pass")
    
    echo -e "${SEC_GREEN}✓ PostgreSQL password generated${SEC_NC}"
    echo -e "${SEC_GREEN}✓ RabbitMQ password generated${SEC_NC}"
    echo -e "${SEC_GREEN}✓ Redis password generated${SEC_NC}"
    echo -e "${SEC_GREEN}✓ OpenSearch password generated${SEC_NC}"
    echo -e "${SEC_GREEN}✓ Django secret key generated${SEC_NC}"
    echo -e "${SEC_GREEN}✓ Basic Auth credentials generated${SEC_NC}"
    
    # Export variables for use in other scripts
    export GEN_POSTGRES_USER="$postgres_user"
    export GEN_POSTGRES_PASSWORD="$postgres_password"
    export GEN_POSTGRES_DB="$postgres_db"
    export GEN_RABBITMQ_USER="$rabbitmq_user"
    export GEN_RABBITMQ_PASSWORD="$rabbitmq_password"
    export GEN_REDIS_PASSWORD="$redis_password"
    export GEN_OPENSEARCH_PASSWORD="$opensearch_password"
    export GEN_DJANGO_SECRET_KEY="$django_secret_key"
    export GEN_BASIC_AUTH_USER="$basic_auth_user"
    export GEN_BASIC_AUTH_PASSWORD="$basic_auth_pass"
    export GEN_BASIC_AUTH_HASH="$basic_auth_hash"
    
    return 0
}

# Save secrets to environment file
save_secrets_to_env() {
    local env_name="$1"
    local domain="$2"
    local env_file="${PROJECT_ROOT}/.env_files/.env.${env_name}"
    local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    
    echo -e "\n${SEC_BLUE}💾 Saving secrets to $env_file${SEC_NC}"
    
    # Create env file from template
    cat > "$env_file" << EOF
# ============================================
# Environment: ${env_name}
# Generated: ${timestamp}
# ============================================
# WARNING: This file contains sensitive credentials
# DO NOT commit to version control
# DO NOT share publicly

# ──────────────────────── Database ──────────────────────────
POSTGRES_USER=${GEN_POSTGRES_USER}
POSTGRES_PASSWORD=${GEN_POSTGRES_PASSWORD}
POSTGRES_DB=${GEN_POSTGRES_DB}

# Database connection (internal Docker network)
DB_HOST=db
DB_PORT=5432
DATABASE_URL=postgres://${GEN_POSTGRES_USER}:${GEN_POSTGRES_PASSWORD}@db:5432/${GEN_POSTGRES_DB}

# ──────────────────────── RabbitMQ ──────────────────────────
RABBITMQ_USER=${GEN_RABBITMQ_USER}
RABBITMQ_PASSWORD=${GEN_RABBITMQ_PASSWORD}

# Celery broker URL
CELERY_BROKER_URL=amqp://${GEN_RABBITMQ_USER}:${GEN_RABBITMQ_PASSWORD}@rabbitmq:5672//

# ──────────────────────── Redis ─────────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=1
REDIS_PASSWORD=${GEN_REDIS_PASSWORD}

# ──────────────────────── OpenSearch ────────────────────────
OPENSEARCH_URL=http://opensearch:9200
OPENSEARCH_PASSWORD=${GEN_OPENSEARCH_PASSWORD}

# ──────────────────────── Django ────────────────────────────
DJANGO_SECRET_KEY=${GEN_DJANGO_SECRET_KEY}
DEBUG=false

# Allowed hosts (add your domain)
ALLOWED_HOSTS=${env_name}.${domain},www.${env_name}.${domain}

# ──────────────────────── Jaeger Tracing ────────────────────
JAEGER_HOST=jaeger
JAEGER_PORT=4317

# ──────────────────────── Basic Auth ────────────────────────
# For auxiliary services (Flower, Grafana, etc.)
BASIC_AUTH_USER=${GEN_BASIC_AUTH_USER}
BASIC_AUTH_PASSWORD=${GEN_BASIC_AUTH_PASSWORD}
BASIC_AUTH_HASH=${GEN_BASIC_AUTH_HASH}

# ──────────────────────── Service URLs ──────────────────────
# Public URLs for services (set by Coolify)
SERVICE_URL_NGINX=https://${env_name}.${domain}
SERVICE_FQDN_NGINX=${env_name}.${domain}

# ──────────────────────── Application Secrets ───────────────
# Add your application-specific secrets below
# GEMI_API_KEY=your_key_here
# CLERK_PUBLISHABLE_KEY=your_key_here
# AWS_ACCESS_KEY_ID=your_key_here
# AWS_SECRET_ACCESS_KEY=your_key_here

EOF

    echo -e "${SEC_GREEN}✓ Secrets saved to $env_file${SEC_NC}"
    
    # Create a summary file (without actual passwords)
    local summary_file="${PROJECT_ROOT}/.env_files/.env.${env_name}.summary"
    cat > "$summary_file" << EOF
# Environment Summary: ${env_name}
# Generated: ${timestamp}
# ============================================

Database:
  - User: ${GEN_POSTGRES_USER}
  - Database: ${GEN_POSTGRES_DB}
  - Password length: ${#GEN_POSTGRES_PASSWORD} characters

RabbitMQ:
  - User: ${GEN_RABBITMQ_USER}
  - Password length: ${#GEN_RABBITMQ_PASSWORD} characters

Redis:
  - Password length: ${#GEN_REDIS_PASSWORD} characters

OpenSearch:
  - Password length: ${#GEN_OPENSEARCH_PASSWORD} characters

Basic Auth:
  - Username: ${GEN_BASIC_AUTH_USER}
  - Password length: ${#GEN_BASIC_AUTH_PASSWORD} characters
  - Password: ${GEN_BASIC_AUTH_PASSWORD}
  - Hash: ${GEN_BASIC_AUTH_HASH}

Django:
  - Secret key length: ${#GEN_DJANGO_SECRET_KEY} characters

Full credentials are in: $env_file
EOF

    echo -e "${SEC_GREEN}✓ Summary saved to $summary_file${SEC_NC}"
    
    return 0
}

# Check if secrets already exist for an environment
check_existing_secrets() {
    local env_name="$1"
    local env_file="${PROJECT_ROOT}/.env_files/.env.${env_name}"
    
    if [[ -f "$env_file" ]]; then
        return 0  # Secrets exist
    else
        return 1  # Secrets don't exist
    fi
}

# Load existing secrets from environment file
load_existing_secrets() {
    local env_name="$1"
    local env_file="${PROJECT_ROOT}/.env_files/.env.${env_name}"
    
    if [[ ! -f "$env_file" ]]; then
        echo -e "${SEC_RED}ERROR: Environment file not found: $env_file${SEC_NC}"
        return 1
    fi
    
    # Source the environment file
    set -a
    source "$env_file"
    set +a
    
    echo -e "${SEC_GREEN}✓ Loaded existing secrets from $env_file${SEC_NC}"
    return 0
}
