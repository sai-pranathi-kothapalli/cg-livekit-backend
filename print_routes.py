from app.api.main import app

for route in app.routes:
    if hasattr(route, 'methods'):
        for method in route.methods:
            print(f"{method:6s} {route.path}")
