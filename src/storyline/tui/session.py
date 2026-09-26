"""Interactive terminal interface for the writing agent."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic_ai import AgentRunResultEvent
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolReturnPart,
)
from textual.app import App, ComposeResult

from storyline.agent import DEFAULT_MODEL_NAME, create_writer_agent
from storyline.tui.message_log import ChatMessage, MessageLog
from storyline.tui.models import MessageKind, PromptCommand, TuiConfig, TuiState
from storyline.tui.prompt import PromptBlock
from storyline.tui.status_line import StatusLine
from storyline.workspace import ScriptWorkspace

THINKING_STATUS = "Thinking…"
WRITING_STATUS = "Writing…"


@dataclass(frozen=True)
class SlashCommand(PromptCommand):
    """A prompt command together with the handler that receives its argument."""

    run: Callable[[str], Awaitable[None]]


class StorylineTui(App[None]):
    """A minimal streamed chat interface with slash commands."""

    CSS = """
    StorylineTui, Screen { background: transparent; }
    """
    BINDINGS = [("ctrl+c", "quit", "Quit"), ("escape", "clear_prompt", "Clear prompt")]
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, config: TuiConfig) -> None:
        super().__init__()
        self._config = config
        self._state = TuiState(model_name=config.initial_model_name)
        self._commands = {
            command.name: command
            for command in (
                SlashCommand(name="/model", description="Show or set the active model", run=self._model_command),
            )
        }

    def compose(self) -> ComposeResult:
        yield MessageLog(id="messages")
        yield PromptBlock(commands=tuple(self._commands.values()))
        yield StatusLine(id="footer")

    async def on_mount(self) -> None:
        self._state.message_history = await self._config.workspace.read_message_history()
        self._prompt.placeholder = self._prompt_placeholder()
        self._status.text = _key_hints("")
        self._prompt.focus_input()

    async def on_prompt_block_submitted(self, message: PromptBlock.Submitted) -> None:
        text = message.value
        if not text:
            return
        self._prompt.clear()
        if text.startswith("/"):
            await self._run_command(text)
            return

        await self._message_log.add_message(MessageKind.USER, text)
        self._prompt.input_disabled = True
        self._status.text = THINKING_STATUS
        self.run_worker(self._run_turn(text), group="agent", exclusive=True)

    def on_prompt_block_changed(self, message: PromptBlock.Changed) -> None:
        """Refresh key hints as the prompt changes."""
        self._status.text = _key_hints(message.value)

    def on_message_log_reached_bottom(self, _: MessageLog.ReachedBottom) -> None:
        self._status.has_unseen_messages = False

    def on_message_log_new_messages(self, _: MessageLog.NewMessages) -> None:
        self._status.has_unseen_messages = True

    def action_clear_prompt(self) -> None:
        """Clear the current input."""
        self._prompt.clear()
        self._prompt.focus_input()

    async def _run_command(self, text: str) -> None:
        name, _, argument = text.partition(" ")
        command = self._commands.get(name)
        if command is None:
            await self._message_log.add_message(MessageKind.ERROR, f"Unknown command: {name}")
            return
        await command.run(argument.strip())

    async def _model_command(self, argument: str) -> None:
        if not argument:
            await self._message_log.add_message(MessageKind.SYSTEM, f"Active model: {self._state.model_name}")
            return
        self._state.model_name = argument
        self._prompt.placeholder = self._prompt_placeholder()
        await self._message_log.add_message(MessageKind.SYSTEM, f"Model set to: {argument}")

    async def _run_turn(self, prompt: str) -> None:
        log = self._message_log
        reply: ChatMessage | None = None
        try:
            async with self._config.agent.run_stream_events(
                prompt,
                deps=self._config.workspace,
                message_history=self._state.message_history,
                model=self._state.model_name,
            ) as events:
                async for event in events:
                    if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                        self._status.text = WRITING_STATUS
                        reply = await log.add_message(MessageKind.AGENT, event.part.content)
                    elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                        if reply is None:
                            reply = await log.add_message(MessageKind.AGENT, "")
                        log.append_to_message(reply, event.delta.content_delta)
                    elif isinstance(event, FunctionToolCallEvent):
                        self._status.text = f"Using {event.part.tool_name}…"
                        await log.add_tool_call(
                            tool_call_id=event.part.tool_call_id,
                            tool_name=event.part.tool_name,
                            arguments=event.part.args_as_json_str(),
                        )
                    elif isinstance(event, FunctionToolResultEvent):
                        self._status.text = THINKING_STATUS
                        result = event.part
                        log.complete_tool_call(
                            tool_call_id=result.tool_call_id,
                            content=result.content if isinstance(result, ToolReturnPart) else result.model_response(),
                            outcome=result.outcome if isinstance(result, ToolReturnPart) else "retry",
                        )
                        await self._save_message_history(events.all_messages())
                    elif isinstance(event, AgentRunResultEvent):
                        await self._save_message_history(event.result.all_messages())
        except RunCancelled as error:
            await self._save_message_history(error.all_messages())
            await log.add_message(MessageKind.ERROR, str(error))
        except Exception as error:
            await log.add_message(MessageKind.ERROR, str(error))
        finally:
            self._prompt.input_disabled = False
            self._prompt.focus_input()
            self._status.text = _key_hints(self._prompt.value)

    async def _save_message_history(self, message_history: list[ModelMessage]) -> None:
        self._state.message_history = message_history
        await self._config.workspace.write_message_history(message_history=message_history)

    @property
    def _message_log(self) -> MessageLog:
        return self.query_one(MessageLog)

    @property
    def _prompt(self) -> PromptBlock:
        return self.query_one(PromptBlock)

    @property
    def _status(self) -> StatusLine:
        return self.query_one(StatusLine)

    def _prompt_placeholder(self) -> str:
        return f"> [{self._state.model_name}]"


def _key_hints(prompt: str) -> str:
    if prompt.startswith("/"):
        return "tab to complete · enter to run · esc to clear"
    if prompt:
        return "enter to send · shift+enter for a new line · esc to clear"
    return "enter to send · shift+enter for a new line · ctrl+c to quit"


def run_interactive_session(*, workspace: ScriptWorkspace, model_name: str = DEFAULT_MODEL_NAME) -> None:
    """Run the interactive terminal UI until the user quits."""
    config = TuiConfig(
        workspace=workspace,
        agent=create_writer_agent(model_name=model_name),
        initial_model_name=model_name,
    )
    StorylineTui(config).run()
