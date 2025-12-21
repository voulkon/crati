#!/usr/bin/env python3
"""
Test script to verify Loki logging integration is working
"""
import requests
import time
import json
from datetime import datetime

def test_loki_health():
    """Test if Loki is running and accessible"""
    try:
        response = requests.get("http://localhost:3100/ready", timeout=5)
        if response.status_code == 200:
            print("✅ Loki is ready and accessible")
            return True
        else:
            print(f"❌ Loki returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to Loki: {e}")
        return False

def test_loki_query():
    """Test if we can query logs from Loki"""
    try:
        # Query for logs from the last hour
        query = '{service_name="diavgeia-backend"}'
        params = {
            'query': query,
            'limit': 10
        }
        
        response = requests.get("http://localhost:3100/loki/api/v1/query", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data', {}).get('result'):
                print(f"✅ Found {len(data['data']['result'])} log streams in Loki")
                for stream in data['data']['result'][:3]:  # Show first 3 streams
                    print(f"  - Stream: {stream.get('stream', {})}")
                    if stream.get('values'):
                        print(f"    Sample log: {stream['values'][0][1]}")
                return True
            else:
                print("ℹ️  No logs found in Loki yet (this is normal if services just started)")
                return True
        else:
            print(f"❌ Loki query failed with status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot query Loki: {e}")
        return False

def test_grafana_health():
    """Test if Grafana is running"""
    try:
        response = requests.get("http://localhost:3000/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Grafana is ready and accessible")
            print("   URL: http://localhost:3000")
            print("   Login: admin / admin")
            return True
        else:
            print(f"❌ Grafana returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to Grafana: {e}")
        return False

def main():
    print("🧪 Testing Loki Logging Integration")
    print("=" * 50)
    
    # Test Loki
    print("\n1. Testing Loki service...")
    loki_healthy = test_loki_health()
    
    if loki_healthy:
        print("\n2. Testing Loki query...")
        query_works = test_loki_query()
    
    # Test Grafana
    print("\n3. Testing Grafana service...")
    grafana_healthy = test_grafana_health()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"   Loki Health: {'✅' if loki_healthy else '❌'}")
    print(f"   Loki Query:  {'✅' if query_works else '❌'}")
    print(f"   Grafana:     {'✅' if grafana_healthy else '❌'}")
    
    if loki_healthy and grafana_healthy:
        print("\n🎉 Logging stack is ready!")
        print("\nNext steps:")
        print("1. Start your Django services: docker-compose up -d backend worker")
        print("2. Generate some logs (run your application)")
        print("3. Visit http://localhost:3000 to see logs in Grafana")
        print("4. Use the test command: python manage.py test_loki_logging")
    else:
        print("\n⚠️  Some services are not ready. Please check:")
        print("- Docker containers are running: docker-compose ps")
        print("- Services are healthy: docker-compose logs [service-name]")

if __name__ == "__main__":
    main()