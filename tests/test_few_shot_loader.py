import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.few_shot_loader import FewShotLoader


class TestFewShotLoader:
    def test_init_with_default_path(self):
        """Test initialization with default path."""
        loader = FewShotLoader()
        assert loader.dataset_path == Path("golden_dataset")

    def test_init_with_custom_path(self):
        """Test initialization with custom path."""
        custom_path = "custom_dataset"
        loader = FewShotLoader(dataset_path=custom_path)
        assert loader.dataset_path == Path(custom_path)

    def test_load_examples_with_valid_files(self):
        """Test loading examples from valid text files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_file1 = Path(temp_dir) / "example1.txt"
            test_file2 = Path(temp_dir) / "example2.txt"

            test_file1.write_text("This is example 1 content.", encoding="utf-8")
            test_file2.write_text("This is example 2 content.", encoding="utf-8")

            loader = FewShotLoader(dataset_path=temp_dir)

            assert len(loader.examples) == 2
            assert "This is example 1 content." in loader.examples
            assert "This is example 2 content." in loader.examples

    def test_load_examples_with_empty_files(self):
        """Test that empty files are ignored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty file and file with content
            empty_file = Path(temp_dir) / "empty.txt"
            content_file = Path(temp_dir) / "content.txt"

            empty_file.write_text("", encoding="utf-8")
            content_file.write_text("Valid content", encoding="utf-8")

            loader = FewShotLoader(dataset_path=temp_dir)

            assert len(loader.examples) == 1
            assert "Valid content" in loader.examples

    def test_load_examples_nonexistent_directory(self):
        """Test behavior when directory doesn't exist."""
        with patch("builtins.print") as mock_print:
            loader = FewShotLoader(dataset_path="nonexistent_dir")

            assert len(loader.examples) == 0
            mock_print.assert_called_with("Warning: nonexistent_dir folder not found. No few-shot examples loaded.")

    def test_load_examples_no_txt_files(self):
        """Test behavior when directory has no .txt files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create non-txt file
            other_file = Path(temp_dir) / "example.json"
            other_file.write_text('{"test": "data"}', encoding="utf-8")

            with patch("builtins.print") as mock_print:
                loader = FewShotLoader(dataset_path=temp_dir)

                assert len(loader.examples) == 0
                mock_print.assert_called_with(f"Warning: No .txt files found in {temp_dir}. No few-shot examples loaded.")

    def test_load_examples_with_file_read_error(self):
        """Test handling of file read errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("Valid content", encoding="utf-8")

            # Make file unreadable
            os.chmod(test_file, 0o000)

            try:
                with patch("builtins.print") as mock_print:
                    loader = FewShotLoader(dataset_path=temp_dir)

                    assert len(loader.examples) == 0
                    # Check that error was printed
                    error_calls = [call for call in mock_print.call_args_list if "Error loading" in str(call)]
                    assert len(error_calls) > 0
            finally:
                # Restore permissions for cleanup
                os.chmod(test_file, 0o644)

    def test_get_style_context_with_examples(self):
        """Test style context formatting with examples."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "example.txt"
            test_file.write_text("Sample style example", encoding="utf-8")

            loader = FewShotLoader(dataset_path=temp_dir)
            context = loader.get_style_context()

            assert "Few-shot style examples" in context
            assert "Example 1:" in context
            assert "Sample style example" in context
            assert "---" in context

    def test_get_style_context_no_examples(self):
        """Test style context when no examples are loaded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = FewShotLoader(dataset_path=temp_dir)
            context = loader.get_style_context()

            assert context == ""

    def test_has_examples_with_examples(self):
        """Test has_examples returns True when examples exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "example.txt"
            test_file.write_text("Sample content", encoding="utf-8")

            loader = FewShotLoader(dataset_path=temp_dir)

            assert loader.has_examples() is True

    def test_has_examples_no_examples(self):
        """Test has_examples returns False when no examples exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = FewShotLoader(dataset_path=temp_dir)

            assert loader.has_examples() is False

    def test_multiple_examples_formatting(self):
        """Test proper formatting of multiple examples."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple test files
            for i in range(3):
                test_file = Path(temp_dir) / f"example{i + 1}.txt"
                test_file.write_text(f"Content for example {i + 1}", encoding="utf-8")

            loader = FewShotLoader(dataset_path=temp_dir)
            context = loader.get_style_context()

            assert "Example 1:" in context
            assert "Example 2:" in context
            assert "Example 3:" in context
            assert "Content for example 1" in context
            assert "Content for example 2" in context
            assert "Content for example 3" in context
