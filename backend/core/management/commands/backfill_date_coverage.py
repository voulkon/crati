from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import transaction
from core.models.decisions import Decision
from core.models.import_jobs import DateCoverage
from django.utils import timezone

class Command(BaseCommand):
    help = 'Backfills the DateCoverage table with data from existing Decisions'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', 
                            help='Clear existing DateCoverage data before backfilling')

    def handle(self, *args, **options):
        start_time = timezone.now()
        self.stdout.write('Starting DateCoverage backfill...')
        
        if options['reset']:
            self.stdout.write('Clearing existing DateCoverage data...')
            DateCoverage.objects.all().delete()
        
        # First, handle organization coverage
        self.stdout.write('Processing organization coverage...')
        
        org_counts = Decision.objects.exclude(organization__isnull=True).values(
            'organization', 'issue_date__date'
        ).annotate(
            decision_count=Count('id')
        )
        
        with transaction.atomic():
            for item in org_counts:
                if not item['issue_date__date'] or not item['organization']:
                    continue
                    
                DateCoverage.objects.update_or_create(
                    date=item['issue_date__date'],
                    organization_id=item['organization'],
                    signer=None,
                    defaults={'decision_count': item['decision_count']}
                )
        
        self.stdout.write(f'Created/updated {len(org_counts)} organization coverage records')
        
        # Then handle signer coverage
        self.stdout.write('Processing signer coverage...')
        
        # This is more complex due to the many-to-many relationship
        # We'll use a raw SQL approach for efficiency
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    s.uid as signer_id,
                    d.issue_date::date as decision_date,
                    COUNT(DISTINCT d.id) as decision_count
                FROM 
                    core_decision d
                JOIN 
                    core_decision_signers ds ON d.id = ds.decision_id
                JOIN 
                    core_signer s ON ds.signer_id = s.uid
                WHERE 
                    d.issue_date IS NOT NULL
                GROUP BY 
                    s.uid, d.issue_date::date
            """)
            
            signer_rows = cursor.fetchall()
            
        with transaction.atomic():
            for signer_id, decision_date, decision_count in signer_rows:
                DateCoverage.objects.update_or_create(
                    date=decision_date,
                    organization=None,
                    signer_id=signer_id,
                    defaults={'decision_count': decision_count}
                )
        
        self.stdout.write(f'Created/updated {len(signer_rows)} signer coverage records')
        
        # Calculate runtime
        runtime = timezone.now() - start_time
        self.stdout.write(self.style.SUCCESS(
            f'DateCoverage backfill completed successfully in {runtime.total_seconds():.2f} seconds'
        ))