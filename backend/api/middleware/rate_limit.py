from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.conf import settings
import time
from ..utils import get_client_ip
from django_redis import get_redis_connection
from ..redis_keys import (
    TOTAL_REQUESTS,
    UNIQUE_IPS,
    HOURLY_STATS,
    DAILY_STATS,
    USER_AGENTS,
    get_endpoint_key,
    get_method_key,
    get_user_ratelimit_key,
    get_ip_ratelimit_key,
)
from ..redis_utils import safe_incr
from diavgeia_project.security_tracing import security_tracer, get_client_ip


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Initialize Redis connection once
        self.redis = get_redis_connection("default")

    def add_cors_headers(self, response):
        """Add CORS headers to response"""
        response["Access-Control-Allow-Origin"] = "http://localhost:3000"
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Expose-Headers"] = "X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset"
        return response

    def __call__(self, request):
        # Record analytics for all requests
        if request.path.startswith("/api/"):
            self.record_api_request(request)

        # Skip rate limiting in development or for staff users
        if settings.DEBUG or (request.user.is_authenticated and request.user.is_staff):
            return self.get_response(request)
            
        if request.user.is_authenticated:
            key = get_user_ratelimit_key(request.user.id)
            daily_count = int(self.redis.get(key) or 0)
            
            # Check if user has exceeded their subscription limit
            if daily_count >= request.user.daily_request_limit:
                security_tracer.log_security_event(
                    "rate_limit.exceeded",
                    {
                        "limit_type": "daily",
                        "count": daily_count,
                        "limit": request.user.daily_request_limit,
                        "path": request.path
                    },
                    user=request.user,
                    ip=get_client_ip(request),
                    severity="WARNING"
                )
                response = JsonResponse(
                    {"error": "Daily API request limit exceeded for your subscription"},
                    status=429
                )
                response["X-RateLimit-Limit"] = request.user.daily_request_limit
                response["X-RateLimit-Remaining"] = 0
                response["X-RateLimit-Reset"] = int(time.time() + 86400)
                return self.add_cors_headers(response)
            
            usage = cache.get(key, {"count": 0, "reset_time": time.time() + 86400})

            # Get user's limit from their subscription
            limit = request.user.daily_request_limit

            # Check if limit reached
            if usage["count"] >= limit:
                remaining = int(usage["reset_time"] - time.time())
                if remaining <= 0:
                    # Reset if time expired
                    usage = {"count": 1, "reset_time": time.time() + 86400}
                    cache.set(key, usage, 86400)
                else:
                    # Return rate limit exceeded response
                    response = JsonResponse(
                        {"error": "Rate limit exceeded. Please upgrade your subscription for more requests."},
                        status=429,
                    )
                    response["X-RateLimit-Limit"] = limit
                    response["X-RateLimit-Remaining"] = 0
                    response["X-RateLimit-Reset"] = int(usage["reset_time"])
                    return self.add_cors_headers(response)

            # Increment usage counter
            usage["count"] += 1
            cache.set(key, usage, 86400)

            response = self.get_response(request)

            # Add rate limit headers
            response["X-RateLimit-Limit"] = limit
            response["X-RateLimit-Remaining"] = max(0, limit - usage["count"])
            response["X-RateLimit-Reset"] = int(usage["reset_time"])

            return self.add_cors_headers(response)

        # Get client IP address
        ip = get_client_ip(request)

        # Check if this is an API request
        if request.path.startswith("/api/"):
            # Get current usage stats
            key = get_ip_ratelimit_key(ip)
            usage = cache.get(key, {"count": 0, "reset_time": time.time() + 86400})

            # Check if limit reached
            limit = 100  # Set your daily limit for anonymous users
            if usage["count"] >= limit:
                remaining = int(usage["reset_time"] - time.time())
                if remaining <= 0:
                    # Reset if time expired
                    usage = {"count": 1, "reset_time": time.time() + 86400}
                    cache.set(key, usage, 86400)
                else:
                    # Return rate limit exceeded response
                    response = JsonResponse(
                        {"error": "Rate limit exceeded. Please try again later."},
                        status=429
                    )
                    response["X-RateLimit-Limit"] = limit
                    response["X-RateLimit-Remaining"] = 0
                    response["X-RateLimit-Reset"] = int(usage["reset_time"])
                    return self.add_cors_headers(response)

            # Increment usage counter
            usage["count"] += 1
            cache.set(key, usage, 86400)  # Store for 24 hours

            # Process the request
            response = self.get_response(request)

            # Add rate limit headers
            response["X-RateLimit-Limit"] = limit
            response["X-RateLimit-Remaining"] = max(0, limit - usage["count"])
            response["X-RateLimit-Reset"] = int(usage["reset_time"])

            return self.add_cors_headers(response)

        return self.get_response(request)

    def record_api_request(self, request):
        """Record API request analytics in Redis"""
        ip = get_client_ip(request)
        endpoint = request.path

        # Increment total request counter
        safe_incr(TOTAL_REQUESTS, 1)

        # Increment requests per endpoint
        endpoint_key = get_endpoint_key(endpoint)
        safe_incr(endpoint_key, 1)

        # Track unique IPs (using Redis Sets)
        self.redis.sadd(UNIQUE_IPS, ip)

        # Store hourly stats (using Redis Sorted Sets)
        hour_key = int(time.time() / 3600)  # Current hour timestamp
        self.redis.zincrby(HOURLY_STATS, 1, str(hour_key))

        # Store daily stats
        day_key = int(time.time() / 86400)  # Current day timestamp
        self.redis.zincrby(DAILY_STATS, 1, str(day_key))

        # Store method stats
        method_key = get_method_key(request.method)
        safe_incr(method_key, 1)

        # Optionally track user agent
        if "HTTP_USER_AGENT" in request.META:
            self.redis.zincrby(USER_AGENTS, 1, request.META["HTTP_USER_AGENT"])
