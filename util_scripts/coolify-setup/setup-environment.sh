#!/usr/bin/env bash
# Coolify Environment Setup Script
# Creates DNS records, generates secrets, and prepares deployment configuration

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Export PROJECT_ROOT so it's available in sourced libraries
export PROJECT_ROOT

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Load library functions
source "${SCRIPT_DIR}/aux_lib/cloudflare.sh"
source "${SCRIPT_DIR}/aux_lib/secrets.sh"
source "${SCRIPT_DIR}/aux_lib/labels.sh"

# Default values
DRY_RUN=false
FORCE=false
SKIP_DNS=false
SKIP_SECRETS=false
CONFIG_FILE="${PROJECT_ROOT}/.env.coolify-config"

# Set default for Cloudflare proxy (will be overridden by config file if set)
CLOUDFLARE_PROXIED="${CLOUDFLARE_PROXIED:-true}"

# Usage information
usage() {
    cat << EOF
${BOLD}Coolify Environment Setup${NC}

${CYAN}Usage:${NC}
  ./setup-environment.sh ENVIRONMENT [OPTIONS]

${CYAN}Arguments:${NC}
  ENVIRONMENT          Environment name (e.g., preview, dev, pr-12345)

${CYAN}Options:${NC}
  --server-ip IP       Server IP address (overrides config)
  --domain DOMAIN      Base domain (overrides config, default: crati.co)
  --cloudflare-token TOKEN  Cloudflare API token (overrides config)
  --cloudflare-zone ZONE    Cloudflare Zone ID (overrides config)
  --no-dns             Skip DNS record creation (only generate secrets)
  --no-secrets         Skip secret generation (only create DNS)
  --dry-run            Show what would be done without making changes
  --force              Overwrite existing configuration
  -h, --help           Show this help message

${CYAN}Examples:${NC}
  # Use all defaults from config file
  ./setup-environment.sh preview

  # Override server IP
  ./setup-environment.sh dev --server-ip=5.6.7.8

  # Create PR environment with custom domain
  ./setup-environment.sh pr-12345 --domain=staging.crati.co

  # Dry run to see what would be created
  ./setup-environment.sh preview --dry-run

  # Regenerate secrets without touching DNS
  ./setup-environment.sh preview --no-dns --force

${CYAN}Configuration:${NC}
  Config file: ${CONFIG_FILE}
  Copy .env.coolify-config.example to .env.coolify-config and configure

EOF
    exit 0
}

# Print formatted header
print_header() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║   Coolify Environment Setup: $1${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Print formatted section
print_section() {
    echo ""
    echo -e "${BLUE}$1${NC}"
}

# Error handler
error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
    exit 1
}

# Warning handler
warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

# Info handler
info() {
    echo -e "${CYAN}$1${NC}"
}

# Check prerequisites
check_prerequisites() {
    local missing_tools=()
    
    for tool in curl jq openssl dig; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        error "Missing required tools: ${missing_tools[*]}\nPlease install them and try again."
    fi
}

# Load configuration
load_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        warning "Config file not found: $CONFIG_FILE"
        echo "Please copy .env.coolify-config.example to .env.coolify-config and configure it."
        echo ""
        echo "Quick setup:"
        echo "  cp .env.coolify-config.example .env.coolify-config"
        echo "  vim .env.coolify-config  # Add your Cloudflare credentials"
        echo ""
        error "Configuration file missing"
    fi
    
    # Source the config file
    set -a
    source "$CONFIG_FILE"
    set +a
    
    info "✓ Configuration loaded from $CONFIG_FILE"
}

# Validate configuration
validate_config() {
    local errors=0
    
    if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]] && [[ "$SKIP_DNS" != "true" ]]; then
        error "CLOUDFLARE_API_TOKEN not set in config"
        ((errors++))
    fi
    
    if [[ -z "${CLOUDFLARE_ZONE_ID:-}" ]] && [[ "$SKIP_DNS" != "true" ]]; then
        error "CLOUDFLARE_ZONE_ID not set in config"
        ((errors++))
    fi
    
    if [[ -z "${CLOUDFLARE_DOMAIN:-}" ]]; then
        error "CLOUDFLARE_DOMAIN not set in config"
        ((errors++))
    fi
    
    if [[ -z "${SERVER_IP:-}" ]] && [[ "$SKIP_DNS" != "true" ]]; then
        error "SERVER_IP not set (provide via config or --server-ip)"
        ((errors++))
    fi
    
    if [[ $errors -gt 0 ]]; then
        exit 1
    fi
    
    info "✓ Configuration validated"
}

# Main setup function
setup_environment() {
    local env_name="$1"
    
    print_header "$env_name"
    
    # Configuration summary
    echo -e "${CYAN}📋 Configuration Summary:${NC}"
    echo "   Environment:      $env_name"
    echo "   Domain:           ${CLOUDFLARE_DOMAIN}"
    echo "   Server IP:        ${SERVER_IP}"
    echo "   Services:         ${EXPOSED_SERVICES}"
    echo "   Pattern:          ${SUBDOMAIN_PATTERN} (e.g., jaeger-${env_name}.${CLOUDFLARE_DOMAIN})"
    echo "   Basic Auth:       ${ENABLE_BASIC_AUTH:-false}"
    echo "   Dry Run:          $DRY_RUN"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        warning "DRY RUN MODE - No changes will be made"
    fi
    
    # Step 1: Generate Secrets
    if [[ "$SKIP_SECRETS" != "true" ]]; then
        print_section "🔐 Step 1/4: Generating Secrets..."
        
        # Check if secrets already exist
        if check_existing_secrets "$env_name"; then
            if [[ "$FORCE" != "true" ]]; then
                warning "Secrets already exist for environment: $env_name"
                echo "   File: .env_files/.env.${env_name}"
                echo "   Use --force to regenerate"
                echo ""
                info "Skipping secret generation (using existing secrets)"
            else
                info "Force flag set - regenerating secrets"
                if [[ "$DRY_RUN" != "true" ]]; then
                    generate_environment_secrets \
                        "$env_name" \
                        "${POSTGRES_USER:-crati_user}" \
                        "${POSTGRES_DB_PATTERN/\{env\}/$env_name}" \
                        "${RABBITMQ_USER:-crati_rabbitmq}" \
                        "${BASIC_AUTH_USERNAME:-admin}" \
                        "${BASIC_AUTH_PASSWORD:-}"
                    
                    save_secrets_to_env "$env_name" "${CLOUDFLARE_DOMAIN}"
                fi
            fi
        else
            if [[ "$DRY_RUN" != "true" ]]; then
                generate_environment_secrets \
                    "$env_name" \
                    "${POSTGRES_USER:-crati_user}" \
                    "${POSTGRES_DB_PATTERN/\{env\}/$env_name}" \
                    "${RABBITMQ_USER:-crati_rabbitmq}" \
                    "${BASIC_AUTH_USERNAME:-admin}" \
                    "${BASIC_AUTH_PASSWORD:-}"
                
                save_secrets_to_env "$env_name" "${CLOUDFLARE_DOMAIN}"
            else
                info "[DRY RUN] Would generate secrets for: $env_name"
            fi
        fi
    else
        info "Skipping secret generation (--no-secrets flag)"
    fi
    
    # Step 2: Create DNS Records
    if [[ "$SKIP_DNS" != "true" ]]; then
        print_section "🌐 Step 2/4: Creating Cloudflare DNS Records..."
        
        if [[ "$DRY_RUN" != "true" ]]; then
            # Test Cloudflare connection
            cf_check_credentials || error "Cloudflare credentials invalid"
            cf_test_connection || error "Cannot connect to Cloudflare API"
            
            # Setup DNS records
            cf_setup_environment_dns \
                "$env_name" \
                "${SERVER_IP}" \
                "${CLOUDFLARE_DOMAIN}" \
                "${EXPOSED_SERVICES}" \
                "${SUBDOMAIN_PATTERN}" \
                "${CLOUDFLARE_PROXIED:-false}" \
                "${DNS_TTL:-1}"
        else
            info "[DRY RUN] Would create DNS records:"
            info "  A record: ${env_name}.${CLOUDFLARE_DOMAIN} → ${SERVER_IP}"
            for service in ${EXPOSED_SERVICES}; do
                if [[ "${SUBDOMAIN_PATTERN}" == "env-service" ]]; then
                    info "  CNAME: ${env_name}-${service}.${CLOUDFLARE_DOMAIN} → ${env_name}.${CLOUDFLARE_DOMAIN}"
                else
                    info "  CNAME: ${service}-${env_name}.${CLOUDFLARE_DOMAIN} → ${env_name}.${CLOUDFLARE_DOMAIN}"
                fi
            done
        fi
    else
        info "Skipping DNS setup (--no-dns flag)"
    fi
    
    # Step 3: Generate Coolify Labels
    print_section "🏷️  Step 3/4: Generating Coolify Labels..."
    
    if [[ "$DRY_RUN" != "true" ]]; then
        generate_labels_file \
            "$env_name" \
            "${CLOUDFLARE_DOMAIN}" \
            "${EXPOSED_SERVICES}" \
            "${SUBDOMAIN_PATTERN}" \
            "${ENABLE_BASIC_AUTH:-false}"
    else
        info "[DRY RUN] Would generate labels file: coolify/labels.${env_name}.yml"
    fi
    
    # Step 4: Generate Deployment Guide
    print_section "📝 Step 4/4: Creating Deployment Guide..."
    
    if [[ "$DRY_RUN" != "true" ]]; then
        generate_deployment_guide \
            "$env_name" \
            "${CLOUDFLARE_DOMAIN}" \
            "${EXPOSED_SERVICES}" \
            "${SUBDOMAIN_PATTERN}"
    else
        info "[DRY RUN] Would generate deployment guide: coolify/deployment-guide.${env_name}.md"
    fi
    
    # Success summary
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║   ✅ Environment '${env_name}' setup complete!${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    if [[ "$DRY_RUN" == "true" ]]; then
        info "This was a dry run. No changes were made."
        info "Run without --dry-run to apply changes."
        return
    fi
    
    echo -e "${CYAN}📂 Generated Files:${NC}"
    [[ "$SKIP_SECRETS" != "true" ]] && echo "   • .env_files/.env.${env_name} (secrets)"
    [[ "$SKIP_SECRETS" != "true" ]] && echo "   • .env_files/.env.${env_name}.summary (summary)"
    [[ "$SKIP_DNS" != "true" ]] && echo "   • coolify/dns-records.${env_name}.json (DNS audit)"
    echo "   • coolify/labels.${env_name}.yml (Traefik config)"
    echo "   • coolify/deployment-guide.${env_name}.md (instructions)"
    echo ""
    
    echo -e "${CYAN}🚀 Next Steps:${NC}"
    echo "   1. Review deployment guide: ${GREEN}coolify/deployment-guide.${env_name}.md${NC}"
    echo "   2. Upload docker-compose.prod.yml to Coolify"
    echo "   3. Add environment variables from .env_files/.env.${env_name}"
    echo "   4. Configure service domains in Coolify"
    echo "   5. Deploy!"
    echo ""
    
    echo -e "${CYAN}🌐 Service URLs:${NC}"
    echo "   • Main app:    https://${env_name}.${CLOUDFLARE_DOMAIN}"
    
    for service in ${EXPOSED_SERVICES}; do
        local subdomain
        if [[ "${SUBDOMAIN_PATTERN}" == "env-service" ]]; then
            subdomain="${env_name}-${service}.${CLOUDFLARE_DOMAIN}"
        else
            subdomain="${service}-${env_name}.${CLOUDFLARE_DOMAIN}"
        fi
        local service_display=$(echo "$service" | tr '_' ' ' | sed 's/\b\(.\)/\u\1/g')
        echo "   • ${service_display}: https://${subdomain}"
    done
    
    echo ""
    echo -e "${CYAN}💡 Tips:${NC}"
    echo "   • DNS propagation may take 1-5 minutes"
    echo "   • SSL certificates provision automatically via Let's Encrypt"
    echo "   • To update IP: ./setup-environment.sh ${env_name} --server-ip=NEW_IP"
    echo "   • To cleanup: ./cleanup-environment.sh ${env_name}"
    echo ""
}

# Parse arguments
ENV_NAME=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            ;;
        --server-ip)
            SERVER_IP="$2"
            shift 2
            ;;
        --domain)
            CLOUDFLARE_DOMAIN="$2"
            shift 2
            ;;
        --cloudflare-token)
            CLOUDFLARE_API_TOKEN="$2"
            shift 2
            ;;
        --cloudflare-zone)
            CLOUDFLARE_ZONE_ID="$2"
            shift 2
            ;;
        --no-dns)
            SKIP_DNS=true
            shift
            ;;
        --no-secrets)
            SKIP_SECRETS=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -*)
            error "Unknown option: $1"
            ;;
        *)
            if [[ -z "$ENV_NAME" ]]; then
                ENV_NAME="$1"
            else
                error "Multiple environment names provided: $ENV_NAME and $1"
            fi
            shift
            ;;
    esac
done

# Validate environment name
if [[ -z "$ENV_NAME" ]]; then
    error "Environment name required\n\nUsage: ./setup-environment.sh ENVIRONMENT [OPTIONS]\nRun with --help for more information"
fi

# Validate environment name format
if [[ ! "$ENV_NAME" =~ ^[a-z0-9-]+$ ]]; then
    error "Invalid environment name: $ENV_NAME\nMust contain only lowercase letters, numbers, and hyphens"
fi

# Main execution
main() {
    check_prerequisites
    load_config
    validate_config
    setup_environment "$ENV_NAME"
}

main
