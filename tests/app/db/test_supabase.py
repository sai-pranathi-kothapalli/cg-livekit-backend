import unittest
from unittest.mock import patch, MagicMock
import os
import importlib

class TestSupabaseDB(unittest.TestCase):
    def test_get_supabase(self):
        """Test that get_supabase returns the global client."""
        from app.db.supabase import get_supabase, supabase
        self.assertEqual(get_supabase(), supabase)

    @patch("supabase.create_client")
    def test_supabase_initialization(self, mock_create_client):
        """
        Verify that reloading the module (to simulate first import)
        calls create_client with expected env vars.
        """
        import app.db.supabase
        
        # Set dummy env vars
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_KEY": "test-key"
        }):
            # Reload the module to trigger re-initialization with new env vars
            importlib.reload(app.db.supabase)
            
            # The module uses:
            # SUPABASE_URL = os.getenv("SUPABASE_URL", "")
            # SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
            # supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            
            mock_create_client.assert_called_with("https://test.supabase.co", "test-key")
            
            # Verify get_supabase returns the newly created client
            from app.db.supabase import get_supabase
            self.assertEqual(get_supabase(), mock_create_client.return_value)

if __name__ == "__main__":
    unittest.main()
