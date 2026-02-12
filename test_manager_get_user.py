import requests
import json

# Test the API endpoint
try:
    # First login as manager
    login_resp = requests.post(
        "http://localhost:8000/api/login",
        json={
            "username": "dewar@codegnan.com",
            "password": "Dewar@123"
        }
    )
    
    if login_resp.status_code == 200:
        login_data = login_resp.json()
        print("Login successful:", login_data.get("success"))
        
        if login_data.get("success"):
            token = login_data.get("token")
            
            # Get pranathi's user ID
            user_id = "341d0fff-c3e3-4fca-a331-480f5d23eecf"
            
            # Now test the get user endpoint
            get_user_resp = requests.get(
                f"http://localhost:8000/api/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            print(f"\nGet User Status: {get_user_resp.status_code}")
            
            if get_user_resp.status_code == 200:
                data = get_user_resp.json()
                print("\nUser Data:")
                print(f"Email: {data.get('email')}")
                print(f"Name: {data.get('name')}")
                print(f"Interviews Count: {len(data.get('interviews', []))}")
                
                print("\nInterviews:")
                for interview in data.get("interviews", []):
                    print(f"  - {interview}")
            else:
                print("Error:", get_user_resp.text)
    else:
        print("Login failed:", login_resp.text)
        
except Exception as e:
    print(f"Error: {e}")
