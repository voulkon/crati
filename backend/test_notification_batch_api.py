"""
Test script for Notification Batch API endpoints
Usage: python test_notification_batch_api.py
"""
import requests
import json
from typing import Optional

BASE_URL = "http://localhost:8000/api"
# Replace with your actual authentication token or session cookie
TOKEN = "your-auth-token-here"

class NotificationBatchAPITester:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def print_response(self, response: requests.Response, test_name: str):
        """Pretty print API response"""
        print(f"\n{'='*60}")
        print(f"Test: {test_name}")
        print(f"Status Code: {response.status_code}")
        print(f"{'='*60}")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
        print()
    
    def test_list_batches(self):
        """Test 1: List all notification batches"""
        response = requests.get(
            f"{self.base_url}/notifications/batches/",
            headers=self.headers
        )
        self.print_response(response, "List All Batches")
        return response
    
    def test_list_unread_batches(self):
        """Test 2: List unread batches"""
        response = requests.get(
            f"{self.base_url}/notifications/batches/?is_read=false",
            headers=self.headers
        )
        self.print_response(response, "List Unread Batches")
        return response
    
    def test_list_by_subscription(self, subscription_id: int):
        """Test 3: List batches filtered by subscription"""
        response = requests.get(
            f"{self.base_url}/notifications/batches/?subscription_id={subscription_id}",
            headers=self.headers
        )
        self.print_response(response, f"List Batches for Subscription {subscription_id}")
        return response
    
    def test_get_batch_detail(self, batch_id: int):
        """Test 4: Get specific batch details"""
        response = requests.get(
            f"{self.base_url}/notifications/batches/{batch_id}/",
            headers=self.headers
        )
        self.print_response(response, f"Get Batch {batch_id} Detail")
        return response
    
    def test_get_batch_decisions(self, batch_id: int, page: int = 1, page_size: int = 10):
        """Test 5: Get decisions in a batch"""
        response = requests.get(
            f"{self.base_url}/notifications/batches/{batch_id}/decisions/",
            params={"page": page, "page_size": page_size},
            headers=self.headers
        )
        self.print_response(response, f"Get Decisions in Batch {batch_id}")
        return response
    
    def test_mark_batch_read(self, batch_id: int):
        """Test 6: Mark batch as read"""
        response = requests.post(
            f"{self.base_url}/notifications/batches/{batch_id}/mark-read/",
            headers=self.headers
        )
        self.print_response(response, f"Mark Batch {batch_id} as Read")
        return response
    
    def test_dismiss_batch(self, batch_id: int):
        """Test 7: Dismiss batch"""
        response = requests.post(
            f"{self.base_url}/notifications/batches/{batch_id}/dismiss/",
            headers=self.headers
        )
        self.print_response(response, f"Dismiss Batch {batch_id}")
        return response
    
    def test_unread_count(self):
        """Test 8: Get unread batch count"""
        response = requests.get(
            f"{self.base_url}/notifications/batches/unread-count/",
            headers=self.headers
        )
        self.print_response(response, "Get Unread Batch Count")
        return response
    
    def test_create_subscription_with_operator(self):
        """Test 9: Create subscription with keyword_match_operator"""
        data = {
            "organization_uid": "99206510",
            "keywords": ["διαγωνισμός", "σύμβαση"],
            "keyword_match_operator": "OR",
            "alias": "Test subscription with OR operator",
            "is_active": True,
            "check_frequency": "daily"
        }
        response = requests.post(
            f"{self.base_url}/notifications/subscriptions/",
            headers=self.headers,
            json=data
        )
        self.print_response(response, "Create Subscription with Keyword Operator")
        return response
    
    def test_update_keyword_operator(self, subscription_id: int):
        """Test 10: Update subscription keyword operator"""
        data = {
            "keyword_match_operator": "AND"
        }
        response = requests.patch(
            f"{self.base_url}/notifications/subscriptions/{subscription_id}/",
            headers=self.headers,
            json=data
        )
        self.print_response(response, f"Update Subscription {subscription_id} Keyword Operator")
        return response
    
    def run_all_tests(self, batch_id: Optional[int] = None, subscription_id: Optional[int] = None):
        """Run all tests"""
        print("\n" + "="*60)
        print("Starting Notification Batch API Tests")
        print("="*60)
        
        # Test 1: List batches
        self.test_list_batches()
        
        # Test 2: List unread batches
        self.test_list_unread_batches()
        
        # Test 3: Filter by subscription (if subscription_id provided)
        if subscription_id:
            self.test_list_by_subscription(subscription_id)
        
        # Test 4-7: Batch-specific tests (if batch_id provided)
        if batch_id:
            self.test_get_batch_detail(batch_id)
            self.test_get_batch_decisions(batch_id)
            self.test_mark_batch_read(batch_id)
            self.test_dismiss_batch(batch_id)
        
        # Test 8: Unread count
        self.test_unread_count()
        
        # Test 9: Create subscription with keyword operator
        # Uncomment to test (will create a new subscription)
        # self.test_create_subscription_with_operator()
        
        # Test 10: Update keyword operator (if subscription_id provided)
        # Uncomment to test (will modify existing subscription)
        # if subscription_id:
        #     self.test_update_keyword_operator(subscription_id)
        
        print("\n" + "="*60)
        print("All tests completed!")
        print("="*60)


if __name__ == "__main__":
    # Initialize tester
    tester = NotificationBatchAPITester(BASE_URL, TOKEN)
    
    # Option 1: Run all tests (requires batch_id and subscription_id)
    # Replace with actual IDs from your database
    BATCH_ID = 1
    SUBSCRIPTION_ID = 1
    
    # To test specific endpoints without actual IDs, comment out the run_all_tests
    # and call individual test methods
    
    print("\nNote: Update TOKEN, BATCH_ID, and SUBSCRIPTION_ID with actual values")
    print("before running tests.\n")
    
    # Uncomment to run tests:
    # tester.run_all_tests(batch_id=BATCH_ID, subscription_id=SUBSCRIPTION_ID)
    
    # Or run individual tests:
    tester.test_list_batches()
    tester.test_list_unread_batches()
    tester.test_unread_count()
