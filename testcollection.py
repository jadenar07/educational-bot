#!/usr/bin/env python3
"""
Test script for Collection Management API
"""
import asyncio
import httpx

BASE_URL = "http://localhost:8000"

async def test_collection_api():
    """Test the collection management API endpoints"""
    
    async with httpx.AsyncClient() as client:
        


        print("Test collection management endpoints")
        
        # Test 1: Create a new collection
        print("\n1. Creating a new collection...")
        create_data = {
            "name": "test_collection",
            "description": "A test collection for API testing",
            "metadata": {"type": "test", "version": "1.0"}
        }
        
        try:
            response = await client.post(f"{BASE_URL}/collections", json=create_data)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f" Collection created: {result['name']}")
                print(f"   Description: {result['description']}")
                print(f"   Document count: {result['document_count']}")
            else:
                print(f" Error: {response.text}")
        except Exception as e:
            print(f"Connection error: {e}")
            return
        
        # Test 2: List all collections
        print("\n2. Listing all collections...")
        try:
            response = await client.get(f"{BASE_URL}/collections")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f" Found {result['total_count']} collections:")
                for collection in result['collections']:
                    print(f"   - {collection['name']} ({collection['document_count']} docs)")
            else:
                print(f" Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 3: Get specific collection info
        print("\n3. Getting collection info...")
        try:
            response = await client.get(f"{BASE_URL}/collections/test_collection")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"Collection info: {result['name']}")
                print(f"   Description: {result['description']}")
                print(f"   Document count: {result['document_count']}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 4: Delete the collection
        print("\n4. Deleting the collection...")
        try:
            response = await client.delete(f"{BASE_URL}/collections/test_collection")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"{result['message']}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 5: Verify deletion
        print("\n5. Verifying deletion...")
        try:
            response = await client.get(f"{BASE_URL}/collections/test_collection")
            print(f"Status: {response.status_code}")
            if response.status_code == 404:
                print("Collection successfully deleted")
            else:
                print(f"Collection still exists: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        print("\n" + "=" * 50)
        print("Collection Management API test completed!")

if __name__ == "__main__":
    asyncio.run(test_collection_api())