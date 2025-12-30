# Auxiliary Services Security Guide

## Overview

This guide documents the authentication setup for all auxiliary services in the stack to prevent unauthorized access to sensitive monitoring and management tools.

## Service Authentication Status

### ✅ Secured Services

#### 1. **Flower** (Celery Task Monitor)
- **URL**: `https://flower-preview-test.crati.co:5555`
- **Authentication**: HTTP Basic Auth (built-in Flower support)
- **Credentials**:
  - Username: `admin` (from `BASIC_AUTH_USER`)
  - Password: from `BASIC_AUTH_PASSWORD` in `.env` file
- **Configuration**: See `docker-compose.prod.yml` - Flower command includes `--basic-auth` flag
- **Access**: Browser will prompt for credentials

#### 2. **RabbitMQ Management UI**
- **URL**: `https://rabbitmq-preview-test.crati.co:15672`
- **Authentication**: Built-in RabbitMQ auth
- **Credentials**:
  - Username: `crati_rabbitmq` (from `RABBITMQ_USER`)
  - Password: from `RABBITMQ_PASSWORD` in `.env` file
- **Configuration**: Set via `RABBITMQ_DEFAULT_USER` and `RABBITMQ_DEFAULT_PASS` in docker-compose

#### 3. **Grafana** (Monitoring Dashboards)
- **URL**: `https://grafana-preview-test.crati.co:3000`
- **Authentication**: Built-in Grafana auth
- **Credentials**:
  - Username: `admin` (default Grafana admin user)
  - Password: from `GRAFANA_ADMIN_PASSWORD` in `.env` file
- **Configuration**: Set via `GF_SECURITY_ADMIN_PASSWORD` environment variable
- **Note**: First-time login may prompt you to change password

### ⚠️ Jaeger (Distributed Tracing)
- **URL**: `https://jaeger-preview-test.crati.co:16686`
- **Current Status**: **NO NATIVE AUTHENTICATION**
- **Risk Level**: HIGH - Exposes internal service traces and performance data

#### Recommended Solutions for Jaeger:

**Option 1: Traefik/Nginx Basic Auth (Recommended for Coolify)**
Add Coolify labels to enable basic auth at the reverse proxy level:

```yaml
# Add to Jaeger service in docker-compose.prod.yml or Coolify UI
labels:
  - "traefik.http.middlewares.jaeger-auth.basicauth.users=${BASIC_AUTH_HASH}"
  - "traefik.http.routers.jaeger.middlewares=jaeger-auth"
```

**Option 2: IP Whitelisting**
Restrict access to specific IPs (your office, VPN, etc.):

```yaml
# In Coolify or Traefik config
labels:
  - "traefik.http.middlewares.jaeger-ipwhitelist.ipwhitelist.sourcerange=YOUR.IP.ADDRESS/32"
  - "traefik.http.routers.jaeger.middlewares=jaeger-ipwhitelist"
```

**Option 3: Use OAuth2 Proxy**
Deploy an OAuth2 proxy in front of Jaeger for Google/GitHub/GitLab authentication.

**Option 4: VPN/Private Network Only**
Don't expose Jaeger publicly; access via VPN or SSH tunnel:
```bash
ssh -L 16686:localhost:16686 user@server
# Then access http://localhost:16686
```

## Quick Reference: Login Credentials

### For Environment: `preview-test`

| Service | URL | Username | Password Location |
|---------|-----|----------|-------------------|
| **Main App** | https://preview-test.crati.co | (App-specific) | (App-specific) |
| **Flower** | https://flower-preview-test.crati.co:5555 | `admin` | `BASIC_AUTH_PASSWORD` |
| **RabbitMQ** | https://rabbitmq-preview-test.crati.co:15672 | `crati_rabbitmq` | `RABBITMQ_PASSWORD` |
| **Grafana** | https://grafana-preview-test.crati.co:3000 | `admin` | `GRAFANA_ADMIN_PASSWORD` |
| **Jaeger** | https://jaeger-preview-test.crati.co:16686 | ⚠️ NONE | ⚠️ UNPROTECTED |
| **Redis Commander** | (Not exposed) | N/A | Protected by network isolation |
| **OpenSearch Dashboards** | (Not exposed) | N/A | Protected by network isolation |

### Credentials from `.env.preview-test`:
```bash
# Basic Auth (Flower, potential Nginx/Traefik auth)
BASIC_AUTH_USER=admin
BASIC_AUTH_PASSWORD=EfjCjsPcZVG8yL1oY0jhxdmX

# RabbitMQ
RABBITMQ_USER=crati_rabbitmq
RABBITMQ_PASSWORD=iYDUePa6I3eIaFHw7zt4aHsjbT4nIZgw

# Grafana
GRAFANA_ADMIN_PASSWORD=c2f77630-240f-5ade-bc38-79052db56ba5
```

## Deployment Checklist

When deploying a new environment:

- [ ] Generate secrets using `setup-environment.sh`
- [ ] Add `FLOWER_BASIC_AUTH` to environment variables
- [ ] Verify Flower authentication works
- [ ] Test RabbitMQ login
- [ ] Test Grafana login (username: `admin`)
- [ ] **Secure Jaeger** - Choose one of:
  - [ ] Add Traefik/Nginx basic auth
  - [ ] Configure IP whitelisting
  - [ ] Deploy OAuth2 proxy
  - [ ] Keep on private network only
- [ ] Store credentials in secure password manager
- [ ] Document any custom auth configurations

## Security Best Practices

### 1. **Rotate Credentials Regularly**
```bash
# Regenerate secrets for an environment
./util_scripts/coolify-setup/setup-environment.sh preview-test --force --no-dns
```

### 2. **Use Strong Passwords**
The setup script generates 32-character passwords by default. Never use weak passwords like "admin" or "password".

### 3. **Limit Public Exposure**
Consider these options for truly sensitive services:
- Keep services on internal Docker network only
- Use VPN for access
- Implement IP whitelisting
- Use OAuth2/SSO for team access

### 4. **Monitor Access Logs**
Check Nginx/Traefik logs for suspicious access attempts:
```bash
docker logs nginx 2>&1 | grep -i "401\|403"
```

### 5. **Enable 2FA Where Possible**
- Grafana supports 2FA - enable it for production
- Consider using OAuth2 providers (Google, GitHub) that support 2FA

## Troubleshooting

### "I can't log into Flower"
1. Check that `FLOWER_BASIC_AUTH` is set in environment
2. Verify format is `username:password` (e.g., `admin:EfjCjsPcZVG8yL1oY0jhxdmX`)
3. Restart Flower container: `docker-compose restart flower`
4. Check Flower logs: `docker logs diavgeia_flower`

### "Grafana won't accept my password"
1. Username is always `admin` (default)
2. Password is from `GRAFANA_ADMIN_PASSWORD`
3. If locked out, reset via container:
   ```bash
   docker exec -it diavgeia_grafana grafana-cli admin reset-admin-password NEW_PASSWORD
   ```

### "RabbitMQ login fails"
1. Verify `RABBITMQ_USER` and `RABBITMQ_PASSWORD` match what's in the container
2. Check container environment: `docker exec diavgeia_rabbitmq env | grep RABBITMQ`
3. Recreate RabbitMQ container if credentials changed

### "I want to add auth to Jaeger"
For Coolify deployments, add these labels in the Coolify UI:

```yaml
traefik.http.middlewares.jaeger-auth.basicauth.users=${BASIC_AUTH_HASH}
traefik.http.routers.jaeger-UNIQUE_ID.middlewares=jaeger-auth
```

Replace `UNIQUE_ID` with your actual Coolify-generated router ID.

## Additional Security Layers

### Option: Tailscale/WireGuard VPN
Deploy a VPN solution and only expose services on VPN network:
```yaml
# Example: Bind services to Tailscale IP only
services:
  jaeger:
    ports:
      - "100.x.x.x:16686:16686"  # Tailscale IP only
```

### Option: Cloudflare Access
Use Cloudflare Zero Trust to add authentication layer:
1. Enable Cloudflare Access for your domain
2. Create access policies for each service subdomain
3. Configure authentication providers (Google, GitHub, email OTP)

### Option: mTLS (Mutual TLS)
For API-to-API communication, implement mutual TLS authentication.

## Environment-Specific Notes

Each environment (preview, staging, production) should have:
- Unique passwords (automatically generated by setup script)
- Separate DNS records
- Independent Cloudflare configurations
- Isolated databases and secrets

## Automated Security Updates

To update secrets across all environments:

```bash
# List all environments
ls .env_files/.env.* | grep -v summary

# Update specific environment
./util_scripts/coolify-setup/setup-environment.sh ENVIRONMENT --force --no-dns

# Apply new credentials to Coolify
# 1. Update environment variables in Coolify UI
# 2. Restart affected services
```

## Contact & Support

For security concerns or to report vulnerabilities:
- Review this guide regularly
- Keep credentials in secure password manager
- Rotate credentials if compromise suspected
- Monitor service access logs

---

**Last Updated**: 2025-12-29  
**Applies to**: All Coolify deployments using docker-compose.prod.yml
