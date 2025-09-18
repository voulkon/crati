from django.core.management.base import BaseCommand
from django.db import transaction
from core.models.decisions import Decision
from core.models.entities import DecisionAmountField, DecisionEntityRelationship
from tqdm import tqdm  # For progress bar; install with pip install tqdm

class Command(BaseCommand):
    help = 'Backfill associated_relationship in DecisionAmountField based on path matching'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for processing decisions')

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        decisions = Decision.objects.all().order_by('id')  # Process in order; filter if needed (e.g., .filter(amount_fields__isnull=False))

        total = decisions.count()
        self.stdout.write(self.style.SUCCESS(f'Backfilling for {total} decisions...'))

        with transaction.atomic():  # Wrap in transaction for efficiency/rollback
            for i in tqdm(range(0, total, batch_size)):
                batch = decisions[i:i + batch_size]
                self.process_batch(batch)

        self.stdout.write(self.style.SUCCESS('Backfill complete!'))

    def process_batch(self, decisions_batch):
        # Prefetch relationships and amounts to minimize queries
        decisions_batch = decisions_batch.prefetch_related(
            'entity_relationships',  # Prefetch DecisionEntityRelationship
            'amount_fields'          # Prefetch DecisionAmountField (assuming related_name='amount_fields' on Decision)
        )

        for decision in decisions_batch:
            # Get relationships and amounts for this decision
            relationships = decision.entity_relationships.all()
            amounts = decision.amount_fields.all()

            # Create dict of path to relationship for quick lookup
            path_to_rel = {rel.parent_key_path: rel for rel in relationships}

            for amount in amounts:
                if amount.associated_relationship_id:  # Skip if already set
                    continue

                # Find matching relationship (e.g., if amount path starts with rel path)
                matching_rel = None
                for rel_path, rel in path_to_rel.items():
                    # Extract container path from relationship (e.g., "sponsor[0].sponsorAFMName" → "sponsor[0]")
                    rel_container = rel_path.rsplit('.', 1)[0] if '.' in rel_path else rel_path
                    
                    # Extract container path from amount (e.g., "sponsor[0].expenseAmount" → "sponsor[0]" or use as-is for "sponsor[0]")
                    amount_container = amount.parent_key_path.rsplit('.', 1)[0] if '.' in amount.parent_key_path else amount.parent_key_path
                    
                    # Match if they're in the same container AND the amount is a specific field (not a container)
                    if rel_container == amount_container and '.' in amount.parent_key_path:
                        matching_rel = rel
                        break

                if matching_rel:
                    amount.associated_relationship = matching_rel
                    amount.save(update_fields=['associated_relationship'])