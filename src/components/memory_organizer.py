from typing import Any

from haystack import component
from haystack.dataclasses import ChatMessage


@component
class MemoryOrganizer:
    """
    A component generating personal welcome message and making it upper case
    """

    @component.output_types(memories=list[ChatMessage])
    def run(self, plan: dict[str, Any], previous_memories: list[ChatMessage] | None = None) -> dict[str, list[ChatMessage]]:
        return {"memories": (previous_memories or [])[-4:] + [ChatMessage.from_user(plan["user_action"]), ChatMessage.from_assistant(plan["character_action"])]}

    # def run(self, user_message: str, replies: list[str], previous_memories: list[ChatMessage] | None = None) -> dict[str, list[ChatMessage]]:
    #   return {
    #     "memories": (previous_memories or [])[-4:] + [
    #       ChatMessage.from_user(user_message),
    #       ChatMessage.from_assistant(replies[0])
    #     ]
    #   }
