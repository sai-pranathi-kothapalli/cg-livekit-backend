import pytest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys
from scripts.dev_utils.generate_key import main

def test_generate_key_output():
    with patch('sys.stdout', new=StringIO()) as fake_out:
        with patch('scripts.dev_utils.generate_key.hash_api_key') as mock_hash:
            mock_hash.return_value = "mocked_hash"
            main()
            output = fake_out.getvalue()
            
            assert "API KEY GENERATED" in output
            assert "API Key:" in output
            assert "SHA-256 Hash: mocked_hash" in output
            assert "API_KEY_HASH=mocked_hash" in output

def test_generate_key_randomness():
    with patch('sys.stdout', new=StringIO()):
        with patch('secrets.token_hex') as mock_token:
            mock_token.return_value = "fixed_token"
            with patch('scripts.dev_utils.generate_key.hash_api_key') as mock_hash:
                mock_hash.return_value = "fixed_hash"
                main()
                mock_token.assert_called_with(32)
