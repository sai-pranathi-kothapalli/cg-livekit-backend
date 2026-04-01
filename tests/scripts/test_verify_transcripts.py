from unittest.mock import patch, MagicMock
import sys

# Mock missing legacy module
with patch.dict(sys.modules, {'app.db.mongo': MagicMock()}):
    from scripts.verify_transcripts import main
import pytest
from io import StringIO

def test_verify_transcripts_no_token_no_docs():
    with patch('scripts.verify_transcripts.get_config'):
        with patch('scripts.verify_transcripts.TranscriptStorageService') as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.col.find.return_value.sort.return_value.limit.return_value = []
            
            with patch('sys.stdout', new=StringIO()) as fake_out:
                with patch('sys.argv', ['verify_transcripts.py']):
                    main()
                    output = fake_out.getvalue()
                    assert "No transcript documents found" in output

def test_verify_transcripts_with_token_success():
    with patch('scripts.verify_transcripts.get_config'):
        with patch('scripts.verify_transcripts.TranscriptStorageService') as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.get_transcript.return_value = [
                {"role": "assistant", "content": "Hello", "index": 0, "timestamp": "123"},
                {"role": "user", "content": "Hi", "index": 1, "timestamp": "124"}
            ]
            
            with patch('sys.stdout', new=StringIO()) as fake_out:
                with patch('sys.argv', ['verify_transcripts.py', 'test_token']):
                    main()
                    output = fake_out.getvalue()
                    assert "=== Transcript for booking_token: test_token ===" in output
                    assert "assistant: Hello" in output
                    assert "user: Hi" in output
                    assert "Transcript is stored in MongoDB" in output
