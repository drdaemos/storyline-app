import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from src.cli import analyze, cli, serve


class TestCLICommands:
    def test_cli_group_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "API server and text analysis" in result.output
        assert "analyze" in result.output
        assert "serve" in result.output
        assert "chat" not in result.output
        assert "sync-characters" not in result.output

    @patch("src.cli.TextAnalyzer")
    def test_analyze_command_with_file(self, mock_analyzer: Mock) -> None:
        mock_instance = mock_analyzer.return_value
        mock_instance.analyze_file.return_value = {
            "file_path": "test.txt",
            "file_stats": {"word_count": 10, "character_count": 50},
            "analysis": "Test analysis result",
        }

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("Test content")
            tmp_path = tmp.name

        try:
            result = runner.invoke(analyze, [tmp_path])
            assert result.exit_code == 0
            mock_instance.analyze_file.assert_called_once_with(tmp_path)
        finally:
            Path(tmp_path).unlink()

    @patch("src.cli.TextAnalyzer")
    def test_analyze_command_with_output_file(self, mock_analyzer: Mock) -> None:
        mock_instance = mock_analyzer.return_value
        mock_instance.analyze_file.return_value = {
            "file_path": "test.txt",
            "file_stats": {"word_count": 4, "character_count": 20},
            "analysis": "Summary body",
        }

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as input_tmp:
            input_tmp.write("Test content")
            input_path = input_tmp.name

        output_path = f"{input_path}.out"
        try:
            result = runner.invoke(analyze, [input_path, "--output", output_path])
            assert result.exit_code == 0
            assert Path(output_path).exists()
            output_text = Path(output_path).read_text(encoding="utf-8")
            assert "Summary body" in output_text
        finally:
            Path(input_path).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_analyze_command_nonexistent_file(self) -> None:
        runner = CliRunner()
        result = runner.invoke(analyze, ["nonexistent_file.txt"])
        assert result.exit_code != 0

    def test_serve_command_uses_env_defaults(self) -> None:
        runner = CliRunner()
        mock_uvicorn = Mock()

        with patch.dict("os.environ", {"HOST": "127.0.0.1", "PORT": "8123"}, clear=False), patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            result = runner.invoke(serve, [])

        assert result.exit_code == 0
        mock_uvicorn.run.assert_called_once_with(
            "src.fastapi_server:app",
            host="127.0.0.1",
            port=8123,
            reload=False,
            log_level="info",
        )

    def test_serve_command_prefers_cli_options(self) -> None:
        runner = CliRunner()
        mock_uvicorn = Mock()

        with patch.dict("os.environ", {"HOST": "127.0.0.1", "PORT": "8123"}, clear=False), patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            result = runner.invoke(serve, ["--host", "0.0.0.0", "--port", "9000", "--reload"])

        assert result.exit_code == 0
        mock_uvicorn.run.assert_called_once_with(
            "src.fastapi_server:app",
            host="0.0.0.0",
            port=9000,
            reload=True,
            log_level="info",
        )
