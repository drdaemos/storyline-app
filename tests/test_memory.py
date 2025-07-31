import pytest
from src.memory import NPCMemory


class TestNPCMemory:
    def test_init(self):
        memory = NPCMemory()
        assert memory.conversations == []
        assert memory.facts == {}
        assert memory.relationships == {}
    
    def test_add_conversation(self):
        memory = NPCMemory()
        memory.add_conversation("Hello", "Greetings, traveler!")
        
        assert len(memory.conversations) == 1
        conversation = memory.conversations[0]
        assert conversation["user"] == "Hello"
        assert conversation["npc"] == "Greetings, traveler!"
        assert conversation["timestamp"] == "0"
    
    def test_add_multiple_conversations(self):
        memory = NPCMemory()
        memory.add_conversation("Hello", "Greetings!")
        memory.add_conversation("How are you?", "I'm well, thank you.")
        
        assert len(memory.conversations) == 2
        assert memory.conversations[0]["timestamp"] == "0"
        assert memory.conversations[1]["timestamp"] == "1"
    
    def test_add_fact(self):
        memory = NPCMemory()
        memory.add_fact("favorite_color", "blue")
        memory.add_fact("hometown", "Village of Eldridge")
        
        assert memory.facts["favorite_color"] == "blue"
        assert memory.facts["hometown"] == "Village of Eldridge"
    
    def test_get_context_empty(self):
        memory = NPCMemory()
        context = memory.get_context()
        expected = "Previous conversations:\n"
        assert context == expected
    
    def test_get_context_with_conversations(self):
        memory = NPCMemory()
        memory.add_conversation("Hello", "Hi there!")
        memory.add_conversation("Nice weather", "Indeed it is!")
        
        context = memory.get_context()
        assert "User: Hello" in context
        assert "NPC: Hi there!" in context
        assert "User: Nice weather" in context
        assert "NPC: Indeed it is!" in context
    
    def test_get_context_with_facts(self):
        memory = NPCMemory()
        memory.add_fact("profession", "blacksmith")
        memory.add_fact("age", "45")
        
        context = memory.get_context()
        assert "Known facts:" in context
        assert "- profession: blacksmith" in context
        assert "- age: 45" in context
    
    def test_get_context_limits_conversations_to_five(self):
        memory = NPCMemory()
        for i in range(7):
            memory.add_conversation(f"Message {i}", f"Response {i}")
        
        context = memory.get_context()
        # Should only contain last 5 conversations (indices 2-6)
        assert "Message 0" not in context
        assert "Message 1" not in context
        assert "Message 2" in context
        assert "Message 6" in context
    
    def test_get_context_combined(self):
        memory = NPCMemory()
        memory.add_conversation("Hello", "Greetings!")
        memory.add_fact("location", "tavern")
        
        context = memory.get_context()
        assert "Previous conversations:" in context
        assert "User: Hello" in context
        assert "Known facts:" in context
        assert "- location: tavern" in context