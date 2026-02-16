import secrets
from app.utils.api_key import hash_api_key

def main():
    print("Generating secure API Key...")
    
    # Generate a random 32-byte hex string
    api_key = secrets.token_hex(32)
    key_hash = hash_api_key(api_key)
    
    print("\n" + "="*50)
    print("API KEY GENERATED")
    print("="*50)
    print(f"API Key:      {api_key}")
    print(f"SHA-256 Hash: {key_hash}")
    print("="*50)
    
    print("\nINSTRUCTIONS:")
    print("1. Copy the 'SHA-256 Hash' value.")
    print("2. Add it to your .env file:")
    print(f"   API_KEY_HASH={key_hash}")
    print("3. Restart the server.")
    print("4. Use 'X-API-Key' header with the 'API Key' value to authenticate.")
    print("\n⚠️  SAVE THE API KEY NOW. IT CANNOT BE RECOVERED SPECIFICALLY IF LOST (only the hash is stored).")

if __name__ == "__main__":
    main()
