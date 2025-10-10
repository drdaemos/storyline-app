import os
from dataclasses import dataclass
from pathlib import Path

from src.chat_logger import ChatLogger
from src.memory.conversation_memory import ConversationMemory
from src.memory.summary_memory import SummaryMemory
from src.models.prompt_processor import PromptProcessor
from src.models.prompt_processor_factory import PromptProcessorFactory


@dataclass
class CharacterResponderDependencies:
    """Dependencies container for CharacterResponder to enable dependency injection."""

    primary_processor: PromptProcessor
    backup_processor: PromptProcessor
    session_id: str
    conversation_memory: ConversationMemory | None = None
    summary_memory: SummaryMemory | None = None
    chat_logger: ChatLogger | None = None

    @classmethod
    def create_default(
        cls,
        character_name: str,
        session_id: str | None = None,
        logs_dir: Path | None = None,
        processor_type: str = "claude",
        backup_processor_type: str | None = None
    ) -> "CharacterResponderDependencies":
        """
        Create default dependencies with standard processor setup.

        Args:
            character_name: Name of the character for logging and memory
            session_id: Session ID for logging and memory
            logs_dir: Directory for chat logs
            processor_type: Type of primary processor
            backup_processor_type: Type of backup processor (uses default if not specified)

        Returns:
            CharacterResponderDependencies instance with default setup
        """

        # Setup processors
        primary_processor = PromptProcessorFactory.create_processor(processor_type)
        if backup_processor_type:
            backup_processor = PromptProcessorFactory.create_processor(backup_processor_type)
        else:
            backup_processor = PromptProcessorFactory.get_default_backup_processor()

        # Setup memory
        conversation_memory = ConversationMemory()
        summary_memory = SummaryMemory()

        if session_id is None:
            session_id = conversation_memory.create_session(character_name)

        # Setup chat logger
        file_only = os.getenv("LOG_TO_CONSOLE", "false").lower() != "true"
        chat_logger = ChatLogger(character_name, session_id, file_only, logs_dir)
        primary_processor.set_logger(chat_logger)
        backup_processor.set_logger(chat_logger)

        return cls(
            primary_processor=primary_processor,
            backup_processor=backup_processor,
            conversation_memory=conversation_memory,
            summary_memory=summary_memory,
            chat_logger=chat_logger,
            session_id=session_id
        )

