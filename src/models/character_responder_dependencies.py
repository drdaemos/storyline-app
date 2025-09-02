from dataclasses import dataclass
from pathlib import Path

from src.chat_logger import ChatLogger
from src.memory import ConversationMemory
from src.models.prompt_processor import PromptProcessor


@dataclass
class CharacterResponderDependencies:
    """Dependencies container for CharacterResponder to enable dependency injection."""

    primary_processor: PromptProcessor
    backup_processor: PromptProcessor
    conversation_memory: ConversationMemory | None = None
    chat_logger: ChatLogger | None = None
    session_id: str | None = None

    @classmethod
    def create_default(
        cls,
        character_name: str,
        session_id: str,
        use_persistent_memory: bool = True,
        logs_dir: Path | None = None,
        processor_type: str = "claude"
    ) -> "CharacterResponderDependencies":
        """
        Create default dependencies with standard processor setup.

        Args:
            character_name: Name of the character for logging and memory
            session_id: Session ID for logging and memory
            use_persistent_memory: Whether to create persistent memory
            logs_dir: Directory for chat logs
            processor_type: Type of primary processor ("claude" or "cohere")

        Returns:
            CharacterResponderDependencies instance with default setup
        """
        from src.processors.claude_prompt_processor import ClaudePromptProcessor
        from src.processors.cohere_prompt_processor import CoherePromptProcessor

        # Setup processors
        if processor_type.lower() == "cohere":
            primary_processor = CoherePromptProcessor()
            backup_processor = ClaudePromptProcessor()  # Use Claude as backup for Cohere
        elif processor_type.lower() == "claude":
            primary_processor = ClaudePromptProcessor()
            backup_processor = CoherePromptProcessor()  # Use Cohere as backup for Claude
        else:
            raise ValueError(f"Unsupported processor type: {processor_type}. Use 'claude' or 'cohere'.")

        # Setup memory if requested
        conversation_memory = ConversationMemory() if use_persistent_memory else None

        # Setup chat logger
        chat_logger = ChatLogger(character_name, session_id, logs_dir)
        primary_processor.set_logger(chat_logger)

        return cls(
            primary_processor=primary_processor,
            backup_processor=backup_processor,
            conversation_memory=conversation_memory,
            chat_logger=chat_logger,
            session_id=session_id
        )

