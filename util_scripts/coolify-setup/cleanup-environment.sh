#!/usr/bin/env bash
# Coolify Environment Cleanup Script
# Removes DNS records and archives secrets

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

# Default values
DRY_RUN=false
SKIP_DNS=false
SKIP_SECRETS=false
CONFIG_FILE="${PROJECT_ROOT}/.env.coolify-config"

# Usage information
usage() {
    cat << EOF
${BOLD}Coolify Environment Cleanup${NC}

${CYAN}Usage:${NC}
  ./cleanup-environment.sh ENVIRONMENT [OPTIONS]

${CYAN}Arguments:${NC}
  ENVIRONMENT          Environment name to cleanup (e.g., preview, dev, pr-12345)

${CYAN}Options:${NC}
  --no-dns             Skip DNS record deletion (only archive secrets)
  --no-secrets         Skip secret archival (only delete DNS)
  --dry-run            Show what would be done without making changes
  -h, --help           Show this help message

${CYAN}Examples:${NC}
  # Remove all resources for an environment
  ./cleanup-environment.sh pr-12345

  # Dry run to see what would be deleted
  ./cleanup-environment.sh preview --dry-run

  # Only remove DNS records
  ./cleanup-environment.sh dev --no-secrets

${CYAN}What This Does:${NC}
  1. Deletes DNS records from Cloudflare (A + CNAME records)
  2. Archives environment secrets to .env_files/archive/
  3. Archives generated files (labels, guides) to coolify/archive/
  4. Provides instructions for Coolify cleanup

${CYAN}Note:${NC}
  This script does NOT delete resources from Coolify - you must do that manually
  in the Coolify dashboard.

EOF
    exit 0
}

# Print formatted header
print_header() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║   Coolify Environment Cleanup: $1${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
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

# Load configuration
load_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        error "Config file not found: $CONFIG_FILE"
    fi
    
    set -a
    source "$CONFIG_FILE"
    set +a
    
    info "✓ Configuration loaded"
}

# Cleanup DNS records
cleanup_dns() {
    local env_name="$1"
    local dns_file="${PROJECT_ROOT}/coolify/dns-records.${env_name}.json"
    
    echo -e "\n${BLUE}🌐 Cleaning up DNS records...${NC}\n"
    
    # Check if DNS records file exists
    if [[ ! -f "$dns_file" ]]; then
        warning "DNS records file not found: $dns_file"
        warning "Will attempt to find and delete records by name pattern"
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY RUN] Would delete DNS records:"
        info "  • ${env_name}.${CLOUDFLARE_DOMAIN}"
        for service in ${EXPOSED_SERVICES}; do
            if [[ "${SUBDOMAIN_PATTERN}" == "env-service" ]]; then
                info "  • ${env_name}-${service}.${CLOUDFLARE_DOMAIN}"
            else
                info "  • ${service}-${env_name}.${CLOUDFLARE_DOMAIN}"
            fi
        done
        return
    fi
    
    # Delete main A record
    local main_domain="${env_name}.${CLOUDFLARE_DOMAIN}"
    local response=$(cf_get_record "$main_domain")
    local result_count=$(echo "$response" | jq -r '.result | length')
    
    if [[ "$result_count" -gt 0 ]]; then
        local record_id=$(echo "$response" | jq -r '.result[0].id')
        cf_delete_record "$record_id" "$main_domain"
    else
        warning "Main A record not found: $main_domain"
    fi
    
    # Delete CNAME records for each service
    for service in ${EXPOSED_SERVICES}; do
        local subdomain
        if [[ "${SUBDOMAIN_PATTERN}" == "env-service" ]]; then
            subdomain="${env_name}-${service}.${CLOUDFLARE_DOMAIN}"
        else
            subdomain="${service}-${env_name}.${CLOUDFLARE_DOMAIN}"
        fi
        
        response=$(cf_get_record "$subdomain")
        result_count=$(echo "$response" | jq -r '.result | length')
        
        if [[ "$result_count" -gt 0 ]]; then
            local record_id=$(echo "$response" | jq -r '.result[0].id')
            cf_delete_record "$record_id" "$subdomain"
        else
            warning "CNAME record not found: $subdomain"
        fi
    done
    
    echo -e "\n${GREEN}✓ DNS cleanup complete${NC}"
}

# Archive secrets
archive_secrets() {
    local env_name="$1"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local archive_dir="${PROJECT_ROOT}/.env_files/archive/${env_name}"
    
    echo -e "\n${BLUE}📦 Archiving secrets...${NC}\n"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY RUN] Would archive secrets to: ${archive_dir}"
        return
    fi
    
    # Create archive directory
    mkdir -p "$archive_dir"
    
    # Archive env file
    if [[ -f "${PROJECT_ROOT}/.env_files/.env.${env_name}" ]]; then
        cp "${PROJECT_ROOT}/.env_files/.env.${env_name}" "${archive_dir}/.env.${env_name}.${timestamp}"
        echo -e "${GREEN}✓ Archived: .env.${env_name}${NC}"
        rm "${PROJECT_ROOT}/.env_files/.env.${env_name}"
        echo -e "${GREEN}✓ Deleted: .env.${env_name}${NC}"
    fi
    
    # Archive summary file
    if [[ -f "${PROJECT_ROOT}/.env_files/.env.${env_name}.summary" ]]; then
        cp "${PROJECT_ROOT}/.env_files/.env.${env_name}.summary" "${archive_dir}/.env.${env_name}.summary.${timestamp}"
        rm "${PROJECT_ROOT}/.env_files/.env.${env_name}.summary"
        echo -e "${GREEN}✓ Archived and deleted: .env.${env_name}.summary${NC}"
    fi
    
    echo -e "\n${GREEN}✓ Secrets archived to: ${archive_dir}${NC}"
}

# Archive generated files
archive_generated_files() {
    local env_name="$1"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local archive_dir="${PROJECT_ROOT}/coolify/archive/${env_name}"
    
    echo -e "\n${BLUE}📦 Archiving generated files...${NC}\n"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY RUN] Would archive generated files to: ${archive_dir}"
        return
    fi
    
    # Create archive directory
    mkdir -p "$archive_dir"
    
    # Archive DNS records
    if [[ -f "${PROJECT_ROOT}/coolify/dns-records.${env_name}.json" ]]; then
        cp "${PROJECT_ROOT}/coolify/dns-records.${env_name}.json" "${archive_dir}/dns-records.${env_name}.${timestamp}.json"
        rm "${PROJECT_ROOT}/coolify/dns-records.${env_name}.json"
        echo -e "${GREEN}✓ Archived and deleted: dns-records.${env_name}.json${NC}"
    fi
    
    # Archive labels
    if [[ -f "${PROJECT_ROOT}/coolify/labels.${env_name}.yml" ]]; then
        cp "${PROJECT_ROOT}/coolify/labels.${env_name}.yml" "${archive_dir}/labels.${env_name}.${timestamp}.yml"
        rm "${PROJECT_ROOT}/coolify/labels.${env_name}.yml"
        echo -e "${GREEN}✓ Archived and deleted: labels.${env_name}.yml${NC}"
    fi
    
    # Archive deployment guide
    if [[ -f "${PROJECT_ROOT}/coolify/deployment-guide.${env_name}.md" ]]; then
        cp "${PROJECT_ROOT}/coolify/deployment-guide.${env_name}.md" "${archive_dir}/deployment-guide.${env_name}.${timestamp}.md"
        rm "${PROJECT_ROOT}/coolify/deployment-guide.${env_name}.md"
        echo -e "${GREEN}✓ Archived and deleted: deployment-guide.${env_name}.md${NC}"
    fi
    
    echo -e "\n${GREEN}✓ Files archived to: ${archive_dir}${NC}"
}

# Main cleanup function
cleanup_environment() {
    local env_name="$1"
    
    print_header "$env_name"
    
    # Confirmation prompt
    if [[ "$DRY_RUN" != "true" ]]; then
        echo -e "${YELLOW}⚠️  This will:${NC}"
        [[ "$SKIP_DNS" != "true" ]] && echo "   • Delete DNS records from Cloudflare"
        [[ "$SKIP_SECRETS" != "true" ]] && echo "   • Archive and remove local secrets"
        echo "   • Archive generated configuration files"
        echo ""
        echo -e "${YELLOW}⚠️  This will NOT:${NC}"
        echo "   • Delete containers or volumes from Coolify"
        echo "   • Delete data from databases"
        echo ""
        read -p "Are you sure you want to cleanup environment '$env_name'? (yes/no): " confirm
        
        if [[ "$confirm" != "yes" ]]; then
            echo "Cleanup cancelled."
            exit 0
        fi
    else
        warning "DRY RUN MODE - No changes will be made"
    fi
    
    # Step 1: Cleanup DNS
    if [[ "$SKIP_DNS" != "true" ]]; then
        cf_check_credentials || error "Cloudflare credentials invalid"
        cleanup_dns "$env_name"
    else
        info "Skipping DNS cleanup (--no-dns flag)"
    fi
    
    # Step 2: Archive secrets
    if [[ "$SKIP_SECRETS" != "true" ]]; then
        archive_secrets "$env_name"
    else
        info "Skipping secret archival (--no-secrets flag)"
    fi
    
    # Step 3: Archive generated files
    archive_generated_files "$env_name"
    
    # Success summary
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║   ✅ Environment '${env_name}' cleanup complete!${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    if [[ "$DRY_RUN" == "true" ]]; then
        info "This was a dry run. No changes were made."
        info "Run without --dry-run to apply changes."
        return
    fi
    
    echo -e "${CYAN}📋 Next Steps - Coolify Dashboard:${NC}"
    echo "   1. Log in to your Coolify dashboard"
    echo "   2. Navigate to the '${env_name}' project"
    echo "   3. Stop all services"
    echo "   4. Delete the project"
    echo "   5. (Optional) Delete associated volumes if you don't need the data"
    echo ""
    
    echo -e "${CYAN}💡 Archived Files:${NC}"
    echo "   • Secrets: .env_files/archive/${env_name}/"
    echo "   • Config:  coolify/archive/${env_name}/"
    echo ""
    
    echo -e "${CYAN}⚠️  Important:${NC}"
    echo "   • DNS changes may take a few minutes to propagate"
    echo "   • Archived secrets contain sensitive data - keep them secure"
    echo "   • To restore, you can re-run: ./setup-environment.sh ${env_name}"
    echo ""
}

# Parse arguments
ENV_NAME=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
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
        -*)
            error "Unknown option: $1"
            ;;
        *)
            if [[ -z "$ENV_NAME" ]]; then
                ENV_NAME="$1"
            else
                error "Multiple environment names provided"
            fi
            shift
            ;;
    esac
done

# Validate environment name
if [[ -z "$ENV_NAME" ]]; then
    error "Environment name required\n\nUsage: ./cleanup-environment.sh ENVIRONMENT [OPTIONS]\nRun with --help for more information"
fi

# Main execution
main() {
    load_config
    cleanup_environment "$ENV_NAME"
}

main
