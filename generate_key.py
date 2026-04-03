import hashlib
import secrets

key = f"cgn_live_lms_{secrets.token_hex(24)}"
hashed = hashlib.sha256(key.encode()).hexdigest()

print("=== LMS API KEY PAIR ===")
print(f"Plain key:  {key}")
print(f"Hashed key: {hashed}")
print("========================")
