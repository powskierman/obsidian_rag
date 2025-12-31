#!/usr/bin/env python3
"""
Test script for the unified query API

Tests all three modes:
- NetworkX only
- LightRAG only
- Hybrid (both)
"""

import requests
import json
import sys

API_URL = "http://localhost:4000/api/v1"

def test_health():
    """Test the health endpoint"""
    print("=" * 60)
    print("Testing Health Endpoint")
    print("=" * 60)

    try:
        response = requests.get(f"{API_URL}/health")
        response.raise_for_status()
        data = response.json()

        print(json.dumps(data, indent=2))

        services = data.get("data", {}).get("services", {})

        # Check each service
        for service_name, service_data in services.items():
            status = service_data.get("status")
            print(f"\n{service_name.upper()}: {status}")
            if status != "healthy":
                print(f"  ⚠️  Warning: {service_name} is {status}")

        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_query(query, mode):
    """Test a query in a specific mode"""
    print("\n" + "=" * 60)
    print(f"Testing {mode.upper()} Mode")
    print("=" * 60)
    print(f"Query: {query}")
    print()

    try:
        response = requests.post(
            f"{API_URL}/query",
            json={
                "query": query,
                "mode": mode,
                "max_results": 5
            },
            timeout=120
        )
        response.raise_for_status()
        result = response.json()

        print(json.dumps(result, indent=2))

        return True
    except requests.exceptions.Timeout:
        print(f"❌ Query timed out after 120 seconds")
        return False
    except Exception as e:
        print(f"❌ Query failed: {e}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response.text}")
        return False


def main():
    """Run all tests"""
    print("\n🧪 Unified Query API Test Suite\n")

    # Test 1: Health check
    if not test_health():
        print("\n❌ Health check failed - ensure all services are running")
        sys.exit(1)

    # Test query
    test_query = sys.argv[1] if len(sys.argv) > 1 else "What is RAG?"

    # Test 2: NetworkX mode
    test_query(test_query, "networkx")

    # Test 3: LightRAG mode
    test_query(test_query, "lightrag")

    # Test 4: Hybrid mode
    test_query(test_query, "hybrid")

    print("\n" + "=" * 60)
    print("✅ All tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
