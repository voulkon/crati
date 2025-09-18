from django.core.management.base import BaseCommand
from api.models import APIAnalytics
from datetime import datetime, timedelta
from collections import Counter


class Command(BaseCommand):
    help = "Quick analysis of the 51/12 pattern and other suspicious activities"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days to analyze (default: 30)",
        )
        parser.add_argument(
            "--pattern", type=str, help='Specific pattern to analyze (e.g., "51:12")'
        )

    def handle(self, *args, **options):
        days = options["days"]
        specific_pattern = options.get("pattern")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🔍 INVESTIGATING API ANALYTICS PATTERNS (Last {days} days)"
            )
        )
        self.stdout.write("=" * 60)

        # Get recent data
        recent_analytics = APIAnalytics.objects.filter(
            timestamp__gte=datetime.now() - timedelta(days=days)
        ).order_by("-timestamp")

        if not recent_analytics.exists():
            self.stdout.write(
                self.style.WARNING(
                    "❌ No analytics data found. Has the persist_analytics command been run?"
                )
            )
            return

        # Pattern frequency analysis
        patterns = Counter()
        suspicious_days = []

        for analytics in recent_analytics:
            pattern = analytics.pattern_signature
            patterns[pattern] += 1

            if analytics.is_suspicious_pattern:
                suspicious_days.append(
                    {
                        "date": analytics.timestamp.date(),
                        "pattern": pattern,
                        "analysis": analytics.pattern_analysis,
                        "top_endpoint": analytics.get_top_endpoints(1).first(),
                    }
                )

        # Display results
        self.stdout.write(f"\n📊 PATTERN FREQUENCY ANALYSIS:")
        self.stdout.write("-" * 40)
        for pattern, count in patterns.most_common(10):
            percentage = (count / len(recent_analytics)) * 100
            indicator = (
                "🔍" if pattern == "51:12" else "📊" if count > days * 0.8 else "✅"
            )
            self.stdout.write(
                f"{indicator} {pattern:<10} | {count:>3} days | {percentage:>5.1f}%"
            )

        # 51:12 specific analysis
        pattern_51_12_count = patterns.get("51:12", 0)
        if pattern_51_12_count > 0:
            percentage = (pattern_51_12_count / len(recent_analytics)) * 100
            self.stdout.write(f"\n🎯 51/12 PATTERN ANALYSIS:")
            self.stdout.write("-" * 40)
            self.stdout.write(
                f"Occurrences: {pattern_51_12_count} out of {len(recent_analytics)} days"
            )
            self.stdout.write(f"Frequency: {percentage:.1f}%")

            if percentage > 50:
                self.stdout.write(
                    self.style.ERROR(
                        "🚨 CRITICAL: Very high frequency! Likely automated traffic."
                    )
                )
            elif percentage > 20:
                self.stdout.write(
                    self.style.WARNING(
                        "⚠️  WARNING: Moderate frequency. Investigation recommended."
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS("✅ NORMAL: Low frequency."))

        # Suspicious days details
        if suspicious_days:
            self.stdout.write(f"\n🚨 SUSPICIOUS DAYS FOUND: {len(suspicious_days)}")
            self.stdout.write("-" * 40)
            for day in suspicious_days[:10]:  # Show last 10
                endpoint_info = (
                    f" | Top: {day['top_endpoint'].endpoint}"
                    if day["top_endpoint"]
                    else ""
                )
                self.stdout.write(
                    f"{day['date']} | {day['pattern']} | {day['analysis']}{endpoint_info}"
                )

        # Specific pattern analysis
        if specific_pattern:
            self.stdout.write(f"\n🔍 ANALYZING SPECIFIC PATTERN: {specific_pattern}")
            self.stdout.write("-" * 40)

            pattern_analytics = recent_analytics.filter(
                total_requests=int(specific_pattern.split(":")[0]),
                unique_ips=int(specific_pattern.split(":")[1]),
            )

            if pattern_analytics.exists():
                endpoint_counts = Counter()
                for analytics in pattern_analytics:
                    for endpoint_stat in analytics.endpoints.all():
                        endpoint_counts[endpoint_stat.endpoint] += endpoint_stat.count

                self.stdout.write(f"Found {pattern_analytics.count()} occurrences:")
                for analytics in pattern_analytics[:5]:
                    self.stdout.write(f"  • {analytics.timestamp.date()}")

                self.stdout.write(f"\nTop endpoints for {specific_pattern} pattern:")
                for endpoint, total_count in endpoint_counts.most_common(5):
                    self.stdout.write(f"  • {endpoint}: {total_count} total requests")
            else:
                self.stdout.write(
                    f"❌ No occurrences of {specific_pattern} pattern found."
                )

        # Recommendations
        self.stdout.write(f"\n💡 RECOMMENDATIONS:")
        self.stdout.write("-" * 40)

        if pattern_51_12_count > days * 0.5:
            self.stdout.write("1. 🔥 URGENT: Check nginx logs for 51/12 pattern days")
            self.stdout.write(
                "2. 🔍 Investigate IP addresses involved in these patterns"
            )
            self.stdout.write("3. 🛡️  Consider implementing stricter rate limiting")
        else:
            self.stdout.write("1. ✅ Pattern frequency appears normal")
            self.stdout.write("2. 📊 Continue monitoring for changes")

        self.stdout.write(
            "4. 🌐 Visit /api/admin/analytics/patterns/ for detailed web analysis"
        )
        self.stdout.write(
            '5. 🔧 Run: python manage.py investigate_patterns --pattern="51:12" for specific analysis'
        )

        self.stdout.write(
            f"\n✅ Analysis complete! Check the admin interface for more details."
        )
