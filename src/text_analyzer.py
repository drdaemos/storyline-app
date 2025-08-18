from pathlib import Path
from typing import Any

from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage


class TextAnalyzer:
    def __init__(self) -> None:
        self.pipeline = self._build_pipeline()

    def _build_pipeline(self) -> Pipeline:
        """Build a simple haystack pipeline for text analysis."""
        prompt_builder = ChatPromptBuilder()
        llm = OpenAIChatGenerator(model="gpt-4.1")

        pipeline = Pipeline()
        pipeline.add_component("prompt_builder", prompt_builder)
        pipeline.add_component("llm", llm)

        pipeline.connect("prompt_builder", "llm")

        return pipeline

    def read_text_file(self, file_path: str) -> str:
        """Read text from a file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        return path.read_text(encoding="utf-8")

    def extract_plot_beats(self, text: str) -> dict[str, Any]:
        """Extract plot beats and summary from text using AI pipeline."""
        template = [
            ChatMessage.from_system("""
Act as playwright and analyze the provided text to prepare
a concise summary and extracy plot beats, and notable examples
of dialogue or character interactions.
Always analyze from a third-person perspective.

Provide the following information:
- Concise, factual summary of the plot (5-10 sentences at most).
- Descriptions for main characters (only the most prevalent).
- A list of plot beats, each described as an action or event (do not include dialogue, thoughts or excessive descriptions of the characters here).
- A list of notable examples of dialogue (5-10), that are reflecting the characters style of speech or referring to the plot-specific terminology.

Output instructions:
- Do not include any interaction with the user, just return the analysis.
            """),
            ChatMessage.from_user(text),
        ]

        result = self.pipeline.run({"prompt_builder": {"template": template, "template_variables": {"text": text }}})

        response = result["llm"]["replies"][0].text

        return {"analysis": response, "word_count": len(text.split()), "character_count": len(text)}

    def analyze_file(self, file_path: str) -> dict[str, Any]:
        """Analyze a text file and return plot beat analysis."""
        text = self.read_text_file(file_path)
        analysis = self.extract_plot_beats(text)

        return {"file_path": file_path, "file_stats": {"word_count": analysis["word_count"], "character_count": analysis["character_count"]}, "analysis": analysis["analysis"]}
