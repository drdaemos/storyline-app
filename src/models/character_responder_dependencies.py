from dataclasses import dataclass
from pathlib import Path

from src.chat_logger import ChatLogger
from src.memory.conversation_memory import ConversationMemory
from src.models.prompt_processor import PromptProcessor
from src.processors.claude_prompt_processor import ClaudePromptProcessor
from src.processors.cohere_prompt_processor import CoherePromptProcessor
from src.processors.openai_prompt_processor import OpenAiPromptProcessor
from src.processors.openrouter_prompt_processor import OpenRouterPromptProcessor
from src.memory.summary_memory import SummaryMemory


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

        # Setup processors
        backup_processor = OpenRouterPromptProcessor(model="deepseek/deepseek-chat-v3.1:free")
        match processor_type.lower():
            case "cohere":
                primary_processor = CoherePromptProcessor()
            case "claude":
                primary_processor = ClaudePromptProcessor()
            case "gpt":
                primary_processor = OpenAiPromptProcessor()
            case "grok":
                primary_processor = OpenRouterPromptProcessor(model="x-ai/grok-4-fast:free")
            case "deepseek":
                primary_processor = OpenRouterPromptProcessor(model="deepseek/deepseek-v3.1-terminus")
            case "gpt-oss":
                primary_processor = OpenRouterPromptProcessor(model="openai/gpt-oss-120b")
            case "google":
                primary_processor = OpenRouterPromptProcessor(model="google/gemini-2.5-flash")
            case _:
                raise ValueError(f"Unsupported processor type: {processor_type}")

        # Setup memory if requested
        conversation_memory = ConversationMemory()
        summary_memory = SummaryMemory()

        if session_id is None:
            session_id = conversation_memory.create_session(character_name)

        # Setup chat logger
        chat_logger = ChatLogger(character_name, session_id, logs_dir)
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

