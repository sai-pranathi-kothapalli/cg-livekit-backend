import traceback
try:
    from app.api.integration import router
    print("Success")
except Exception as e:
    traceback.print_exc()
