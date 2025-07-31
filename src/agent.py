from crewai import Agent, Task, Crew, LLM
from .memory import NPCMemory
from .few_shot_loader import FewShotLoader


class NPCAgent:
    def __init__(self, role: str, backstory: str, name: str = "NPC"):
        self.memory = NPCMemory()
        self.few_shot_loader = FewShotLoader()
        self.name = name
        self.role = role
        self.backstory = backstory

        llm = LLM(
            model="openai/gpt-4.1",
            stream=True
        )
        
        self.agent = Agent(
            llm=llm,
            role=self.role,
            goal=f"Act as {self.name}, staying in character and using your memory of past interactions",
            backstory=self.backstory,
            verbose=False,
            allow_delegation=False
        )
    
    def respond(self, user_input: str) -> str:
        context = self.memory.get_context()
        style_context = self.few_shot_loader.get_style_context()
        
        # Create a system task description without user input
        system_description = f"""
        You are {self.name}, a character with this background: {self.backstory}
        
        Context from previous interactions:
        {context}
        
        Respond as {self.name} would, staying in character. Keep responses conversational and engaging.
        Don't break character and treat this task as a role-playing exercise.
        Reference past conversations when relevant. Your response should be 1-3 sentences.
        If few-shot examples are provided below, emulate their writing style, tone, and character voice.
        
        The user's message will be provided separately below.
        """
        
        # Create task with user input as separate message content
        task = Task(
            description=f"""
            {system_description}
            Simulate the following text in style of writing:
            {style_context}
            
            Respond to the following user message: {user_input}""",
            agent=self.agent,
            expected_output="A character response that stays in role and references memory when appropriate"
        )
        
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=False
        )
        
        result = crew.kickoff()
        response = str(result)
        
        self.memory.add_conversation(user_input, response)
        
        return response