from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter for auth endpoints (limit by IP)
limiter = Limiter(key_func=get_remote_address)
