# Coolify Caddy Basic Auth Label Bug Report

## Summary

The `caddy_0.basicauth` label generates an invalid Caddyfile, placing the `basicauth` directive as a global option instead of inside the site block.

## Environment

- **Coolify Version:** (fill in from your instance)
- **Caddy Proxy:** coolify-proxy container
- **Deployment Method:** Git-based deployment via Coolify UI

## Steps to Reproduce

1. Add the following label to a service in `docker-compose.yaml`:
   ```yaml
   labels:
     - 'caddy_0.basicauth.admin="$$2a$$14$$wSoeyRmlaOsma23OlVSUcOTnh3hrbaBZU0WSt27ntfGRVw/ScEQPK"'
   ```

2. Deploy via Coolify Git integration

3. Check the Caddy proxy logs:
   ```bash
   docker logs coolify-proxy --tail 50
   ```

## Expected Behavior

The `basicauth` directive should be placed **inside** the site block in the generated Caddyfile:

```caddyfile
https://jaeger-preview-test.crati.co {
	basicauth {
		admin $2a$14$wSoeyRmlaOsma23OlVSUcOTnh3hrbaBZU0WSt27ntfGRVw/ScEQPK
	}
	encode zstd gzip
	handle_path /* {
		reverse_proxy 172.18.0.4:16686
	}
	header -Server
	try_files {path} /index.html /index.php
}
```

## Actual Behavior

Coolify generates the `basicauth` block **outside** the site block as a global option:

```caddyfile
{
	basicauth {
		admin $2a$14$wSoeyRmlaOsma23OlVSUcOTnh3hrbaBZU0WSt27ntfGRVw/ScEQPK
	}
}
https://jaeger-preview-test.crati.co {
	encode zstd gzip
	handle_path /* {
		reverse_proxy 172.18.0.4:16686
	}
	header -Server
	try_files {path} /index.html /index.php
}
```

## Error Messages

From `docker logs coolify-proxy`:

```
{"level":"info","ts":1772049288.8599327,"logger":"docker-proxy","msg":"Process Caddyfile","logs":"[ERROR]  Removing invalid block: Caddyfile:2: unrecognized global option: basicauth\n{\n\tbasicauth {\n\t\tadmin $2a$14$wSoeyRmlaOsma23OlVSUcOTnh3hrbaBZU0WSt27ntfGRVw/ScEQPK\n\t}\n}\n\n"}
```

## Root Cause

In Caddy v2, `basicauth` (or `basic_auth` in v2.8.0+) is a **site directive**, not a global option. It must be placed within a site block, not at the global scope.

Reference: https://caddyserver.com/docs/caddyfile/directives/basic_auth

## Additional Issues Observed

### 1. Environment Variable Substitution

When using `${VARIABLE}` syntax in labels, Coolify escapes `$` to `$$`, resulting in literal `${VARIABLE}` strings instead of substituted values:

**Input (in source compose file):**
```yaml
labels:
  - "caddy_0.basicauth.${JAEGER_AUTH_USER}=${JAEGER_AUTH_HASH}"
```

**Result (in Coolify-generated compose):**
```yaml
labels:
  - 'caddy_0.basicauth.$${JAEGER_AUTH_USER}=$${JAEGER_AUTH_HASH}'
```

This means environment variables defined in Coolify are not substituted into Caddy labels.

### 2. Dollar Sign Handling in Hashes

Bcrypt hashes contain `$` characters (e.g., `$2a$14$...`). These are interpreted as environment variable references by Docker Compose, requiring double-escaping (`$$`) which further complicates the configuration.

## Workaround

Currently, there is no working workaround using the `caddy_0.basicauth` label syntax. The feature appears to be broken for Caddy v2.

Possible alternatives:
1. Use Coolify's built-in Basic Auth feature if available in the UI
2. Configure authentication at the application level (e.g., nginx auth, application middleware)
3. Use a separate authentication proxy (e.g., oauth2-proxy, authelia)

## Impact

- Users cannot protect services with HTTP Basic Authentication using the documented label syntax
- The feature is non-functional for Caddy-based deployments
- Security-sensitive services remain exposed without authentication

## Related Documentation

- Coolify Basic Auth Docs: (link to the docs you referenced)
- Caddy basic_auth directive: https://caddyserver.com/docs/caddyfile/directives/basic_auth
