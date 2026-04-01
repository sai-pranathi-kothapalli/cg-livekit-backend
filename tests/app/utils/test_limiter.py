import pytest
from app.utils.limiter import limiter
from slowapi import Limiter

def test_limiter_initialization():
    assert isinstance(limiter, Limiter)
    assert limiter._key_func is not None
