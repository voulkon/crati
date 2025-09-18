from django.core.management.base import BaseCommand
from django.core.cache import cache
from django_redis import get_redis_connection
from datetime import datetime
import time
import json


class Command(BaseCommand):
    help = "Persist Redis analytics data to database"

    def handle(self, *args, **options):
        from api.models import APIAnalytics, DailyTraffic, EndpointStats

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

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully persisted analytics data (ID: {analytics.id})"
            )
        )
