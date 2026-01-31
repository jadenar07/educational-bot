from fastapi.testclient import TestClient
from unittest.mock import patch
from backend.app import app  # Assuming 'app' is imported from here

client = TestClient(app)

# Mock payloads for different roles
mock_payloads = {
    "student": {"role": "student"},
    "professor": {"role": "professor"},
}

# Queries to test per role
test_queries = {
    "student": "I am feeling overwhelmed and need to talk to someone",
    "professor": "show me the progress report for my students",
}

def test_role_based_queries():
    for role, payload in mock_payloads.items():
        query = test_queries[role]

        with patch("backend.middleware.role_middleware.jwt.decode") as mock_decode:
            mock_decode.return_value = payload

            response = client.post(
                "/query",
                headers={"Authorization": "Bearer faketoken"},
                json={
                    "query": query,
                    "guild_id": 123,
                    "channel_id": 456
                }
            )
        
        # Print helpful debug info *before* the assertion
        print(f"\n=== TESTING ROLE: {role.upper()} ===")
        print(f"Query: \"{query}\"")
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")

        assert response.status_code == 200, f"{role} test failed with status {response.status_code}: {response.text}"
        
        data = response.json()
        assert "answer" in data, f"{role} response missing 'answer'key. Got: {data}"
        
        print(f"Result: PASSED")


def test_invalid_and_missing_tokens():
    # Test missing token (should return 401)
    response = client.post(
        "/query",
        json={"query": "any query", "guild_id": 0, "channel_id": 0}
    )
    assert response.status_code == 401, f"Missing token test failed: {response.status_code}"
    print("\n=== MISSING TOKEN RESPONSE ===")
    print("Status code:", response.status_code)
    print("Response JSON:", response.json())

    # Test invalid token (should return 401)
    with patch("backend.middleware.role_middleware.jwt.decode") as mock_decode:
        mock_decode.side_effect = Exception("Invalid token")
        response = client.post(
            "/query",
            headers={"Authorization": "Bearer invalidtoken"},
            json={"query": "any query", "guild_id": 0, "channel_id": 0} 
        )
    assert response.status_code in [401], f"Invalid token test failed: {response.status_code}"
    print("\n=== INVALID TOKEN RESPONSE ===")
    print("Status code:", response.status_code)
    print("Response JSON:", response.json())

if __name__ == "__main__":
    print("Starting role-based query tests...")
    test_role_based_queries()
    print("\nStarting auth token tests...")
    test_invalid_and_missing_tokens()
    print("\nAll tests finished.")