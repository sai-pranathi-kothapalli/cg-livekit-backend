import pytest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys

# Note: These legacy scripts import from app.db.mongo which might not exist.
# We mock the import to test the control flow.

def test_create_indexes_flow():
    # Mocking the missing app.db.mongo
    with patch.dict(sys.modules, {'app.db.mongo': MagicMock()}):
        from scripts.create_indexes import create_indexes
        
        mock_db = MagicMock()
        mock_db.name = "test_db"
        mock_db.list_collection_names.return_value = []
        
        with patch('scripts.create_indexes.get_database', return_value=mock_db):
            with patch('scripts.create_indexes.get_config'):
                with patch('sys.stdout', new=StringIO()) as fake_out:
                    create_indexes()
                    output = fake_out.getvalue()
                    assert "Creating indexes for database: test_db" in output
                    assert "All indexes created successfully!" in output
                    # Verify one of the indexes was called
                    assert mock_db.interview_bookings.create_index.called

def test_create_transcript_collection_flow():
    with patch.dict(sys.modules, {'app.db.mongo': MagicMock()}):
        from scripts.create_transcript_collection import main
        
        mock_service = MagicMock()
        mock_service.db.name = "test_db"
        mock_service.db.list_collection_names.return_value = []
        
        with patch('scripts.create_transcript_collection.TranscriptStorageService', return_value=mock_service):
            with patch('scripts.create_transcript_collection.get_config'):
                with patch('sys.stdout', new=StringIO()) as fake_out:
                    main()
                    output = fake_out.getvalue()
                    assert "Created collection 'interview_transcripts'" in output
                    mock_service.db.create_collection.assert_called_with("interview_transcripts")
