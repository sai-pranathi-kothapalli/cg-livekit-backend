import pytest
import logging
from unittest.mock import MagicMock, patch
from app.utils.logger import setup_logging, get_logger

def test_get_logger():
    logger = get_logger("test-logger")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test-logger"

def test_setup_logging():
    config = MagicMock()
    config.LOG_LEVEL = "DEBUG"
    config.LOG_FORMAT = "%(message)s"
    
    with patch("logging.getLogger") as mock_get_logger:
        root_logger = MagicMock()
        mock_get_logger.return_value = root_logger
        
        setup_logging(config)
        
        # Verify root logger level was set
        root_logger.setLevel.assert_any_call(logging.DEBUG)
        # Verify handlers were cleared
        root_logger.handlers.clear.assert_called()
        # Verify handler was added
        assert root_logger.addHandler.called
