#!/usr/bin/env python3
"""
Test script for the cloud API
"""

import requests
import json

# Cloud API URL
API_BASE_URL = "https://smart-order-router.onrender.com"

def test_api():
    """Test the cloud API endpoints"""
    
    print("🧪 Testing Cloud API...")
    print(f"API URL: {API_BASE_URL}")
    print("-" * 50)
    
    # Test 1: Health check
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Health check: PASSED")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check: FAILED ({response.status_code})")
    except Exception as e:
        print(f"❌ Health check: ERROR - {e}")
    
    print()
    
    # Test 2: Prices endpoint
    print("2. Testing prices endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/prices/BTC/USDT", timeout=10)
        if response.status_code == 200:
            print("✅ Prices endpoint: PASSED")
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Prices endpoint: FAILED ({response.status_code})")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Prices endpoint: ERROR - {e}")
    
    print()
    
    # Test 3: System stats
    print("3. Testing system stats endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/system/stats", timeout=10)
        if response.status_code == 200:
            print("✅ System stats: PASSED")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ System stats: FAILED ({response.status_code})")
    except Exception as e:
        print(f"❌ System stats: ERROR - {e}")
    
    print()
    print("🎉 API testing complete!")

if __name__ == "__main__":
    test_api()
