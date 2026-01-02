from django.core.management.base import BaseCommand
from experiments.testing import SampleTester
from experiments.strategies import StrategyRegistry
import os


class Command(BaseCommand):
    help = 'Test strategies on exported samples (filesystem) before DB testing'

    def add_arguments(self, parser):
        parser.add_argument('--samples-dir', type=str, default='decision_samples', help='Directory with samples')
        parser.add_argument('--strategy', type=str, help='Strategy to test')
        parser.add_argument('--compare-all', action='store_true', help='Compare all strategies')
        parser.add_argument('--show-failures', action='store_true', help='Show failed cases')
        parser.add_argument('--list-strategies', action='store_true', help='List available strategies')

    def handle(self, *args, **options):
        samples_dir = options['samples_dir']
        
        # List available strategies
        if options['list_strategies']:
            strategies = StrategyRegistry.list_names()
            self.stdout.write(self.style.SUCCESS("Available strategies:"))
            for name in strategies:
                self.stdout.write(f"  - {name}")
            return
        
        if not os.path.exists(samples_dir):
            self.stdout.write(self.style.ERROR(f"Directory not found: {samples_dir}"))
            self.stdout.write("Run 'python manage.py export_samples' first")
            return
        
        # Get all available strategies
        strategies_map = StrategyRegistry.get_all()
        
        if not strategies_map:
            self.stdout.write(self.style.ERROR("No strategies found!"))
            return
        
        tester = SampleTester(samples_dir)
        
        if options['compare_all']:
            # Test all strategies
            strategies = [cls() for cls in strategies_map.values()]
            results = tester.compare_strategies(strategies)
            
            self.stdout.write(self.style.WARNING("\n=== STRATEGY COMPARISON (Filesystem Test) ===\n"))
            for result in results:
                self.stdout.write(
                    f"{result['strategy']:25} | "
                    f"Success: {result['success_rate']:5.1f}% | "
                    f"{result['successful']}/{result['total']} passed"
                )
            
        else:
            # Test single strategy
            strategy_name = options.get('strategy')
            if not strategy_name:
                # Default to first available
                strategy_name = list(strategies_map.keys())[0]
                self.stdout.write(f"No strategy specified, using: {strategy_name}")
            
            if strategy_name not in strategies_map:
                self.stdout.write(self.style.ERROR(f"Unknown strategy: {strategy_name}"))
                self.stdout.write(f"Available: {', '.join(strategies_map.keys())}")
                return
            
            strategy = strategies_map[strategy_name]()
            result = tester.test_strategy(strategy)
            
            self.stdout.write(self.style.SUCCESS(
                f"\n{strategy.name} Test Results:\n"
                f"Success: {result['successful']}/{result['total']} ({result['success_rate']:.1f}%)\n"
                f"Failed:  {result['failed']}"
            ))
            
            # Show failures if requested
            if options['show_failures'] and result['failed'] > 0:
                failures = tester.get_failures(strategy, limit=10)
                self.stdout.write("\n" + self.style.WARNING("Sample Failures:"))
                for f in failures:
                    self.stdout.write(f"  {f.ada}: {f.error}")
        
        self.stdout.write(
            self.style.SUCCESS("\n✓ Filesystem testing complete. Ready for DB testing with 'run_experiment'")
        )
