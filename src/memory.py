class NPCMemory:
    def __init__(self) -> None:
        self.conversations: list[dict[str, str]] = []
        self.facts: dict[str, str] = {}
        self.relationships: dict[str, str] = {}

    def add_conversation(self, user_input: str, npc_response: str) -> None:
        self.conversations.append({"user": user_input, "npc": npc_response, "timestamp": str(len(self.conversations))})

    def add_fact(self, key: str, value: str) -> None:
        self.facts[key] = value

    def get_context(self) -> str:
        context = "Previous conversations:\n"
        for conv in self.conversations[-5:]:
            context += f"User: {conv['user']}\nNPC: {conv['npc']}\n\n"

        if self.facts:
            context += "Known facts:\n"
            for key, value in self.facts.items():
                context += f"- {key}: {value}\n"

        return context
