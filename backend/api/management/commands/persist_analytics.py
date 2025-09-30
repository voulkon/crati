from django.core.management.base import BaseCommand
from django.core.cache import cache
from django_redis import get_redis_connection
from datetime import datetime
import time
import json


class Command(BaseCommand):
    help = "Persist Redis analytics data to database"

    def handle(self, *args, **options):
        from api.models import APIAnalytics, DailyTraffic, EndpointStats, IPJourney
        from api.redis_keys import get_ip_endpoints_key

        redis = get_redis_connection("default")

        # Create a new analytics record
        analytics = APIAnalytics.objects.create(
            total_requests=cache.get("stats:total_requests", 0),
            unique_ips=redis.scard("stats:unique_ips"),
            timestamp=datetime.now(),
        )

        # Persist endpoint stats
        endpoint_keys = redis.keys("stats:endpoint:*")
        for key in endpoint_keys:
            endpoint = key.decode("utf-8").replace("stats:endpoint:", "")
            count = int(cache.get(f"stats:endpoint:{endpoint}", 0))
            EndpointStats.objects.create(
                analytics=analytics, endpoint=endpoint, count=count
            )

        # Persist daily traffic
        daily_data = redis.zrange("stats:daily", 0, -1, withscores=True)
        for day_key, count in daily_data:
            day = datetime.fromtimestamp(int(day_key.decode("utf-8")) * 86400)
            DailyTraffic.objects.create(
                analytics=analytics, date=day.date(), count=int(count)
            )

        # Persist IP journey data
        unique_ips = redis.smembers("stats:unique_ips")
        ip_count = 0
        for ip_bytes in unique_ips:
            ip = ip_bytes.decode('utf-8')
            ip_endpoints_key = get_ip_endpoints_key(ip)
            endpoints = redis.smembers(ip_endpoints_key)
            
            if endpoints:
                endpoint_list = sorted([e.decode('utf-8') for e in endpoints])
                IPJourney.objects.create(
                    analytics=analytics,
                    ip_address=ip,
                    endpoints_visited=endpoint_list,
                    journey_length=len(endpoint_list)
                )
                ip_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully persisted analytics data (ID: {analytics.id})\n"
                f"  - {len(endpoint_keys)} endpoints\n"
                f"  - {len(daily_data)} days of traffic\n"
                f"  - {ip_count} IP journeys"
            )
        )
