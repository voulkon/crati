from django.core.management.base import BaseCommand
from core.models.decisions import Decision
from core.models.entities import DecisionAmountField, DecisionEntityRelationship
from django.db import transaction
import json
from typing import Dict, Any, List

class Command(BaseCommand):
    help = 'Back-fill DecisionAmountField with amounts from existing decisions'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=100)

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        total = Decision.objects.exclude(extra_field_values_json__isnull=True).count()
        self.stdout.write(f"📊 Back-filling {total:,} decisions...")

        processed = 0
        for i in range(0, total, batch_size):
            batch = Decision.objects.exclude(extra_field_values_json__isnull=True)[i:i + batch_size]
            with transaction.atomic():
                for decision in batch:
                    self.extract_and_save_amounts(decision)
                    processed += 1
            self.stdout.write(f"Processed {processed:,}/{total:,}")
        self.stdout.write(self.style.SUCCESS("✅ Back-fill complete!"))

    def extract_and_save_amounts(self, decision: Decision):
        amount_patterns = self.find_amount_patterns_in_data(decision.extra_field_values_json, decision.ada)
        for pattern in amount_patterns:
            amount_info = pattern['amount_info']
            for i, amount in enumerate(amount_info['amounts']):
                DecisionAmountField.objects.get_or_create(
                    decision=decision,
                    parent_key_path=pattern['parent_path'],
                    source_field_name=amount_info['fields_found'][i],
                    defaults={
                        'amount': amount,
                        'currency': amount_info['currencies'][i] if i < len(amount_info['currencies']) else 'EUR',
                        'structure_type': amount_info['structure_types'][i],
                        'raw_context': pattern['raw_data']
                    }
                )
                # Optional: If entity-linked, update DecisionEntityRelationship
                if amount_info['related_afms']:
                    rel = DecisionEntityRelationship.objects.filter(
                        decision=decision,
                        parent_key_path=pattern['parent_path']
                    ).first()
                    if rel:
                        rel.amount = amount
                        rel.currency = amount_info['currencies'][i] or 'EUR'
                        rel.amount_source_field = amount_info['fields_found'][i]
                        rel.amount_structure_type = amount_info['structure_types'][i]
                        rel.save()

    # Adapted from explore_amount_patterns.py
    def find_amount_patterns_in_data(self, data: Any, decision_ada: str, parent_path: str = "") -> List[Dict]:
        patterns = []
        if isinstance(data, dict):
            amount_info = self.detect_amounts_in_dict(data, parent_path)
            if amount_info:
                patterns.append({'parent_path': parent_path or 'root', 'amount_info': amount_info, 'raw_data': data})
            for key, value in data.items():
                new_path = f"{parent_path}.{key}" if parent_path else key
                patterns.extend(self.find_amount_patterns_in_data(value, decision_ada, new_path))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{parent_path}[{i}]" if parent_path else f"[{i}]"
                patterns.extend(self.find_amount_patterns_in_data(item, decision_ada, new_path))
        return patterns

    # Adapted from explore_amount_patterns.py
    def detect_amounts_in_dict(self, data: Dict[str, Any], parent_path: str) -> Dict[str, Any]:
        amount_info = {
            'fields_found': [],
            'structure_types': [],
            'amounts': [],
            'currencies': [],
            'related_afms': []
        }
        amount_keywords = ['amount', 'expenseAmount', 'awardAmount', 'amountWithVAT', 'value', 'cost', 'price', 'sum', 'total', 'ποσο', 'αξια']
        for key, value in data.items():
            key_lower = key.lower()
            if any(amt_term in key_lower for amt_term in amount_keywords):
                amount_info['fields_found'].append(key)
                if isinstance(value, dict):
                    amount_info['structure_types'].append('nested_object')
                    amt = value.get('amount')
                    if amt is not None:
                        try:
                            amount_info['amounts'].append(float(amt))
                        except (ValueError, TypeError):
                            pass
                    curr = value.get('currency')
                    if curr:
                        amount_info['currencies'].append(curr)
                elif isinstance(value, (int, float)):
                    amount_info['structure_types'].append('plain_numeric')
                    amount_info['amounts'].append(float(value))
                else:
                    amount_info['structure_types'].append('other')
                    try:
                        if value is not None:
                            numeric_value = float(str(value).replace(',', ''))
                            amount_info['amounts'].append(numeric_value)
                    except (ValueError, TypeError):
                        pass
        for key, value in data.items():
            if 'afm' in key.lower() and isinstance(value, str):
                amount_info['related_afms'].append(value)
            elif isinstance(value, dict) and 'afm' in value:
                amount_info['related_afms'].append(value['afm'])
        return amount_info if amount_info['fields_found'] else {}