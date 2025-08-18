import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.text_analyzer import TextAnalyzer


class TestTextAnalyzer:
    def test_init(self) -> None:
        analyzer = TextAnalyzer()
        assert analyzer.pipeline is not None

    def test_read_text_file_success(self) -> None:
        analyzer = TextAnalyzer()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            test_content = "This is a test story about heroes and villains."
            tmp.write(test_content)
            tmp_path = tmp.name

        try:
            result = analyzer.read_text_file(tmp_path)
            assert result == test_content
        finally:
            Path(tmp_path).unlink()

    def test_read_text_file_not_found(self) -> None:
        analyzer = TextAnalyzer()

        with pytest.raises(FileNotFoundError):
            analyzer.read_text_file("nonexistent_file.txt")

    @patch("src.text_analyzer.TextAnalyzer._build_pipeline")
    def test_extract_plot_beats(self, mock_build_pipeline) -> None:
        # Mock the pipeline response
        mock_pipeline = Mock()
        mock_reply = Mock()
        mock_reply.text = "Summary: A hero's journey begins.\nPlot beats: Introduction, Call to adventure"
        mock_pipeline.run.return_value = {"llm": {"replies": [mock_reply]}}
        mock_build_pipeline.return_value = mock_pipeline

        analyzer = TextAnalyzer()
        test_text = "Once upon a time, there was a hero who embarked on a great adventure."

        result = analyzer.extract_plot_beats(test_text)

        assert "analysis" in result
        assert "word_count" in result
        assert "character_count" in result
        assert result["word_count"] == len(test_text.split())
        assert result["character_count"] == len(test_text)
        assert result["analysis"] == mock_reply.text

    @patch("src.text_analyzer.TextAnalyzer.read_text_file")
    @patch("src.text_analyzer.TextAnalyzer.extract_plot_beats")
    def test_analyze_file(self, mock_extract_plot_beats, mock_read_text_file) -> None:
        mock_read_text_file.return_value = "Test story content"
        mock_extract_plot_beats.return_value = {"analysis": "Test analysis", "word_count": 3, "character_count": 18}

        analyzer = TextAnalyzer()
        result = analyzer.analyze_file("test_file.txt")

        assert result["file_path"] == "test_file.txt"
        assert result["file_stats"]["word_count"] == 3
        assert result["file_stats"]["character_count"] == 18
        assert result["analysis"] == "Test analysis"

        mock_read_text_file.assert_called_once_with("test_file.txt")
        mock_extract_plot_beats.assert_called_once_with("Test story content")
