#!/usr/bin/env bash
# Cloudflare DNS management functions

# Colors for output
CF_GREEN='\033[0;32m'
CF_YELLOW='\033[1;33m'
CF_RED='\033[0;31m'
CF_BLUE='\033[0;34m'
CF_NC='\033[0m' # No Color

# Check if Cloudflare credentials are configured
cf_check_credentials() {
    if [[ -z "$CLOUDFLARE_API_TOKEN" ]]; then
        echo -e "${CF_RED}ERROR: CLOUDFLARE_API_TOKEN not set${CF_NC}"
        return 1
    fi
    
    if [[ -z "$CLOUDFLARE_ZONE_ID" ]]; then
        echo -e "${CF_RED}ERROR: CLOUDFLARE_ZONE_ID not set${CF_NC}"
        return 1
    fi
    
    # Strip quotes and whitespace from credentials
    CLOUDFLARE_API_TOKEN=$(echo "$CLOUDFLARE_API_TOKEN" | tr -d '"' | tr -d "'" | xargs)
    CLOUDFLARE_ZONE_ID=$(echo "$CLOUDFLARE_ZONE_ID" | tr -d '"' | tr -d "'" | xargs)
    
    # Debug: Show first 10 chars of token (for troubleshooting)
    local token_preview="${CLOUDFLARE_API_TOKEN:0:10}"
    echo -e "${CF_BLUE}→ Using API token: ${token_preview}...${CF_NC}"
    echo -e "${CF_BLUE}→ Zone ID: ${CLOUDFLARE_ZONE_ID}${CF_NC}"
    
    return 0
}

# Test Cloudflare API connection
cf_test_connection() {
    echo -e "${CF_BLUE}→ Testing API connection...${CF_NC}"
    
    local response
    response=$(curl -s -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
        -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
        -H "Content-Type: application/json")
    
    local success=$(echo "$response" | jq -r '.success // false')
    
    if [[ "$success" != "true" ]]; then
        echo -e "${CF_RED}ERROR: Cloudflare API authentication failed${CF_NC}"
        echo "Response: $response"
        echo ""
        echo -e "${CF_YELLOW}Troubleshooting tips:${CF_NC}"
        echo "1. Verify your token at: https://dash.cloudflare.com/profile/api-tokens"
        echo "2. Ensure token has 'Zone.DNS' edit permissions"
        echo "3. Check if token is expired"
        echo "4. Token should be in format: xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        return 1
    fi
    
    echo -e "${CF_GREEN}✓ Cloudflare API connection verified${CF_NC}"
    return 0
}

# List all DNS records for the zone
cf_list_records() {
    local response
    response=$(curl -s -X GET \
        "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records" \
        -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
        -H "Content-Type: application/json")
    
    echo "$response"
}

# Get DNS record by name
cf_get_record() {
    local record_name="$1"
    
    local response
    response=$(curl -s -X GET \
        "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records?name=$record_name" \
        -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
        -H "Content-Type: application/json")
    
    echo "$response"
}

# Create A record
cf_create_a_record() {
    local name="$1"
    local ip="$2"
    local proxied="${3:-false}"
    local ttl="${4:-1}"
    
    local payload=$(jq -n \
        --arg type "A" \
        --arg name "$name" \
        --arg content "$ip" \
        --argjson proxied "$proxied" \
        --argjson ttl "$ttl" \
        '{type: $type, name: $name, content: $content, proxied: $proxied, ttl: $ttl}')
    
    local response
    response=$(curl -s -X POST \
        "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records" \
        -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
        -H "Content-Type: application/json" \
        --data "$payload")
    
    local success=$(echo "$response" | jq -r '.success // false')
    
    if [[ "$success" == "true" ]]; then
        echo -e "${CF_GREEN}✓ Created A record: $name → $ip${CF_NC}"
        return 0
    else
        local errors=$(echo "$response" | jq -r '.errors[]?.message // "Unknown error"')
        echo -e "${CF_RED}✗ Failed to create A record: $name${CF_NC}"
        echo "  Error: $errors"
        return 1
    fi
}

# Create CNAME record
cf_create_cname_record() {
    local name="$1"
    local target="$2"
    local proxied="${3:-false}"
    local ttl="${4:-1}"
    
    local payload=$(jq -n \
        --arg type "CNAME" \
        --arg name "$name" \
        --arg content "$target" \
        --argjson proxied "$proxied" \
        --argjson ttl "$ttl" \
        '{type: $type, name: $name, content: $content, proxied: $proxied, ttl: $ttl}')
    
    local response
    response=$(curl -s -X POST \
        "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records" \
        -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
        -H "Content-Type: application/json" \
        --data "$payload")
    
    local success=$(echo "$response" | jq -r '.success // false')
    
    if [[ "$success" == "true" ]]; then
        echo -e "${CF_GREEN}✓ Created CNAME: $name → $target${CF_NC}"
        return 0
    else
        local errors=$(echo "$response" | jq -r '.errors[]?.message // "Unknown error"')
        echo -e "${CF_RED}✗ Failed to create CNAME: $name${CF_NC}"
        echo "  Error: $errors"
        return 1
    fi
}

# Update existing DNS record
cf_update_record() {
    local record_id="$1"
    local record_type="$2"
    local name="$3"
    local content="$4"
    local proxied="${5:-false}"
    local ttl="${6:-1}"
    
    local payload=$(jq -n \
        --arg type "$record_type" \
        --arg name "$name" \
        --arg content "$content" \
        --argjson proxied "$proxied" \
        --argjson ttl "$ttl" \
        '{type: $type, name: $name, content: $content, proxied: $proxied, ttl: $ttl}')
    
    local response
    response=$(curl -s -X PUT \
        "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records/$record_id" \
        -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
        -H "Content-Type: application/json" \
        --data "$payload")
    
    local success=$(echo "$response" | jq -r '.success // false')
    
    if [[ "$success" == "true" ]]; then
        echo -e "${CF_YELLOW}↻ Updated record: $name → $content${CF_NC}"
        return 0
    else
        local errors=$(echo "$response" | jq -r '.errors[]?.message // "Unknown error"')
        echo -e "${CF_RED}✗ Failed to update record: $name${CF_NC}"
        echo "  Error: $errors"
        return 1
    fi
}

# Delete DNS record
cf_delete_record() {
    local record_id="$1"
    local record_name="$2"
    
    local response
    response=$(curl -s -X DELETE \
        "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records/$record_id" \
        -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
        -H "Content-Type: application/json")
    
    local success=$(echo "$response" | jq -r '.success // false')
    
    if [[ "$success" == "true" ]]; then
        echo -e "${CF_GREEN}✓ Deleted record: $record_name${CF_NC}"
        return 0
    else
        local errors=$(echo "$response" | jq -r '.errors[]?.message // "Unknown error"')
        echo -e "${CF_RED}✗ Failed to delete record: $record_name${CF_NC}"
        echo "  Error: $errors"
        return 1
    fi
}

# Create or update A record
cf_upsert_a_record() {
    local name="$1"
    local ip="$2"
    local proxied="${3:-false}"
    local ttl="${4:-1}"
    
    # Check if record exists
    local existing_response
    existing_response=$(cf_get_record "$name")
    
    local result_count=$(echo "$existing_response" | jq -r '.result | length')
    
    if [[ "$result_count" -gt 0 ]]; then
        # Record exists, check if update is needed
        local record_id=$(echo "$existing_response" | jq -r '.result[0].id')
        local current_content=$(echo "$existing_response" | jq -r '.result[0].content')
        local current_proxied=$(echo "$existing_response" | jq -r '.result[0].proxied')
        
        if [[ "$current_content" == "$ip" ]] && [[ "$current_proxied" == "$proxied" ]]; then
            echo -e "${CF_BLUE}→ A record already correct: $name → $ip (proxied: $proxied)${CF_NC}"
            return 0
        else
            echo -e "${CF_BLUE}→ Updating A record: $name (proxied: $current_proxied → $proxied)${CF_NC}"
            cf_update_record "$record_id" "A" "$name" "$ip" "$proxied" "$ttl"
        fi
    else
        # Record doesn't exist, create it
        cf_create_a_record "$name" "$ip" "$proxied" "$ttl"
    fi
}

# Create or update CNAME record
cf_upsert_cname_record() {
    local name="$1"
    local target="$2"
    local proxied="${3:-false}"
    local ttl="${4:-1}"
    
    # Check if record exists
    local existing_response
    existing_response=$(cf_get_record "$name")
    
    local result_count=$(echo "$existing_response" | jq -r '.result | length')
    
    if [[ "$result_count" -gt 0 ]]; then
        # Record exists, check if update is needed
        local record_id=$(echo "$existing_response" | jq -r '.result[0].id')
        local current_content=$(echo "$existing_response" | jq -r '.result[0].content')
        local current_proxied=$(echo "$existing_response" | jq -r '.result[0].proxied')
        
        if [[ "$current_content" == "$target" ]] && [[ "$current_proxied" == "$proxied" ]]; then
            echo -e "${CF_BLUE}→ CNAME already correct: $name → $target (proxied: $proxied)${CF_NC}"
            return 0
        else
            echo -e "${CF_BLUE}→ Updating CNAME: $name (proxied: $current_proxied → $proxied)${CF_NC}"
            cf_update_record "$record_id" "CNAME" "$name" "$target" "$proxied" "$ttl"
        fi
    else
        # Record doesn't exist, create it
        cf_create_cname_record "$name" "$target" "$proxied" "$ttl"
    fi
}

# Setup environment DNS records
cf_setup_environment_dns() {
    local env_name="$1"
    local server_ip="$2"
    local domain="$3"
    local services="$4"
    local pattern="$5"
    local proxied="${6:-false}"
    local ttl="${7:-1}"
    
    local main_domain="${env_name}.${domain}"
    local dns_records=()
    
    echo -e "\n${CF_BLUE}🌐 Setting up DNS records for environment: $env_name${CF_NC}"
    echo "   Domain: $domain"
    echo "   Server IP: $server_ip"
    echo "   Pattern: $pattern"
    echo ""
    
    # Create main A record
    cf_upsert_a_record "$main_domain" "$server_ip" "$proxied" "$ttl"
    dns_records+=("{\"type\":\"A\",\"name\":\"$main_domain\",\"content\":\"$server_ip\"}")
    
    # Create CNAME records for each service
    for service in $services; do
        local subdomain
        if [[ "$pattern" == "env-service" ]]; then
            subdomain="${env_name}-${service}.${domain}"
        else
            subdomain="${service}-${env_name}.${domain}"
        fi
        
        cf_upsert_cname_record "$subdomain" "$main_domain" "$proxied" "$ttl"
        dns_records+=("{\"type\":\"CNAME\",\"name\":\"$subdomain\",\"content\":\"$main_domain\"}")
    done
    
    # Save DNS records to JSON file
    local dns_json="[$(IFS=,; echo "${dns_records[*]}")]"
    echo "$dns_json" | jq '.' > "${PROJECT_ROOT}/coolify/dns-records.${env_name}.json"
    
    echo -e "\n${CF_GREEN}✓ DNS setup complete. Records saved to coolify/dns-records.${env_name}.json${CF_NC}"
}
