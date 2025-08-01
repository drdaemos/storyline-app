from pathlib import Path


class FewShotLoader:
    """Loads few-shot example texts from the golden_dataset folder to influence agent writing style."""  # noqa: E501

    def __init__(self, dataset_path: str = "golden_dataset") -> None:
        self.dataset_path = Path(dataset_path)
        self.examples: list[str] = []
        self.load_examples()

    def load_examples(self) -> None:
        """Load all text files from the golden_dataset folder."""
        if not self.dataset_path.exists():
            print(f"Warning: {self.dataset_path} folder not found. No few-shot examples loaded.")
            return

        txt_files = list(self.dataset_path.glob("*.txt"))

        if not txt_files:
            print(f"Warning: No .txt files found in {self.dataset_path}. No few-shot examples loaded.")
            return

        for txt_file in txt_files:
            try:
                with open(txt_file, encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self.examples.append(content)
                        print(f"Loaded few-shot example from {txt_file.name}")
            except Exception as e:
                print(f"Error loading {txt_file}: {e}")

    def get_style_context(self) -> str:
        """Get formatted few-shot examples for use in agent prompts."""
        if not self.examples:
            return ""

        context = "Few-shot style examples (emulate this writing style and tone):\n\n"
        for i, example in enumerate(self.examples, 1):
            context += f"Example {i}:\n{example}\n\n"

        context += "---\n\n"
        return context

    def has_examples(self) -> bool:
        """Check if any examples were loaded."""
        return len(self.examples) > 0
