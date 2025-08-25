import tempfile
from pathlib import Path
from unittest.mock import patch

from src.chat_logger import ChatLogger


class TestChatLogger:

    def setup_method(self):
        """Set up test data for each test."""
        self.character_id = "Alice"

    def test_logging_setup_with_default_directory(self):
        """Test that logging is set up with default directory."""

        with patch('pathlib.Path.cwd') as mock_cwd:
            mock_cwd.return_value = Path(tempfile.mkdtemp())
            chat_logger = ChatLogger(self.character_id, session_id="test-session-123456789")

            assert hasattr(chat_logger, 'logger')
            assert hasattr(chat_logger, 'log_file_path')
            assert chat_logger.logs_dir.name == "logs"

    def test_logging_setup_with_custom_directory(self):
        """Test that logging is set up with custom directory."""

        with tempfile.TemporaryDirectory() as temp_dir:
            custom_logs_dir = Path(temp_dir) / "custom_logs"
            chat_logger = ChatLogger(self.character_id, session_id="test-session-123456789", logs_dir=custom_logs_dir)

            try:
                assert chat_logger.logs_dir == custom_logs_dir
                assert custom_logs_dir.exists()
            finally:
                chat_logger.close_logger()
                # Clean up log file
                if chat_logger.log_file_path.exists():
                    chat_logger.log_file_path.unlink()

    def test_log_file_naming(self):
        """Test that log files are named correctly with character and session ID."""

        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)

            # Test with session ID
            chat_logger = ChatLogger(
                self.character_id,
                session_id="test-session-123456789",
                logs_dir=logs_dir
            )

            try:
                # Check that character directory is created
                expected_char_dir = logs_dir / "Alice"
                assert expected_char_dir.exists()

                # Check filename is just session ID
                expected_filename = "test-ses.log"  # First 8 chars of session ID
                assert chat_logger.log_file_path.name == expected_filename

                # Check full path includes character directory
                assert chat_logger.log_file_path.parent.name == "Alice"
            finally:
                chat_logger.close_logger()
                # Clean up log file
                if chat_logger.log_file_path.exists():
                    chat_logger.log_file_path.unlink()

    def test_log_file_naming_with_special_characters(self):
        """Test log file naming with special characters in character name."""

        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            chat_logger = ChatLogger(
                "Alice O'Malley & Co.",
                session_id="test123",
                logs_dir=logs_dir
            )

            try:
                # Check that sanitized character directory is created
                expected_char_dir = logs_dir / "Alice OMalley  Co"
                assert expected_char_dir.exists()

                # Check filename is just session ID
                expected_filename = "test123.log"
                assert chat_logger.log_file_path.name == expected_filename

                # Check full path includes sanitized character directory
                assert chat_logger.log_file_path.parent.name == "Alice OMalley  Co"
            finally:
                chat_logger.close_logger()
                # Clean up log file
                if chat_logger.log_file_path.exists():
                    chat_logger.log_file_path.unlink()

    def test_log_file_encoding_unicode(self):
        """Test that log files handle Unicode characters properly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            chat_logger = ChatLogger(
                self.character_id,
                session_id="unicode-session",
                logs_dir=logs_dir
            )

            try:
                # Send message with Unicode characters
                chat_logger.log_message("test", "Héllo charactér! 🌟")
                chat_logger.log_message("character", "Héllo wörld! 🎭")

                # Check that Unicode is properly stored
                log_content = chat_logger.log_file_path.read_text(encoding='utf-8')
                assert "Héllo charactér! 🌟" in log_content
                assert "Héllo wörld! 🎭" in log_content
            finally:
                chat_logger.close_logger()
                # Clean up log file
                if chat_logger.log_file_path.exists():
                    chat_logger.log_file_path.unlink()
