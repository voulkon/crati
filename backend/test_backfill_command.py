#!/usr/bin/env python3
"""
Test script for the backfill_decision_entities_and_amounts management command.
Run this to test different scenarios.
"""

import os
import sys
import subprocess
from datetime import date, timedelta

def run_command(cmd_args, description):
    """Run a management command and display results."""
    print(f"\n🧪 Testing: {description}")
    print(f"Command: python manage.py backfill_decision_entities_and_amounts {cmd_args}")
    
    try:
        result = subprocess.run(
            f"python manage.py backfill_decision_entities_and_amounts {cmd_args}",
            shell=True,
            capture_output=True,
            text=True,
            cwd="/code"
        )
        
        if result.returncode == 0:
            print("✅ Success!")
            print(result.stdout)
        else:
            print("❌ Error!")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ Exception: {e}")

def main():
    print("🚀 Testing backfill_decision_entities_and_amounts command")
    
    # Test 1: Dry run for your specific dates
    run_command(
        "--start-date 2025-06-30 --end-date 2025-07-01 --dry-run",
        "Dry run for June 30 - July 1, 2025"
    )
    
    # Test 2: Check integrity (dry run)
    run_command(
        "--check-integrity --dry-run",
        "Integrity check (dry run)"
    )
    
    # Test 3: Process specific ADA (dry run)
    run_command(
        "--ada 9ΥΘΧΩ9Γ-1Μ6 --dry-run",
        "Process specific ADA (dry run)"
    )
    
    # Test 4: Help
    run_command(
        "--help",
        "Show help"
    )
    
    print("\n🎉 All tests completed!")
    print("\nTo run the actual backfill for your dates:")
    print("python manage.py backfill_decision_entities_and_amounts --start-date 2025-06-30 --end-date 2025-07-01")
    print("\nTo check integrity and backfill all missing data:")
    print("python manage.py backfill_decision_entities_and_amounts --check-integrity")

if __name__ == "__main__":
    main()
