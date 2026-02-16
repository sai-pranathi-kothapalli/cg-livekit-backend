from fastapi.testclient import TestClient
from app.api.main import app
from app.utils.api_key import hash_api_key
from app.config import get_config
import os

client = TestClient(app)

def test_api_key_auth():
    print("Testing API Key Authentication...")
    
    # 1. Generate a test key and hash
    test_key = "test-secret-key-123"
    test_hash = hash_api_key(test_key)
    
    # Mock configuration to return this hash
    # We need to patch get_config or ensure app reads this env
    # Since config is loaded at module level in some places, 
    # we might need to patch the config instance directly if possible, or use dependency override if we had one for config.
    # But api_key.py calls get_config() inside the dependency.
    
    # Let's override the environment variable and reload config or patch the object
    os.environ["API_KEY_HASH"] = test_hash
    
    # Force reload of config for the dependency check
    # In app/utils/api_key.py: "config = get_config()" returns a new instance or cached?
    # get_config() calls Config.from_env() which reads os.environ.
    # So assuming get_config is not cached (it isn't decorated with @lru_cache in config.py), checking...
    # config.py: def get_config(): return Config.from_env() -> It creates new instance every time. Good.
    
    # 2. Test Missing Key
    print("\n[Case 1] Missing Key")
    response = client.get("/api/secure-data")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    if response.status_code == 401:
        print("✅ Passed")
    else:
        print("❌ Failed (Expected 401)")

    # 3. Test Invalid Key
    print("\n[Case 2] Invalid Key")
    response = client.get("/api/secure-data", headers={"X-API-Key": "wrong-key"})
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    if response.status_code == 403:
        print("✅ Passed")
    else:
        print("❌ Failed (Expected 403)")

    # 4. Test Valid Key
    print("\n[Case 3] Valid Key")
    response = client.get("/api/secure-data", headers={"X-API-Key": test_key})
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    if response.status_code == 200:
        print("✅ Passed")
    else:
        print("❌ Failed (Expected 200)")

if __name__ == "__main__":
    try:
        test_api_key_auth()
    except Exception as e:
        print(f"❌ Test Failed with Exception: {e}")
