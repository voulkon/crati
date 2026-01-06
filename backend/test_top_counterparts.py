"""
Test script for organization top counterparts endpoint.

This script tests the new endpoint without requiring a full frontend.
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'diavgeia_project.settings')
django.setup()

from datetime import datetime, timedelta
from core.models.organizations import Organization
from core.services.financial_calculation_service import FinancialCalculationService

def test_top_counterparts():
    """Test the get_top_counterparts_for_organization method."""
    
    # Get a sample organization
    try:
        org = Organization.objects.first()
        if not org:
            print("❌ No organizations found in database")
            return
        
        print(f"✅ Testing with organization: {org.uid} - {org.label}")
    except Exception as e:
        print(f"❌ Error getting organization: {e}")
        return
    
    # Test date range (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    print(f"\n📅 Date range: {start_date.date()} to {end_date.date()}")
    
    # Test the service method
    financial_service = FinancialCalculationService()
    
    print("\n🔍 Testing get_top_counterparts_for_organization()...")
    
    try:
        result = financial_service.get_top_counterparts_for_organization(
            organization=org,
            start_date=start_date,
            end_date=end_date,
            limit=5,
            offset=0
        )
        
        print(f"\n✅ Success!")
        print(f"   Total entities found: {result['total_count']}")
        print(f"   Has more results: {result['has_more']}")
        print(f"\n   Top {len(result['results'])} counterparts:")
        
        for i, entity in enumerate(result['results'], 1):
            print(f"      {i}. AFM: {entity['entity__afm']}")
            print(f"         Name: {entity['entity__name']}")
            print(f"         Type: {entity['entity__entity_type']}")
            print(f"         Total: €{entity['total_amount']:,.2f}")
            print(f"         Decisions: {entity['decision_count']}")
            print()
        
        # Test pagination
        if result['has_more']:
            print("\n📄 Testing pagination (offset=5)...")
            result_page2 = financial_service.get_top_counterparts_for_organization(
                organization=org,
                start_date=start_date,
                end_date=end_date,
                limit=5,
                offset=5
            )
            
            print(f"   Page 2 results: {len(result_page2['results'])} entities")
            if result_page2['results']:
                print(f"   First entity on page 2: {result_page2['results'][0]['entity__afm']}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Organization Top Counterparts Endpoint")
    print("=" * 60)
    test_top_counterparts()
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
