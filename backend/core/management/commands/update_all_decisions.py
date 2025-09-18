from django.core.management.base import BaseCommand
from django.db import transaction
from core.models.decisions import Decision
from core.fetchers.diavgeia_fetcher import DiavgeiaFetcher
from core.importers.decisions import DecisionImporter
import json
import time
import os
from pathlib import Path
from loguru import logger

class Command(BaseCommand):
    help = 'Update all decisions with complete data using nuclear models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of decisions to process in each batch'
        )
        parser.add_argument(
            '--max-decisions',
            type=int,
            help='Maximum number of decisions to process (for testing)'
        )
        parser.add_argument(
            '--delay-seconds',
            type=float,
            default=0.1,
            help='Delay between API requests'
        )
        parser.add_argument(
            '--start-from-ada',
            type=str,
            help='Start processing from this specific ADA (for resuming)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating'
        )
        parser.add_argument(
            '--force-ada',
            type=str,
            help='Process a specific ADA (will fetch fresh even if not in DB)'
        )
        parser.add_argument(
            '--resume-file',
            type=str,
            default='./update_progress.txt',
            help='File to store progress for resuming (default: ./update_progress.txt)'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        max_decisions = options.get('max_decisions')
        delay = options['delay_seconds']
        start_from_ada = options.get('start_from_ada')
        dry_run = options['dry_run']
        resume_file = options.get('resume_file', './update_progress.txt')
        
        self.fetcher = DiavgeiaFetcher()
        self.importer = DecisionImporter()
        
        # Get all decisions to update
        queryset = Decision.objects.all().order_by('ada')
        
        if options.get('force_ada'):
            ada = options['force_ada']
            self.stdout.write(f"🎯 Force processing ADA: {ada}")
            
            # Fetch fresh data
            fresh_dto = self.fetcher.fetch_a_decision(ada)
            if not fresh_dto:
                self.stdout.write(f"❌ Could not fetch {ada}")
                return
            
            new_data = self.importer._extract_promoted_fields(fresh_dto)
            self.stdout.write(f"📊 Nuclear extraction result:")
            self.stdout.write(json.dumps(new_data.get('extra_field_values_json', {}), indent=2, ensure_ascii=False))
            
            self.stdout.write(f"🎉 Nuclear models captured {len(new_data.get('extra_field_values_json', {}))} fields!")
            return
        
        if start_from_ada:
            queryset = queryset.filter(ada__gte=start_from_ada)
            self.stdout.write(f"📍 Starting from ADA: {start_from_ada}")
        
        total_decisions = queryset.count()
        if max_decisions:
            total_decisions = min(total_decisions, max_decisions)
            self.stdout.write(f"🔄 Processing {total_decisions:,} decisions (limited for testing)")
        else:
            self.stdout.write(f"🔄 Processing ALL {total_decisions:,} decisions")
        
        if dry_run:
            self.stdout.write("🧪 DRY RUN MODE - No actual updates will be made")
        
        processed = 0
        updated_count = 0
        unchanged_count = 0
        errors = []
        field_changes = {}
        
        # Add auto-resume logic at the start:
        if not start_from_ada and not options.get('force_ada'):
            progress = self._load_progress(resume_file)
            if progress:
                self.stdout.write(f"📁 Found previous progress file: {resume_file}")
                self.stdout.write(f"   Last ADA: {progress.get('LAST_ADA')}")
                self.stdout.write(f"   Processed: {progress.get('PROCESSED')}/{progress.get('TOTAL')}")
                
                resume_prompt = input("Resume from last position? (y/N): ")
                if resume_prompt.lower().startswith('y'):
                    start_from_ada = progress.get('LAST_ADA')
                    self.stdout.write(f"🔄 Resuming from ADA: {start_from_ada}")
        
        for i in range(0, total_decisions, batch_size):
            batch = list(queryset[i:i + batch_size])
            
            self.stdout.write(f"\n📦 Processing batch {i//batch_size + 1} ({len(batch)} decisions)")
            
            for decision in batch:
                try:
                    # Store original data for comparison
                    original_extra_fields = decision.extra_field_values_json.copy() if decision.extra_field_values_json else {}
                    
                    # Fetch fresh data from API
                    fresh_dto = self.fetcher.fetch_a_decision(decision.ada)
                    
                    if not fresh_dto:
                        errors.append(f"Failed to fetch {decision.ada}")
                        continue
                    
                    # Extract new data with nuclear models
                    new_data = self.importer._extract_promoted_fields(fresh_dto)
                    new_extra_fields = new_data.get('extra_field_values_json', {})
                    
                    # Compare data
                    if new_extra_fields != original_extra_fields:
                        # Track what fields changed
                        new_fields = set(new_extra_fields.keys()) - set(original_extra_fields.keys())
                        for field in new_fields:
                            field_changes[field] = field_changes.get(field, 0) + 1
                        
                        if not dry_run:
                            # Update the decision
                            with transaction.atomic():
                                for field, value in new_data.items():
                                    if hasattr(decision, field):
                                        setattr(decision, field, value)
                                decision.save()
                        
                        updated_count += 1
                        
                        # Show sample of changes (first 10)
                        if updated_count <= 10:
                            self.stdout.write(f"📝 Updated {decision.ada}:")
                            self.stdout.write(f"   Old fields: {len(original_extra_fields)}")
                            self.stdout.write(f"   New fields: {len(new_extra_fields)}")
                            if new_fields:
                                self.stdout.write(f"   Added: {', '.join(sorted(new_fields))}")
                    else:
                        unchanged_count += 1
                    
                    processed += 1
                    
                    # Progress update
                    if processed % 100 == 0:
                        self.stdout.write(f"📊 Progress: {processed}/{total_decisions} ({processed/total_decisions*100:.1f}%)")
                        self.stdout.write(f"   Updated: {updated_count}, Unchanged: {unchanged_count}, Errors: {len(errors)}")
                    
                    # 💾 Save progress every 100 decisions
                    if processed % 100 == 0:
                        self._save_progress(decision.ada, processed, total_decisions, resume_file)
                        self.stdout.write(f"💾 Progress saved to {resume_file}")
                    
                    # Be nice to the API
                    if delay > 0:
                        time.sleep(delay)
                
                except Exception as e:
                    error_msg = f"Error processing {decision.ada}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
        
        # Final summary
        self.stdout.write(f"\n🎯 UPDATE COMPLETE!")
        self.stdout.write(f"📊 Total processed: {processed:,}")
        self.stdout.write(f"📊 Updated: {updated_count:,}")
        self.stdout.write(f"📊 Unchanged: {unchanged_count:,}")
        self.stdout.write(f"📊 Errors: {len(errors)}")
        
        if field_changes:
            self.stdout.write(f"\n📈 NEW FIELDS DISCOVERED:")
            sorted_fields = sorted(field_changes.items(), key=lambda x: x[1], reverse=True)
            for field, count in sorted_fields[:20]:  # Top 20 most common new fields
                self.stdout.write(f"  • {field}: {count:,} decisions")
            
            if len(sorted_fields) > 20:
                self.stdout.write(f"  ... and {len(sorted_fields) - 20} more fields")
        
        if errors:
            self.stdout.write(f"\n❌ ERRORS (first 10):")
            for error in errors[:10]:
                self.stdout.write(f"  • {error}")
            if len(errors) > 10:
                self.stdout.write(f"  ... and {len(errors) - 10} more errors")
        
        percentage_updated = (updated_count / processed * 100) if processed > 0 else 0
        self.stdout.write(f"\n🎉 {percentage_updated:.1f}% of decisions had data updates!")
    
    def _save_progress(self, ada, processed, total, resume_file):
        """Save current progress to file for resuming."""
        try:
            with open(resume_file, 'w') as f:
                f.write(f"LAST_ADA={ada}\n")
                f.write(f"PROCESSED={processed}\n")
                f.write(f"TOTAL={total}\n")
                f.write(f"TIMESTAMP={time.time()}\n")
        except Exception as e:
            logger.warning(f"Could not save progress: {e}")

    def _load_progress(self, resume_file):
        """Load progress from file."""
        if not os.path.exists(resume_file):
            return None
        
        try:
            progress = {}
            with open(resume_file, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        progress[key] = value
            return progress
        except Exception as e:
            logger.warning(f"Could not load progress: {e}")
            return None