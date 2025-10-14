import logging
import sys
from pathlib import Path


class ChatLogger:
    def __init__(self, character_id: str, session_id: str, file_only: bool = True, logs_dir: Path | None = None) -> None:
        """
        Setup logging for conversation messages.

        Args:
            logs_dir: Directory to store logs. Defaults to ./logs
        """
        if logs_dir is None:
            logs_dir = Path.cwd() / "logs"

        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Create character-specific directory
        safe_character_id = "".join(c for c in character_id if c.isalnum() or c in (" ", "-", "_")).rstrip()
        character_logs_dir = self.logs_dir / safe_character_id
        character_logs_dir.mkdir(parents=True, exist_ok=True)

        # Create log filename using session ID only (character name is now in folder)
        safe_session_id = session_id[:8]  # Use first 8 chars of session ID
        log_filename = f"{safe_session_id}.log"
        self.log_file_path = character_logs_dir / log_filename

        # Setup logger for this character session
        logger_name = f"character_responder_{safe_character_id}_{safe_session_id}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

        # Remove any existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create file handler
        file_handler = logging.FileHandler(self.log_file_path, encoding="utf-8")
        file_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(formatter)

        # Add handler to logger
        self.logger.addHandler(file_handler)

        # Add console handler if not file_only
        if not file_only:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False

    def log_message(self, role: str, content: str) -> None:
        """
        Log the conversation message to the log file.

        Args:
            user_message: The user's input message
            raw_evaluation: Raw evaluation response from the processor
            raw_response: Raw character response from the processor
            character_response: Parsed character response
        """
        # Log user message
        self.logger.info(f"{role.upper()}: {content}")

    def log_exception(self, exc: Exception) -> None:
        """Log an exception message."""
        self.logger.exception(exc)

    def close_logger(self) -> None:
        """Close the logger and release file handles."""
        if hasattr(self, "logger"):
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)
