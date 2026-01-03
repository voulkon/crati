"""
Central registry of Redis keys used throughout the application.
"""

# Key namespaces
STATS_NS = "stats"
RATELIMIT_NS = "ratelimit"

# Stats keys
TOTAL_REQUESTS = f"{STATS_NS}:total_requests"
UNIQUE_IPS = f"{STATS_NS}:unique_ips"
HOURLY_STATS = f"{STATS_NS}:hourly"
DAILY_STATS = f"{STATS_NS}:daily"
ENDPOINT_PREFIX = f"{STATS_NS}:endpoint:"
METHOD_PREFIX = f"{STATS_NS}:method:"
USER_AGENTS = f"{STATS_NS}:user_agents"

# IP tracking keys (for user journey analysis)
IP_ENDPOINTS_PREFIX = f"{STATS_NS}:ip:"  # stats:ip:<ip>:endpoints
ENDPOINT_IPS_PREFIX = f"{STATS_NS}:endpoint_ips:"  # stats:endpoint_ips:<endpoint>

# AFM Fetch Locking (distributed lock for company data fetching)
AFM_FETCH_LOCK_PREFIX = "lock:afm_fetch:"
AFM_FETCH_LOCK_TIMEOUT = 60 * 5  # 5 minutes lock timeout

# Rate limit keys
USER_RATELIMIT_PREFIX = f"{RATELIMIT_NS}:user:"
IP_RATELIMIT_PREFIX = f"{RATELIMIT_NS}:ip:"

# Default expiration times (in seconds)
STATS_EXPIRE = 60 * 60 * 24 * 30  # 30 days
RATELIMIT_EXPIRE = 60 * 60 * 24  # 24 hours

AFM_FETCH_LOCK_PREFIX = "afm_fetch_lock:"
AFM_FETCH_LOCK_TIMEOUT = 300

def get_endpoint_key(endpoint):
    """Get the Redis key for endpoint stats"""
    return f"{ENDPOINT_PREFIX}{endpoint}"


def get_method_key(method):
    """Get the Redis key for HTTP method stats"""
    return f"{METHOD_PREFIX}{method}"


def get_user_ratelimit_key(user_id):
    """Get the Redis key for user rate limiting"""
    return f"{USER_RATELIMIT_PREFIX}{user_id}"


def get_ip_ratelimit_key(ip):
    """Get the Redis key for IP rate limiting"""
    return f"{IP_RATELIMIT_PREFIX}{ip}"


def get_ip_endpoints_key(ip: str) -> str:
    """Generate Redis key for tracking endpoints visited by an IP"""
    return f"{IP_ENDPOINTS_PREFIX}{ip}:endpoints"


def get_endpoint_ips_key(endpoint: str) -> str:
    """Generate Redis key for tracking IPs that visited an endpoint"""
    return f"{ENDPOINT_IPS_PREFIX}{endpoint}"
