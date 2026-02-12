import requests
import json

# Test the analytics endpoint
try:
    # First login to get a token
    login_resp = requests.post(
        "http://localhost:8000/api/login",
        json={
            "username": "pranathi@codegnan.com",
            "password": "Pranathi@0509"
        }
    )
    
    if login_resp.status_code == 200:
        login_data = login_resp.json()
        print("Login successful:", login_data.get("success"))
        
        if login_data.get("success"):
            token = login_data.get("token")
            
            # Now test analytics endpoint
            analytics_resp = requests.get(
                "http://localhost:8000/api/student/analytics",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            print(f"\nAnalytics Status: {analytics_resp.status_code}")
            
            if analytics_resp.status_code == 200:
                data = analytics_resp.json()
                print("\nAnalytics Data:")
                print(json.dumps(data, indent=2))
            else:
                print("Error:", analytics_resp.text)
    else:
        print("Login failed:", login_resp.text)
        
except Exception as e:
    print(f"Error: {e}")
