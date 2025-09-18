# Preview Environment Network Connectivity Issue - Troubleshooting Guide

**Date**: July 4, 2025  
**Environment**: Coolify with Traefik proxy  
**Domain**: preview.crati.co  
**Issue**: Complete application inaccessibility despite healthy containers  

## 🚨 Problem Summary

The preview environment became completely inaccessible from external requests, showing either:
- Infinite redirect loops (302 responses)
- Gateway timeouts (504 errors) 
- Connection timeouts

All containers were running healthy, internal networking worked perfectly, but external traffic couldn't reach the application.

## 🔍 Root Cause Analysis

**Primary Issue**: **Docker Network Connectivity Failure**
- The nginx container was not connected to Coolify's proxy network (`coolify`)
- Traefik (coolify-proxy) couldn't reach the nginx container
- This prevented external routing despite correct Traefik labels

**Secondary Issues Investigated**:
1. ~~Cloudflare SSL mode~~ (Fixed: Changed from Flexible to Full Strict)
2. ~~Frontend container issues~~ (Production build working correctly)
3. ~~Nginx configuration~~ (Configuration was correct)
4. ~~Authentication problems~~ (Basic auth working correctly)

## 🛠️ Diagnostic Steps & Results

### 1. Container Health Check
```bash
# Check if containers are running
docker ps | grep lgwgsc00gcgoo4wscogwswkk
# ✅ Result: All containers running normally
```

### 2. Internal Container Communication Test
```bash
# Test backend to frontend communication
docker exec backend-container wget -qO- http://frontend:3000/
# ✅ Result: Successful - returned HTML content

# Test nginx to backend communication  
docker exec nginx-container wget -qO- http://backend:8000/
# ✅ Result: Successful - returned health check JSON
```

### 3. Nginx Configuration Validation
```bash
# Check nginx config syntax
docker exec nginx-container nginx -t
# ✅ Result: Configuration syntax OK

# Check nginx processes
docker exec nginx-container ps aux
# ✅ Result: Master and worker processes running

# Check nginx listening ports
docker exec nginx-container netstat -tlnp
# ✅ Result: Listening on 0.0.0.0:80
```

### 4. Network Connectivity Analysis
```bash
# Check nginx container networks
docker inspect nginx-container | grep -A 20 "Networks"
# ❌ Result: Only on 'lgwgsc00gcgoo4wscogwswkk' network (172.22.0.x)

# Check Traefik/coolify-proxy networks  
docker inspect coolify-proxy | grep -A 20 "Networks"
# ❌ Result: Only on 'coolify' network (172.20.0.x)

# Test connectivity between Traefik and nginx
docker exec coolify-proxy nc -zv nginx-container 80
# ❌ Result: Connection refused - different networks!
```

### 5. Traefik Configuration Check
```bash
# Check if Traefik has routing rules for domain
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers | grep preview.crati.co
# ❌ Result: No routers found for domain

# Check container labels
docker inspect nginx-container | grep traefik
# ✅ Result: All correct Traefik labels present
```

## ✅ Solution Applied

### Step 1: Network Connection Fix
```bash
# Manually connect nginx container to coolify network
docker network connect coolify nginx-lgwgsc00gcgoo4wscogwswkk-184532725431

# Verify nginx now on both networks
docker inspect nginx-container | grep -A 20 "Networks"
# ✅ Result: Now on both 'coolify' (172.20.0.3) and 'lgwgsc00gcgoo4wscogwswkk' networks
```

### Step 2: Test Connectivity
```bash
# Test Traefik to nginx connectivity
docker exec coolify-proxy nc -zv nginx-container 80
# ✅ Result: Connection successful

# Test with authentication
docker exec coolify-proxy wget -qO- --header="Authorization: Basic ..." http://nginx-container/
# ✅ Result: HTML content returned successfully
```

### Step 3: Traefik Configuration Refresh
```bash
# Restart Traefik to refresh routing configuration
docker restart coolify-proxy

# Wait for startup and test external access
curl -v https://preview.crati.co/
# ✅ Result: 401 Authentication Required (correct response!)
```

## 🎯 Final Verification

```bash
# Test with proper authentication
curl -u "username:password" https://preview.crati.co/
# ✅ Result: Application accessible and working correctly
```

## 🚀 Prevention & Early Detection

### What to Monitor
1. **Container Network Membership**
   ```bash
   # Verify nginx is on coolify network
   docker network inspect coolify | grep -A 5 nginx-container-name
   ```

2. **Traefik Routing Rules**
   ```bash
   # Check if domain has active routers
   docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers | grep your-domain.com
   ```

3. **Network Connectivity**
   ```bash
   # Test Traefik can reach nginx
   docker exec coolify-proxy nc -zv nginx-container 80
   ```

### Warning Signs
- ❌ External requests timeout without reaching containers
- ❌ No logs in nginx access logs for external requests  
- ❌ Traefik API shows no routers for your domain
- ❌ Container only on application network, not coolify network

### Quick Diagnosis Commands
```bash
# One-liner health check
docker network inspect coolify | grep "$(docker ps --format '{{.Names}}' | grep nginx)" || echo "❌ Nginx not on coolify network"

# Check if Traefik knows about your domain
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | grep -q "your-domain.com" && echo "✅ Domain found" || echo "❌ Domain not found"
```

## 🤔 Why This Happened

**Coolify's Expected Behavior**: Coolify should automatically connect containers to the proxy network during deployment.

**Possible Causes**:
1. **Deployment Race Condition**: Network connection failed during container startup
2. **Coolify Bug**: Network management failed silently 
3. **Resource Constraints**: Temporary resource issues during deployment
4. **Docker Daemon Issues**: Docker network driver problems

**Most Likely**: This appears to be a **Coolify reliability issue** since:
- Other deployments work normally
- Container labels were correctly applied
- Internal networking worked perfectly
- Manual network connection immediately resolved the issue

## 📋 Future Action Plan

### If This Happens Again:
1. **First**: Check network connectivity between Traefik and nginx
2. **Second**: Verify Traefik routing configuration
3. **Third**: Check container network membership
4. **Last Resort**: Manually connect to coolify network and restart Traefik

### Coolify Reliability Considerations:
- Monitor for similar issues across deployments
- Consider implementing health checks that verify network connectivity
- Document any patterns that trigger this issue
- Report to Coolify maintainers if it becomes recurring

### Alternative Solutions:
- Consider using explicit network configuration in docker-compose
- Implement monitoring that alerts on network connectivity issues
- Use health checks that verify external accessibility

## 📝 Lessons Learned

1. **Container Health ≠ Application Accessibility**: Running containers don't guarantee network reachability
2. **Layered Networking**: Modern deployments have multiple network layers that can fail independently
3. **Diagnostic Importance**: Network-level debugging is crucial for container orchestration issues
4. **Coolify Limitations**: Even managed solutions can have reliability issues requiring manual intervention

---

**Resolution Time**: ~2 hours  
**Impact**: Complete service outage  
**Complexity**: Medium (required deep networking knowledge)  
**Recurrence Risk**: Low (but possible due to underlying Coolify reliability concerns)