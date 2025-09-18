from users.models import CustomUser
from django.db import models


class APIRequest(models.Model):
    ip_address = models.GenericIPAddressField()
    path = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    user = models.ForeignKey(
        "users.CustomUser", null=True, blank=True, on_delete=models.SET_NULL
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["ip_address"]),
            models.Index(fields=["timestamp"]),
        ]


class APIAnalytics(models.Model):
    total_requests = models.PositiveIntegerField()
    unique_ips = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "API Analytics"
        verbose_name_plural = "API Analytics"

    def __str__(self):
        return f"Analytics {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    @property
    def requests_per_ip_ratio(self):
        """Calculate the average requests per IP"""
        if self.unique_ips > 0:
            return round(self.total_requests / self.unique_ips, 2)
        return 0

    @property
    def pattern_signature(self):
        """Return a string signature for this pattern"""
        return f"{self.total_requests}:{self.unique_ips}"

    @property
    def is_suspicious_pattern(self):
        """Check if this represents a suspicious pattern"""
        # 51/12 pattern
        if self.total_requests == 51 and self.unique_ips == 12:
            return True
        # Perfect 1:1 ratio (each IP makes exactly 1 request)
        if self.total_requests == self.unique_ips:
            return True
        # Exact integer ratios might be suspicious
        if self.unique_ips > 0 and self.total_requests % self.unique_ips == 0:
            ratio = self.total_requests // self.unique_ips
            if ratio > 10:  # Each IP making more than 10 requests in exact numbers
                return True
        return False

    @property
    def pattern_analysis(self):
        """Return human-readable pattern analysis"""
        if self.total_requests == 51 and self.unique_ips == 12:
            return "🔍 51/12 SUSPICIOUS PATTERN"
        elif self.total_requests == self.unique_ips:
            return "⚠️ 1:1 RATIO (each IP = 1 request)"
        elif self.unique_ips > 0 and self.total_requests % self.unique_ips == 0:
            ratio = self.total_requests // self.unique_ips
            return f"📊 EXACT {ratio}:1 RATIO"
        elif self.requests_per_ip_ratio > 20:
            return "🔥 HIGH ACTIVITY PER IP"
        else:
            return "✅ Normal pattern"

    def get_top_endpoints(self, limit=5):
        """Get the top endpoints for this analytics record"""
        return self.endpoints.order_by("-count")[:limit]

    @classmethod
    def get_pattern_frequency(cls, days=30):
        """Get frequency of different patterns over the last N days"""
        from collections import Counter
        from datetime import datetime, timedelta

        recent_analytics = cls.objects.filter(
            timestamp__gte=datetime.now() - timedelta(days=days)
        )

        patterns = Counter()
        for analytics in recent_analytics:
            patterns[analytics.pattern_signature] += 1

        return patterns.most_common()


class EndpointStats(models.Model):
    analytics = models.ForeignKey(
        APIAnalytics, on_delete=models.CASCADE, related_name="endpoints"
    )
    endpoint = models.CharField(max_length=255)
    count = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Endpoint Stat"
        verbose_name_plural = "Endpoint Stats"

    def __str__(self):
        return f"{self.endpoint}: {self.count}"


class DailyTraffic(models.Model):
    analytics = models.ForeignKey(
        APIAnalytics, on_delete=models.CASCADE, related_name="daily_traffic"
    )
    date = models.DateField()
    count = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Daily Traffic"
        verbose_name_plural = "Daily Traffic"

    def __str__(self):
        return f"{self.date}: {self.count}"
