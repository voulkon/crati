# Coolify Network Troubleshooting Guide - General Reference

**Purpose**: Systematic approach to diagnose and fix network connectivity issues in Coolify deployments  
**Target**: Any application experiencing external accessibility problems despite healthy containers  

---

## 🤖 Automated Diagnostic Script (Recommended)

**For quick diagnosis, use the automated script first:**

### Basic Usage (Safe Diagnostics Only):
```bash
# Navigate to your project directory
cd /path/to/your/coolify/project

# Make script executable (if not already)
chmod +x util_scripts/coolify-diagnostics.sh

# Run diagnostics for your domain (read-only, completely safe)
./util_scripts/coolify-diagnostics.sh preview.crati.co

# Or for any domain
./util_scripts/coolify-diagnostics.sh your-domain.com
```

### Advanced Usage (With Auto-Fix):
```bash
# Run diagnostics AND automatically fix common issues
./util_scripts/coolify-diagnostics.sh preview.crati.co auto-fix

# What auto-fix does (safe operations only):
# ✅ Connects nginx container to coolify network (if missing)
# ✅ Restarts Traefik to refresh configuration (if needed)
# ❌ Never deletes containers, data, or configs
```

### Script Arguments:
- **First argument**: Your domain (e.g., `preview.crati.co`)
- **Second argument**: `auto-fix` to enable automatic fixes (optional)

### Safety Guarantee:
- **Read-only by default** - only diagnoses and reports issues
- **Non-destructive fixes** - only connects networks and restarts services
- **No data loss risk** - never modifies files or deletes containers
- **Reversible actions** - all fixes can be easily undone

### Example Output:
```bash
$ ./util_scripts/coolify-diagnostics.sh preview.crati.co

[INFO] Checking domain: preview.crati.co
[✅ SUCCESS] Found nginx container: crati-nginx-xyz
[✅ SUCCESS] coolify-proxy is running
[✅ SUCCESS] Nginx container is running
[❌ ERROR] coolify-proxy CANNOT reach nginx container
[❌ ERROR] Nginx container is NOT on coolify network

Issues Found (2):
❌ no connectivity between coolify-proxy and nginx
❌ nginx not on coolify network

Next Steps:
⚠️ Issues detected. Recommended actions:
   - Run: docker network connect coolify crati-nginx-xyz
   - Consult the full troubleshooting guide for detailed steps
```

**🎯 Use this script first before manual troubleshooting - it will save you time!**

---

## 🎯 Quick Diagnosis Checklist

Run these in order to quickly identify the issue:

```bash
# 1. ✅ Are the key containers running?
docker ps | grep -E "(nginx|proxy|traefik)"

# 2. ✅ Can Traefik reach the nginx container?
docker exec coolify-proxy nc -zv $(docker ps --format '{{.Names}}' | grep nginx | head -1) 80

# 3. ✅ Does Traefik have routing rules for your domain?
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | grep "your-domain.com"

# 4. ✅ Is nginx on the coolify network?
docker network inspect coolify | grep -A 5 "$(docker ps --format '{{.Names}}' | grep nginx | head -1)"
```

**If any step fails, jump to the corresponding detailed section below.**

---

## 📋 Systematic Troubleshooting Steps

### Step 1: Container Health Verification

```bash
# Check if your application containers are running
docker ps | grep your-app-id

# Check specifically for nginx/gateway container
docker ps | grep nginx

# Check if coolify-proxy (Traefik) is running
docker ps | grep coolify-proxy

# Check container logs for errors
docker logs container-name --tail 50
```

**Expected Results:**
- ✅ All containers should show "Up" status
- ✅ No crash loops or restart counts increasing
- ✅ Recent logs should show normal operation

**If containers are not running:** Check Coolify deployment logs, resource constraints, or Docker daemon issues.

---

### Step 2: Internal Network Connectivity

```bash
# Test nginx container is responding internally
docker exec nginx-container-name wget -qO- http://localhost:80 2>/dev/null || echo "❌ Nginx not responding"

# Test nginx config syntax
docker exec nginx-container-name nginx -t

# Check what ports nginx is listening on
docker exec nginx-container-name netstat -tlnp

# Test application containers can communicate
docker exec backend-container wget -qO- http://frontend:3000/ 2>/dev/null && echo "✅ Frontend reachable"
docker exec nginx-container wget -qO- http://backend:8000/ 2>/dev/null && echo "✅ Backend reachable"
```

**Expected Results:**
- ✅ Nginx responds on port 80
- ✅ Nginx config syntax is valid
- ✅ Inter-container communication works

**If internal communication fails:** Check container networking, service discovery, or application configuration.

---

### Step 3: External Network Connectivity (Critical!)

```bash
# Check if coolify-proxy can reach nginx container
NGINX_CONTAINER=$(docker ps --format '{{.Names}}' | grep nginx | head -1)
docker exec coolify-proxy nc -zv $NGINX_CONTAINER 80

# Test with actual HTTP request
docker exec coolify-proxy wget -qO- http://$NGINX_CONTAINER/ 2>&1 | head -10

# Test connectivity by IP if container name fails
NGINX_IP=$(docker inspect $NGINX_CONTAINER | grep '"IPAddress"' | tail -1 | cut -d'"' -f4)
docker exec coolify-proxy nc -zv $NGINX_IP 80
```

**Expected Results:**
- ✅ Port 80 should be open and accessible
- ✅ HTTP requests should return response (even if 401/403)

**If connectivity fails:** This is the most common issue - proceed to Step 4.

---

### Step 4: Network Membership Analysis

```bash
# Check what networks nginx container is on
docker inspect $NGINX_CONTAINER | grep -A 20 "Networks"

# Check what networks coolify-proxy is on  
docker inspect coolify-proxy | grep -A 20 "Networks"

# List all Docker networks
docker network ls

# Specifically inspect the coolify network
docker network inspect coolify

# Check if nginx is on coolify network
docker network inspect coolify | grep -A 5 $NGINX_CONTAINER
```

**Expected Results:**
- ✅ Nginx container should be on both application network AND coolify network
- ✅ Coolify-proxy should be on coolify network
- ✅ Both should have IPs in same network range (e.g., 172.20.0.x)

**If nginx is missing from coolify network:** This is the fix - proceed to Step 8.

---

### Step 5: Traefik Configuration Analysis

```bash
# Check Traefik main configuration
docker exec coolify-proxy cat /traefik/traefik.yml

# Check Traefik docker-compose (shows how it's configured)
docker exec coolify-proxy cat /traefik/docker-compose.yml

# Check dynamic configuration directory
docker exec coolify-proxy ls -la /traefik/dynamic/

# Check if any dynamic configs mention your domain
docker exec coolify-proxy grep -r "your-domain.com" /traefik/dynamic/ 2>/dev/null || echo "No static configs found"
```

**Gold Mine Commands** (show Coolify's inner workings):
```bash
# See exactly how Traefik is configured by Coolify
docker exec coolify-proxy cat /traefik/traefik.yml

# See Traefik's docker-compose setup
docker exec coolify-proxy cat /traefik/docker-compose.yml

# Check for any manual overrides
docker exec coolify-proxy find /traefik -name "*.yml" -o -name "*.yaml" | xargs ls -la
```

---

### Step 6: Traefik API Inspection

```bash
# Check if Traefik API is accessible
docker exec coolify-proxy wget -qO- http://localhost:8080/ping || echo "❌ Traefik API down"

# List all HTTP routers
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | jq '.' || docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers 2>/dev/null

# Search for your domain in routers
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | grep "your-domain.com"

# List all HTTP services
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/services 2>/dev/null | grep nginx

# Check middlewares
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/middlewares 2>/dev/null
```

**Expected Results:**
- ✅ Traefik API should respond to ping
- ✅ Should find routers with rules matching your domain
- ✅ Should find services pointing to your nginx container

**If no routers found:** Traefik isn't picking up the container labels.

---

### Step 7: Container Labels Verification

```bash
# Check if nginx container has correct Traefik labels
docker inspect $NGINX_CONTAINER | grep -A 10 -B 5 traefik

# Look specifically for domain rules
docker inspect $NGINX_CONTAINER | grep "your-domain.com"

# Check for traefik.enable label
docker inspect $NGINX_CONTAINER | grep "traefik.enable"

# Verify all required labels are present
docker inspect $NGINX_CONTAINER | grep -E "(traefik\.http\.routers|traefik\.http\.services|traefik\.enable)"
```

**Expected Results:**
- ✅ `traefik.enable=true`
- ✅ Router rules with your domain
- ✅ Service definitions pointing to correct port

**If labels are missing:** Coolify configuration issue or deployment problem.

---

### Step 8: Coolify Application Configuration

```bash
# Connect to Coolify database to check application settings
docker exec coolify php artisan tinker

# In tinker, check application configuration:
\App\Models\Application::where('fqdn', 'like', '%your-domain%')->get();

# Check specific application by ID
$app = \App\Models\Application::find(YOUR_APP_ID);
echo $app->fqdn;
echo $app->status;
```

**Coolify Configuration Commands:**
```bash
# Check Coolify logs for deployment issues
docker logs coolify --tail 100 | grep -i error

# Check recent Coolify activity
docker logs coolify --since 1h | grep "your-domain"

# Check Coolify database health
docker exec coolify php artisan health:check
```

---

## 🛠️ Common Fixes

### Fix 1: Network Connectivity Issue (Most Common)

```bash
# Connect nginx container to coolify network
docker network connect coolify $NGINX_CONTAINER

# Verify connection
docker network inspect coolify | grep -A 5 $NGINX_CONTAINER

# Test connectivity
docker exec coolify-proxy nc -zv $NGINX_CONTAINER 80
```

### Fix 2: Traefik Configuration Refresh

```bash
# Restart Traefik to reload configuration
docker restart coolify-proxy

# Wait for startup
sleep 30

# Verify routers are loaded
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | grep "your-domain"
```

### Fix 3: Application FQDN Configuration

```bash
# In Coolify tinker
$app = \App\Models\Application::find(YOUR_APP_ID);
$app->fqdn = 'your-domain.com';
$app->save();

# Trigger redeploy
# (Usually done through Coolify UI)
```

### Fix 4: Container Label Fix

If labels are missing, redeploy through Coolify:
1. Go to Coolify dashboard
2. Find your application  
3. Click "Redeploy"
4. Monitor deployment logs

---

## 🚨 Emergency Quick Fixes

### Fastest Fix (Use the automated script):

```bash
# One command to diagnose and fix most issues
./util_scripts/coolify-diagnostics.sh your-domain.com auto-fix
```

### If external site is completely down (manual approach):

```bash
# 1. Quick network fix
NGINX_CONTAINER=$(docker ps --format '{{.Names}}' | grep nginx | head -1)
docker network connect coolify $NGINX_CONTAINER
docker restart coolify-proxy

# 2. Test immediately
curl -I https://your-domain.com --max-time 10
```

### If still not working:

```bash
# 3. Check what's actually broken
docker exec coolify-proxy nc -zv $NGINX_CONTAINER 80 || echo "❌ Network issue"
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | grep -q "your-domain" && echo "✅ Router found" || echo "❌ No router"
```

---

## 📊 Debugging Command Reference

### Essential Information Gathering:
```bash
# Application container status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep your-app

# Network information
docker network ls
docker network inspect coolify

# Traefik status  
docker exec coolify-proxy wget -qO- http://localhost:8080/ping
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers

# Container network details
docker inspect container-name | grep -A 20 "Networks"

# Container labels
docker inspect container-name | grep -A 20 "Labels"
```

### Coolify Inner Workings (Gold Mine Commands):
```bash
# Traefik configuration
docker exec coolify-proxy cat /traefik/traefik.yml
docker exec coolify-proxy cat /traefik/docker-compose.yml
docker exec coolify-proxy ls -la /traefik/dynamic/

# Coolify application data  
docker exec coolify php artisan tinker
# Then: \App\Models\Application::all()->pluck('name', 'fqdn');

# Coolify logs
docker logs coolify --tail 100
docker logs coolify --since 1h | grep your-domain
```

---

## 🎯 Success Indicators

You know it's fixed when:

```bash
# External access works
curl -I https://your-domain.com
# ✅ Should return HTTP response (even 401 is good)

# Traefik sees the route
docker exec coolify-proxy wget -qO- http://localhost:8080/api/http/routers | grep your-domain
# ✅ Should return router configuration

# Network connectivity works
docker exec coolify-proxy nc -zv nginx-container 80
# ✅ Should show "open"

# Container is on correct network
docker network inspect coolify | grep nginx-container
# ✅ Should show container details
```

---

## 📝 Prevention Checklist

After fixing, verify these to prevent future issues:

- [ ] Nginx container is on both application and coolify networks
- [ ] Traefik has active routers for your domain
- [ ] Container labels are correctly applied
- [ ] Coolify application FQDN is properly set
- [ ] External connectivity test passes
- [ ] Monitor setup to catch future issues early

---

**Remember**: Most Coolify network issues are network connectivity problems between containers. Start with Step 3 (network connectivity) if you're in a hurry!
