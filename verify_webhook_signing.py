import hashlib
import hmac
import json

def verify_signature(secret, body_bytes, signature_header):
    expected_signature = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    actual_signature = signature_header.replace("sha256=", "")
    return expected_signature == actual_signature

# Test data
test_secret = "e3099b44ad6c7837018fa83c323d46ebd469476c56a0331b242bb5b7a4a3e9f6"
test_payload = {
    "event": "EVALUATION_COMPLETED",
    "booking_token": "abc123",
    "overall_score": 7.5
}
body_bytes = json.dumps(test_payload, sort_keys=True).encode()
signature = hmac.new(test_secret.encode(), body_bytes, hashlib.sha256).hexdigest()
header = f"sha256={signature}"

print(f"Body: {body_bytes.decode()}")
print(f"Header: {header}")
print(f"Verification result: {verify_signature(test_secret, body_bytes, header)}")
