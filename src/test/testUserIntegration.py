import httpx
import asyncio
import logging 

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8000"

async def test_integration():
    async with httpx.AsyncClient() as client: 
        logger.info("---Starting Integration Test ---")

        logger.info("Step 1: Testing single user registration...")
        new_user = {
            "username" : "test_user_99",
            "email":"test_99@discord.local",
            "role":"student",
            "default_collection":"general"
        }

        response = await client.post(f"{BASE_URL}/api/users",json=new_user)
        if response.status_code == 200:
            logging.info(f"Response: {response.status_code}-{response.json()}")
        else:
            logger.info("\nStep 2: Testing duplicate handling (Edge Case)...")
        response_dup = await client.post(f"{BASE_URL}/api/users", json=new_user)
        logger.info(f"Response: {response_dup.status_code} - (Should be successful/no duplicate created)")
        # 3. Test Batch Sync (Simulating on_ready)
        logger.info("\nStep 3: Testing batch sync of multiple users...")
        batch_users = [
            {"username": "user_a", "email": "a@test.com", "role": "student", "default_collection": "general"},
            {"username": "user_b", "email": "b@test.com", "role": "student", "default_collection": "general"},
            {"username": "test_user_99", "email": "test_99@discord.local", "role": "student", "default_collection": "general"}
        ]
        response_batch = await client.post(f"{BASE_URL}/api/users/batch", json=batch_users)
        logger.info(f"Response: {response_batch.status_code} - Synced {len(batch_users)} users.")

        logger.info("\n--- Integration Tests Complete ---")

if __name__ == "__main__":
    asyncio.run(test_integration())