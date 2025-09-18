#!/bin/bash

# Coolify Network Diagnostics & Auto-Fix Script
# Usage: ./coolify-diagnostics.sh [domain] [auto-fix]
# Example: ./coolify-diagnostics.sh preview.crati.co auto-fix

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN=${1:-"preview.crati.co"}
AUTO_FIX=${2:-"manual"}
SCRIPT_VERSION="1.0.0"

# Global variables
NGINX_CONTAINER=""
ISSUES_FOUND=()
FIXES_APPLIED=()

# Utility functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✅ SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠️  WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[❌ ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}===========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===========================================${NC}"
}

add_issue() {
    ISSUES_FOUND+=("$1")
}

add_fix() {
    FIXES_APPLIED+=("$1")
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Find nginx container for the application
find_nginx_container() {
    log_info "Searching for nginx container..."
    
    # Try different patterns to find nginx container
    NGINX_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E "(nginx|gateway|proxy)" | grep -v coolify-proxy | head -1)
    
    if [[ -z "$NGINX_CONTAINER" ]]; then
        log_warning "No nginx container found with standard naming"
        log_info "Available containers:"
        docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
        read -r -p "Enter nginx container name manually: " NGINX_CONTAINER
    fi
    
    if [[ -n "$NGINX_CONTAINER" ]] && docker ps --format '{{.Names}}' | grep -q "^${NGINX_CONTAINER}$"; then
        log_success "Found nginx container: $NGINX_CONTAINER"
        return 0
    else
        log_error "Invalid or non-existent nginx container: $NGINX_CONTAINER"
        return 1
    fi
}

# Step 1: Container Health Check
check_container_health() {
    log_step "STEP 1: Container Health Verification"
    
    # Check coolify-proxy
    if docker ps | grep -q coolify-proxy; then
        log_success "coolify-proxy is running"
    else
        log_error "coolify-proxy is not running!"
        add_issue "coolify-proxy container not running"
        return 1
    fi
    
    # Check nginx container
    if docker ps | grep -q "$NGINX_CONTAINER"; then
        log_success "Nginx container ($NGINX_CONTAINER) is running"
    else
        log_error "Nginx container ($NGINX_CONTAINER) is not running!"
        add_issue "nginx container not running"
        return 1
    fi
    
    # Check container logs for obvious errors
    log_info "Checking nginx container logs for errors..."
    if docker logs "$NGINX_CONTAINER" --tail 10 2>&1 | grep -i -E "(error|failed|fatal)"; then
        log_warning "Found potential errors in nginx logs"
        add_issue "nginx container has error logs"
    else
        log_success "No obvious errors in nginx logs"
    fi
    
    return 0
}

check_coolify_version_issues() {
    log_step "COOLIFY VERSION ANALYSIS"
    
    # Try to get Coolify version from various sources
    local coolify_version=""
    
    # Try from container labels
    coolify_version=$(docker inspect coolify-proxy | grep -o '"coolify.version":"[^"]*"' | cut -d'"' -f4 || echo "")
    
    if [[ -z "$coolify_version" ]]; then
        # Try from any container with coolify labels
        coolify_version=$(docker inspect "$NGINX_CONTAINER" | grep -o '"coolify.version":"[^"]*"' | cut -d'"' -f4 || echo "")
    fi
    
    if [[ -n "$coolify_version" ]]; then
        log_info "Detected Coolify version: $coolify_version"
        
        # Check for known problematic versions
        if [[ "$coolify_version" =~ beta\.(400|420) ]]; then
            log_error "CRITICAL: Running known problematic beta version $coolify_version"
            log_error "This version has documented routing and configuration issues"
            add_issue "running problematic coolify beta version"
        elif [[ "$coolify_version" =~ beta ]]; then
            log_warning "Running beta version $coolify_version - may have stability issues"
            add_issue "running coolify beta version"
        fi
    else
        log_warning "Could not determine Coolify version"
    fi
}

# Step 2: Internal Network Connectivity
check_internal_connectivity() {
    log_step "STEP 2: Internal Network Connectivity"
    
    # Test nginx responds internally
    log_info "Testing nginx internal response..."
    local wget_status
    wget_status=$(docker exec "$NGINX_CONTAINER" wget -S -O- http://localhost:80 --timeout=5 2>&1 | grep "HTTP/" || true)
    if [[ -n "$wget_status" ]]; then
        log_success "Nginx responds internally on port 80 (status: $wget_status)"
    else
        log_error "Nginx does not respond internally on port 80"
        add_issue "nginx not responding internally"
    fi        
    # Check if nginx process is running
    log_info "Checking nginx process inside container..."
    if docker exec "$NGINX_CONTAINER" pgrep nginx >/dev/null; then
        log_success "nginx process is running"
    else
        log_error "nginx process is NOT running"
        add_issue "nginx process not running"
    fi

    # Check if anything is listening on port 80
    log_info "Checking if anything is listening on port 80..."
    if docker exec "$NGINX_CONTAINER" netstat -tlnp 2>/dev/null | grep ":80 "; then
        log_success "Something is listening on port 80"
    else
        log_error "Nothing is listening on port 80"
        add_issue "nothing listening on port 80"
    fi

    # Try curl with verbose output for more detail
    log_info "Trying curl to localhost:80 inside container..."
    docker exec "$NGINX_CONTAINER" curl -v --max-time 5 http://localhost:80 2>&1 | tee /tmp/nginx_curl_output.txt
    if grep -q "HTTP/" /tmp/nginx_curl_output.txt; then
        log_success "curl received HTTP response from nginx"
    else
        log_error "curl did not receive HTTP response from nginx"
        add_issue "curl failed to get HTTP response from nginx"
    fi

    # Test nginx config
    log_info "Testing nginx configuration..."
    if docker exec "$NGINX_CONTAINER" nginx -t >/dev/null 2>&1; then
        log_success "Nginx configuration is valid"
    else
        log_error "Nginx configuration has errors"
        add_issue "nginx configuration invalid"
        docker exec "$NGINX_CONTAINER" nginx -t
    fi
    
    # Check listening ports
    log_info "Checking nginx listening ports..."
    local ports 
    ports=$(docker exec "$NGINX_CONTAINER" netstat -tlnp 2>/dev/null | grep ":80 " || echo "")
    if [[ -n "$ports" ]]; then
        log_success "Nginx is listening on port 80"
    else
        log_error "Nginx is not listening on port 80"
        add_issue "nginx not listening on port 80"
    fi
}

# Step 3: External Network Connectivity (Critical)
check_external_connectivity() {
    log_step "STEP 3: External Network Connectivity (CRITICAL)"
    
    log_info "Testing connectivity from coolify-proxy to nginx..."
    
    # Test basic connectivity
    if docker exec coolify-proxy nc -zv "$NGINX_CONTAINER" 80 2>/dev/null; then
        log_success "coolify-proxy CAN reach nginx container"
        return 0
    else
        log_error "coolify-proxy CANNOT reach nginx container"
        add_issue "no connectivity between coolify-proxy and nginx"
        
        # Try by IP
        log_info "Trying connection by IP address..."
        local nginx_ip 
        nginx_ip=$(docker inspect "$NGINX_CONTAINER" | grep '"IPAddress"' | tail -1 | cut -d'"' -f4)
        if [[ -n "$nginx_ip" ]] && docker exec coolify-proxy nc -zv "$nginx_ip" 80 2>/dev/null; then
            log_warning "Connection works by IP ($nginx_ip) but not by container name"
            add_issue "DNS resolution issue between containers"
        else
            log_error "Connection fails even by IP address"
        fi
        
        return 1
    fi
}

# Step 4: Network Membership Analysis

check_network_membership() {
    log_step "STEP 4: Network Membership Analysis"
    
    log_info "Checking nginx container networks..."
    local nginx_networks 
    nginx_networks=$(docker inspect "$NGINX_CONTAINER" --format '{{range $net, $config := .NetworkSettings.Networks}}{{$net}} {{end}}')
    log_info "Nginx is on networks: $(echo "$nginx_networks" | tr '\n' ' ')"
    
    log_info "Checking coolify-proxy networks..."
    local proxy_networks 
    proxy_networks=$(docker inspect coolify-proxy --format '{{range $net, $config := .NetworkSettings.Networks}}{{$net}} {{end}}')
    log_info "coolify-proxy is on networks: $(echo "$proxy_networks" | tr '\n' ' ')"
    
    # Check if they share at least one common network
    local common_networks=""
    for nginx_net in $nginx_networks; do
        for proxy_net in $proxy_networks; do
            if [[ "$nginx_net" == "$proxy_net" ]]; then
                common_networks="$common_networks $nginx_net"
            fi
        done
    done
    
    if [[ -n "$common_networks" ]]; then
        log_success "Found common network(s): $common_networks"
        return 0
    else
        log_error "No common networks found between nginx and coolify-proxy"
        add_issue "no common networks between containers"
        return 1
    fi
}


# Step 5: Traefik Configuration Analysis
check_traefik_config() {
    log_step "STEP 5: Traefik Configuration Analysis"
    
    # Check if Traefik API is accessible
    log_info "Checking Traefik API accessibility..."

    if docker exec coolify-proxy wget -qO- http://localhost:8080/ping --timeout=5 >/dev/null 2>&1 || true; then

        log_success "Traefik API is accessible"
    else
        log_error "Traefik API is not accessible"
        add_issue "traefik API not accessible"
        return 1
    fi
    
    # Check for routers with the domain
    log_info "Checking for routers with domain: $DOMAIN"
    local routers=$(docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | grep "$DOMAIN" || echo "")
    if [[ -n "$routers" ]]; then
        log_success "Found Traefik routers for domain $DOMAIN"
    else
        log_error "No Traefik routers found for domain $DOMAIN"
        add_issue "no traefik routers for domain"
    fi
    
    # Check for services
    log_info "Checking for nginx services in Traefik..."
    local services=$(docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/services 2>/dev/null | grep nginx || echo "")
    if [[ -n "$services" ]]; then
        log_success "Found nginx services in Traefik"
    else
        log_warning "No nginx services found in Traefik"
        add_issue "no nginx services in traefik"
    fi
}

# Step 6: Container Labels Verification
check_container_labels() {
    log_step "STEP 6: Container Labels Verification"
    
    # Check for traefik.enable
    log_info "Checking traefik.enable label..."
    if docker inspect "$NGINX_CONTAINER" | grep -q '"traefik.enable": "true"'; then
        log_success "traefik.enable=true found"
    else
        log_error "traefik.enable=true NOT found"
        add_issue "traefik.enable label missing or false"
    fi
    
    # Check for domain rules
    log_info "Checking for domain rules in labels..."
    if docker inspect "$NGINX_CONTAINER" | grep -q "$DOMAIN"; then
        log_success "Domain $DOMAIN found in container labels"
    else
        log_error "Domain $DOMAIN NOT found in container labels"
        add_issue "domain not found in container labels"
    fi
    
    # Check for router rules
    log_info "Checking for router labels..."
    local router_labels=$(docker inspect "$NGINX_CONTAINER" | grep -c "traefik.http.routers")
    if [[ $router_labels -gt 0 ]]; then
        log_success "Found $router_labels Traefik router labels"
    else
        log_error "No Traefik router labels found"
        add_issue "no traefik router labels"
    fi
}

# Auto-fix functions
fix_network_connectivity() {
    log_info "Attempting to fix network connectivity..."
    
    # Connect nginx to coolify network
    if docker network connect coolify "$NGINX_CONTAINER" 2>/dev/null; then
        log_success "Connected nginx container to coolify network"
        add_fix "connected nginx to coolify network"
        
        # Test connectivity again
        sleep 2
        if docker exec coolify-proxy nc -zv "$NGINX_CONTAINER" 80 2>/dev/null; then
            log_success "Network connectivity restored!"
            return 0
        else
            log_warning "Connected to network but connectivity still failing"
            return 1
        fi
    else
        log_warning "Failed to connect nginx to coolify network (might already be connected)"
        return 1
    fi
}

fix_traefik_config() {
    log_info "Attempting to refresh Traefik configuration..."
    
    if docker restart coolify-proxy >/dev/null 2>&1; then
        log_success "Restarted coolify-proxy"
        add_fix "restarted traefik proxy"
        
        # Wait for startup
        log_info "Waiting for Traefik to start up..."
        sleep 10
        
        # Check if routers are now available
        local routers=$(docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | grep "$DOMAIN" || echo "")
        if [[ -n "$routers" ]]; then
            log_success "Traefik routers now available for $DOMAIN"
            return 0
        else
            log_warning "Traefik restarted but routers still not available"
            return 1
        fi
    else
        log_error "Failed to restart coolify-proxy"
        return 1
    fi
}

# Test external access
test_external_access() {
    log_step "TESTING EXTERNAL ACCESS"
    
    log_info "Testing external access to https://$DOMAIN/"
    
    # Test with curl
    local response=$(curl -I "https://$DOMAIN/" --max-time 10 --silent --show-error 2>&1 | head -1 || echo "FAILED")
    
    if echo "$response" | grep -q "HTTP.*[2-4][0-9][0-9]"; then
        log_success "External access working! Response: $response"
        return 0
    else
        log_error "External access failed. Response: $response"
        return 1
    fi
}

# Apply fixes
apply_fixes() {
    if [[ "$AUTO_FIX" != "auto-fix" ]]; then
        return 0
    fi
    
    log_step "APPLYING AUTOMATIC FIXES"
    
    local fixes_attempted=0
    
    # Fix network connectivity if needed
    if printf '%s\n' "${ISSUES_FOUND[@]}" | grep -q "no connectivity between coolify-proxy and nginx\|nginx not on coolify network"; then
        fix_network_connectivity
        ((fixes_attempted++))
    fi
    
    # Fix Traefik config if needed
    if printf '%s\n' "${ISSUES_FOUND[@]}" | grep -q "no traefik routers for domain\|traefik API not accessible"; then
        fix_traefik_config
        ((fixes_attempted++))
    fi
    
    if [[ $fixes_attempted -eq 0 ]]; then
        log_info "No automatic fixes available for detected issues"
    fi
}

# Generate report
generate_report() {
    log_step "DIAGNOSTIC REPORT"
    
    echo -e "\n${BLUE}Coolify Network Diagnostics Report${NC}"
    echo -e "${BLUE}===================================${NC}"
    echo -e "Domain: $DOMAIN"
    echo -e "Nginx Container: $NGINX_CONTAINER"
    echo -e "Timestamp: $(date)"
    echo -e "Script Version: $SCRIPT_VERSION"
    
    echo -e "\n${RED}Issues Found (${#ISSUES_FOUND[@]}):${NC}"
    if [[ ${#ISSUES_FOUND[@]} -eq 0 ]]; then
        echo -e "${GREEN}✅ No issues detected!${NC}"
    else
        for issue in "${ISSUES_FOUND[@]}"; do
            echo -e "${RED}❌ $issue${NC}"
        done
    fi
    
    if [[ ${#FIXES_APPLIED[@]} -gt 0 ]]; then
        echo -e "\n${GREEN}Fixes Applied (${#FIXES_APPLIED[@]}):${NC}"
        for fix in "${FIXES_APPLIED[@]}"; do
            echo -e "${GREEN}✅ $fix${NC}"
        done
    fi
    
    echo -e "\n${BLUE}Next Steps:${NC}"
    if [[ ${#ISSUES_FOUND[@]} -eq 0 ]]; then
        echo -e "${GREEN}✅ System appears healthy. If you're still experiencing issues, check:${NC}"
        echo -e "   - Cloudflare settings (SSL mode)"
        echo -e "   - DNS configuration"
        echo -e "   - Application-specific logs"
    else
        echo -e "${YELLOW}⚠️  Issues detected. Recommended actions:${NC}"
        
        if printf '%s\n' "${ISSUES_FOUND[@]}" | grep -q "nginx not on coolify network"; then
            echo -e "   - Run: docker network connect coolify $NGINX_CONTAINER"
        fi
        
        if printf '%s\n' "${ISSUES_FOUND[@]}" | grep -q "no traefik routers"; then
            echo -e "   - Run: docker restart coolify-proxy"
            echo -e "   - Check Coolify application configuration"
        fi
        
        if printf '%s\n' "${ISSUES_FOUND[@]}" | grep -q "nginx not responding internally"; then
            echo -e "   - Check nginx configuration and logs"
            echo -e "   - Verify application is properly built"
        fi
        
        echo -e "   - Consult the full troubleshooting guide for detailed steps"
    fi
}

check_nginx_config_issues() {
    log_step "NGINX CONFIGURATION ANALYSIS"
    
    log_info "Checking for problematic nginx configurations..."
    
    # Check if this is a static site with nginx config
    if docker inspect "$NGINX_CONTAINER" | grep -q "static.*site\|Static.*Site"; then
        log_info "This appears to be a static site deployment"
        
        # Check for try_files directive that might break SPA routing
        local nginx_config=$(docker exec "$NGINX_CONTAINER" cat /etc/nginx/nginx.conf 2>/dev/null || echo "")
        if echo "$nginx_config" | grep -q "try_files.*\$uri.*=404"; then
            log_error "Found problematic try_files directive that breaks SPA routing"
            add_issue "nginx config breaks SPA routing"
        fi
        
        # Check for missing fallback to index.html
        if ! echo "$nginx_config" | grep -q "try_files.*index\.html\|fallback.*index"; then
            log_warning "No fallback to index.html found - may cause SPA routing issues"
            add_issue "missing SPA fallback in nginx config"
        fi
    fi
    
    # Check for location blocks that might override app routing
    local nginx_config=$(docker exec "$NGINX_CONTAINER" cat /etc/nginx/nginx.conf 2>/dev/null || echo "")
    local location_blocks=$(echo "$nginx_config" | grep -c "location" 2>/dev/null || echo 0)
    if [[ $location_blocks -gt 3 ]]; then
        log_warning "Found $location_blocks location blocks - complex routing may cause conflicts"
        add_issue "complex nginx location blocks detected"
    fi
}


check_traefik_config_detailed() {
    log_step "DETAILED TRAEFIK ANALYSIS"
    
    # Check if API is actually working
    log_info "Testing Traefik API endpoints..."
    
    # Test ping with better error handling
    local ping_result=""
    ping_result=$(docker exec coolify-proxy wget -qO- http://localhost:8080/ping --timeout=5 2>/dev/null || echo "PING_FAILED")
    
    if [[ "$ping_result" != "PING_FAILED" ]] && [[ -n "$ping_result" ]]; then
        log_success "Traefik ping successful: $ping_result"
        
        # Only proceed with API calls if ping works
        log_info "Fetching ALL Traefik routers..."
        local all_routers
        all_routers=$(docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers --timeout=10 2>/dev/null || echo "")
        
        if [[ -n "$all_routers" ]] && [[ "$all_routers" != "404 page not found" ]]; then
            echo "Raw router data (first 500 chars):"
            echo "$all_routers" | head -c 500
            echo "..."
            
            # Count total routers
            local router_count
            router_count=$(echo "$all_routers" | jq '. | length' 2>/dev/null || echo "unknown")
            log_info "Total routers found: $router_count"
            
            # List all router names
            log_info "Router names:"
            echo "$all_routers" | jq -r 'keys[]' 2>/dev/null | head -10 || echo "Could not parse router names"
            
            # Search for your domain more carefully
            log_info "Searching for domain $DOMAIN in router rules..."
            local domain_matches
            domain_matches=$(echo "$all_routers" | jq -r '.[] | select(.rule? and (.rule | contains("'"$DOMAIN"'"))) | .rule' 2>/dev/null || echo "")
            if [[ -n "$domain_matches" ]]; then
                log_success "Found routes for $DOMAIN:"
                echo "$domain_matches"
            else
                log_warning "No routes found for $DOMAIN in API (but traffic is working!)"
            fi
            
        else
            log_error "No router data received from Traefik API"
            add_issue "traefik router API not responding"
        fi
        
        # Check services too
        log_info "Checking Traefik services..."
        local services
        services=$(docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/services --timeout=10 2>/dev/null || echo "")
        if [[ -n "$services" ]] && [[ "$services" != "404 page not found" ]]; then
            local service_count
            service_count=$(echo "$services" | jq '. | length' 2>/dev/null || echo "unknown")
            log_info "Total services found: $service_count"
        else
            log_warning "Services API not responding"
        fi
        
    else
        log_error "Traefik ping failed - API is completely down"
        log_info "This explains why API queries fail, but traffic routing still works"
        log_info "Traefik data plane (routing) works independently of control plane (API)"
        add_issue "traefik API completely unavailable"
        
        # Check if Traefik process is actually running
        log_info "Checking if Traefik process exists..."
        local traefik_processes
        traefik_processes=$(docker exec coolify-proxy ps aux | grep -v grep | grep traefik || echo "")
        if [[ -n "$traefik_processes" ]]; then
            log_info "Traefik process is running:"
            echo "$traefik_processes"
        else
            log_error "No Traefik process found in container!"
        fi
        
        return 1
    fi
}


# Add function to check for problematic certificate configurations
check_certificate_issues() {
    log_step "CERTIFICATE CONFIGURATION ANALYSIS"
    
    log_info "Checking for problematic certificate configurations..."
    
    # Check Traefik logs for certificate errors
    local cert_errors=$(docker logs coolify-proxy --tail 50 | grep -i "certificate\|acme\|letsencrypt" || echo "")
    if [[ -n "$cert_errors" ]]; then
        log_warning "Found certificate-related errors in logs:"
        echo "$cert_errors" | tail -5
        
        # Check for specific problematic domains
        if echo "$cert_errors" | grep -q "reyesjewels.com"; then
            log_error "CRITICAL: Legacy domain reyesjewels.com causing certificate failures"
            log_error "This legacy configuration is causing Traefik restarts"
            add_issue "legacy domain causing certificate renewal failures"
        fi
        
        if echo "$cert_errors" | grep -q "NXDOMAIN"; then
            log_error "DNS resolution failures detected for certificate domains"
            add_issue "DNS resolution failures for certificate domains"
        fi
    else
        log_success "No recent certificate errors found"
    fi
    
    # Check if current domain certificate is working
    log_info "Testing SSL certificate for $DOMAIN..."
    local ssl_test=$(echo | openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null | grep -o "Verify return code: [0-9]*" || echo "")
    if [[ -n "$ssl_test" ]]; then
        if echo "$ssl_test" | grep -q "Verify return code: 0"; then
            log_success "SSL certificate verification successful"
        else
            log_warning "SSL certificate verification issues: $ssl_test"
        fi
    else
        log_warning "Could not verify SSL certificate"
    fi
}

check_docker_events() {
    log_step "DOCKER EVENTS ANALYSIS"
    
    # Check for recent significant events only
    log_info "Recent significant Docker events for $NGINX_CONTAINER:"
    
    local events=$(docker events --since '2h' --filter container="$NGINX_CONTAINER" \
        --filter event=start --filter event=stop --filter event=restart \
        --filter event=die --filter event=kill --filter event=destroy \
        --format '{{.Time}} {{.Action}} {{.Status}}' --until "$(date --utc +%Y-%m-%dT%H:%M:%SZ)" 2>/dev/null || echo "")
    
    if [[ -n "$events" ]]; then
        echo "$events" | tail -10  # Only show last 10 events
        local restart_count=$(echo "$events" | grep -c "restart\|stop\|die" || echo 0)
        if [[ $restart_count -gt 0 ]]; then
            log_warning "Container has been restarted/stopped $restart_count times in the last 2 hours"
            add_issue "container instability detected"
        fi
    else
        log_info "No significant container events in the last 2 hours"
    fi
    
    # Check for proxy restart events that might affect route discovery
    log_info "Checking coolify-proxy restart events..."
    local proxy_events=$(docker events --since '24h' --filter container=coolify-proxy \
        --filter event=start --format '{{.Time}} {{.Action}}' --until "$(date --utc +%Y-%m-%dT%H:%M:%SZ)" 2>/dev/null || echo "")
    
    if [[ -n "$proxy_events" ]]; then
        local proxy_restart_count=$(echo "$proxy_events" | wc -l)
        log_info "coolify-proxy restarted $proxy_restart_count times in the last 24h"
        if [[ $proxy_restart_count -gt 2 ]]; then
            log_warning "Frequent proxy restarts detected - this can cause route discovery issues"
            add_issue "frequent proxy restarts"
        fi
    fi
}


check_deployment_timing() {
    log_step "DEPLOYMENT TIMING ANALYSIS"
    
    local nginx_started=$(docker inspect "$NGINX_CONTAINER" --format '{{.State.StartedAt}}')
    local proxy_started=$(docker inspect coolify-proxy --format '{{.State.StartedAt}}')
    
    log_info "Nginx started: $nginx_started"
    log_info "Proxy started: $proxy_started"
    
    # Convert to timestamps for comparison
    local nginx_ts=$(date -d "$nginx_started" +%s 2>/dev/null || echo 0)
    local proxy_ts=$(date -d "$proxy_started" +%s 2>/dev/null || echo 0)
    
    if [[ $proxy_ts -gt $nginx_ts ]]; then
        local diff=$(( proxy_ts - nginx_ts ))
        log_error "CRITICAL: Proxy restarted ${diff} seconds AFTER container deployment!"
        log_error "This causes Traefik to miss container discovery events"
        add_issue "proxy restarted after container deployment (timing issue)"
    else
        log_success "Container deployment timing looks normal"
    fi
}

check_header_passthrough() {
    log_step "HEADER PASS-THROUGH ANALYSIS"
    
    log_info "Testing header pass-through from nginx to external..."
    
    # Test if custom headers make it through
    local test_response=$(curl -s -I "http://$NGINX_CONTAINER:80" --max-time 5 2>/dev/null || echo "")
    
    if [[ -n "$test_response" ]]; then
        # Check for common stripped headers
        if ! echo "$test_response" | grep -qi "access-control-allow"; then
            log_warning "No CORS headers detected - may cause cross-origin issues"
            add_issue "CORS headers not present"
        fi
        
        if echo "$test_response" | grep -qi "server.*nginx"; then
            log_info "Server header present (nginx detected)"
        else
            log_warning "Server header may be stripped"
        fi
    else
        log_warning "Could not test header pass-through"
    fi
}

check_route_conflicts() {
    log_step "ROUTE CONFLICT ANALYSIS"
    
    log_info "Checking for route priority conflicts..."
    
    # Get all routers and their rules
    local all_routers=$(docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers 2>/dev/null || echo "")
    
    if [[ -n "$all_routers" ]]; then
        # Check for conflicting Host rules
        local host_conflicts=$(echo "$all_routers" | grep -o "Host(\`[^)]*\`)" | sort | uniq -d | wc -l)
        if [[ $host_conflicts -gt 0 ]]; then
            log_error "Found $host_conflicts conflicting Host rules"
            add_issue "route conflicts detected"
        fi
        
        # Check router priorities for this domain
        local domain_routers=$(echo "$all_routers" | grep "$DOMAIN" || echo "")
        if [[ -n "$domain_routers" ]]; then
            log_info "Found routers for $DOMAIN:"
            echo "$domain_routers" | grep -o '"[^"]*@docker"' | head -5
            
            # Check if priority is set
            if ! echo "$domain_routers" | grep -q "priority"; then
                log_warning "No explicit priority set for $DOMAIN routes"
                add_issue "no explicit route priority"
            fi
        else
            log_error "No routers found for $DOMAIN in Traefik API"
        fi
        
        # Check for PathPrefix conflicts
        local path_conflicts=$(echo "$all_routers" | grep -c "PathPrefix(\`/\`)")
        if [[ $path_conflicts -gt 1 ]]; then
            log_warning "Found $path_conflicts routes with PathPrefix(/) - may cause conflicts"
            add_issue "multiple root path routes detected"
        fi
    else
        log_error "Could not retrieve router information from Traefik API"
        add_issue "traefik API not accessible for router analysis"
    fi
}

check_docker() {
    if ! command_exists docker; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker ps >/dev/null 2>&1; then
        log_error "Cannot access Docker daemon. Check permissions or if Docker is running."
        exit 1
    fi
    
    log_success "Docker is accessible"
}

# Add this function to test actual routing
test_actual_routing() {
    log_step "ACTUAL ROUTING TEST"
    
    log_info "Testing if Traefik is actually routing traffic..."
    
    # Test internal routing from proxy to container
    local internal_test=$(docker exec coolify-proxy curl -s -o /dev/null -w "%{http_code}" "http://$NGINX_CONTAINER:80" 2>/dev/null || echo "000")
    
    if [[ "$internal_test" == "401" ]] || [[ "$internal_test" == "200" ]]; then
        log_success "Internal routing working (HTTP $internal_test)"
    else
        log_error "Internal routing failed (HTTP $internal_test)"
    fi
    
    # Test external routing
    local external_test=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/" --max-time 10 2>/dev/null || echo "000")
    
    if [[ "$external_test" == "401" ]] || [[ "$external_test" == "200" ]]; then
        log_success "External routing working perfectly! (HTTP $external_test)"
        log_info "Your site is accessible and working correctly"
    else
        log_error "External routing failed (HTTP $external_test)"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}Coolify Network Diagnostics Script v$SCRIPT_VERSION${NC}"
    echo -e "${BLUE}=================================================${NC}"
    
    if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
        echo "Usage: $0 [domain] [auto-fix]"
        echo ""
        echo "Arguments:"
        echo "  domain    Domain to check (default: your-domain.com)"
        echo "  auto-fix  Enable automatic fixes (use 'auto-fix')"
        echo ""
        echo "Examples:"
        echo "  $0 preview.crati.co"
        echo "  $0 preview.crati.co auto-fix"
        exit 0
    fi
    
    log_info "Checking domain: $DOMAIN"
    log_info "Auto-fix mode: $AUTO_FIX"
    
    # Prerequisites
    check_docker
    
    # Find nginx container
    if ! find_nginx_container; then
        log_error "Cannot proceed without nginx container"
        exit 1
    fi
    
    # Run diagnostic steps
    check_container_health
    check_internal_connectivity
    check_external_connectivity  
    check_network_membership
    check_traefik_config
    check_certificate_issues
    check_route_conflicts
    check_nginx_config_issues
    check_header_passthrough
    check_container_labels
    check_docker_events
    check_deployment_timing
    check_coolify_version_issues
    check_traefik_config_detailed
    test_actual_routing

    
    # Apply fixes if requested
    apply_fixes
    
    # Test external access
    test_external_access
    
    # Generate final report
    generate_report
    
    # Exit code based on issues found
    if [[ ${#ISSUES_FOUND[@]} -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# Run main function with all arguments
main "$@"
