"""Interactive terminal interface for the writing agent."""

import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass

from pydantic_ai import Agent, AgentRun
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import (
    AgentStreamEvent,
    EnqueuedMessagesEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    HandleResponseEvent,
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from textual.app import App, ComposeResult

from storyline.agent import DEFAULT_MODEL_NAME, create_writer_agent, turn_prompt
from storyline.tui.message_log import AgentReply, MessageLog
from storyline.tui.models import MessageKind, PromptCommand, TuiConfig, TuiState
from storyline.tui.prompt import PromptBlock
from storyline.tui.status_line import StatusLine
from storyline.tui.transcript import tool_result_summary, transcript_entries
from storyline.workspace import ConversationHistoryError, ScriptWorkspace

THINKING_STATUS = "Thinking…"
WRITING_STATUS = "Writing…"
INTERRUPTED_NOTICE = "Interrupted."
RESTORED_ENTRY_LIMIT = 40


@dataclass(frozen=True)
class SlashCommand(PromptCommand):
    """A prompt command together with the handler that receives its argument."""

    run: Callable[[str], Awaitable[None]]


@dataclass
class QueuedPrompt:
    """A prompt typed while the agent was working, waiting to be delivered into the run."""

    text: str
    enqueue_id: str | None = None


class StorylineTui(App[None]):
    """A streamed chat interface with slash commands, interruption and steering."""

    CSS = """
    StorylineTui, Screen { background: transparent; }
    """
    BINDINGS = [("ctrl+c", "quit", "Quit"), ("escape", "interrupt_or_clear", "Interrupt or clear")]
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, config: TuiConfig) -> None:
        super().__init__()
        self._config = config
        self._state = TuiState(model_name=config.initial_model_name)
        self._busy = False
        self._run: AgentRun[ScriptWorkspace, str] | None = None
        self._reply: AgentReply | None = None
        self._queue: list[QueuedPrompt] = []
        self._activity = ""
        self._commands = {
            command.name: command
            for command in (
                SlashCommand(name="/help", description="List commands and keys", run=self._help_command),
                SlashCommand(name="/model", description="Show or set the active model", run=self._model_command),
                SlashCommand(name="/script", description="Show the story text", run=self._script_command),
                SlashCommand(name="/lore", description="List lore files", run=self._lore_command),
                SlashCommand(name="/clear", description="Start a new conversation", run=self._clear_command),
                SlashCommand(name="/quit", description="Exit Storyline", run=self._quit_command),
            )
        }

    def compose(self) -> ComposeResult:
        yield MessageLog(id="messages")
        yield PromptBlock(commands=tuple(self._commands.values()))
        yield StatusLine(id="footer")

    async def on_mount(self) -> None:
        self._prompt.placeholder = self._prompt_placeholder()
        self._refresh_status()
        self._prompt.focus_input()
        await self._restore_history()

    async def on_prompt_block_submitted(self, message: PromptBlock.Submitted) -> None:
        text = message.value
        if not text:
            return
        self._prompt.clear()
        if text.startswith("/"):
            await self._run_command(text)
        elif self._busy:
            self._queue.append(QueuedPrompt(text=text))
            self._enqueue_waiting_prompts()
        else:
            await self._message_log.add_message(MessageKind.USER, text)
            self._start_turn(text)

    def on_prompt_block_changed(self, _: PromptBlock.Changed) -> None:
        self._refresh_status()

    def on_message_log_reached_bottom(self, _: MessageLog.ReachedBottom) -> None:
        self._status.has_unseen_messages = False

    def on_message_log_new_messages(self, _: MessageLog.NewMessages) -> None:
        self._status.has_unseen_messages = True

    def action_interrupt_or_clear(self) -> None:
        """Stop the running agent turn, or clear the prompt when the agent is idle."""
        if not self._busy:
            self._prompt.clear()
            self._prompt.focus_input()
        elif self._run is not None:
            self._run.cancel()
        else:
            self.workers.cancel_group(self, "agent")

    # Slash commands

    async def _run_command(self, text: str) -> None:
        name, _, argument = text.partition(" ")
        command = self._commands.get(name)
        if command is None:
            await self._message_log.add_message(MessageKind.ERROR, f"Unknown command: {name} · /help lists commands")
            return
        await command.run(argument.strip())

    async def _help_command(self, _: str) -> None:
        width = max(len(name) for name in self._commands)
        lines = [f"{command.name:<{width}}  {command.description}" for command in self._commands.values()]
        lines += [
            "",
            "enter        send; while the agent works, queue a message it reads at its next step",
            "shift+enter  new line (ctrl+j in terminals without shift+enter)",
            "esc          interrupt the agent, or clear the prompt",
            "tab          complete a command · ctrl+c quit",
        ]
        await self._message_log.add_message(MessageKind.SYSTEM, "\n".join(lines))

    async def _model_command(self, argument: str) -> None:
        if not argument:
            await self._message_log.add_message(MessageKind.SYSTEM, f"Active model: {self._state.model_name}")
            return
        self._state.model_name = argument
        self._prompt.placeholder = self._prompt_placeholder()
        note = " (from the next turn)" if self._busy else ""
        await self._message_log.add_message(MessageKind.SYSTEM, f"Model set to: {argument}{note}")

    async def _script_command(self, _: str) -> None:
        script = await self._config.workspace.read_script()
        body = f"script.md · {len(script)} characters\n\n{script}" if script else "script.md is empty."
        await self._message_log.add_message(MessageKind.SYSTEM, body)

    async def _lore_command(self, _: str) -> None:
        lore_files = await self._config.workspace.list_lore()
        lines = [f"{lore.filename}  {lore.summary or '(missing summary)'}" for lore in lore_files]
        await self._message_log.add_message(MessageKind.SYSTEM, "\n".join(lines) or "No lore files.")

    async def _clear_command(self, _: str) -> None:
        if self._busy:
            await self._message_log.add_message(MessageKind.ERROR, "The agent is working · wait or press esc first.")
            return
        await self._save_message_history([])
        await self._message_log.clear()
        await self._message_log.add_message(MessageKind.SYSTEM, "Started a new conversation. Story and lore are unchanged.")

    async def _quit_command(self, _: str) -> None:
        self.exit()

    # Agent turns

    def _start_turn(self, prompt: str) -> None:
        self._busy = True
        self._set_activity(THINKING_STATUS)
        self.run_worker(self._run_turn(prompt), group="agent", exclusive=True)

    async def _run_turn(self, prompt: str) -> None:
        log = self._message_log
        completed = False
        try:
            async with self._config.agent.iter(
                await turn_prompt(self._config.workspace, prompt),
                deps=self._config.workspace,
                message_history=self._state.message_history,
                model=self._state.model_name,
            ) as run:
                self._run = run
                self._enqueue_waiting_prompts()
                async for node in run:
                    if Agent.is_model_request_node(node) or Agent.is_call_tools_node(node):
                        async with node.stream(run.ctx) as events:
                            await self._show_events(events)
                    if Agent.is_call_tools_node(node):
                        await self._save_message_history(run.all_messages())
                self._run = None
            await self._save_message_history(run.all_messages())
            completed = True
        except RunCancelled as error:
            await self._save_message_history(error.all_messages())
            await log.add_message(MessageKind.SYSTEM, INTERRUPTED_NOTICE)
        except asyncio.CancelledError:
            await log.add_message(MessageKind.SYSTEM, INTERRUPTED_NOTICE)
            raise
        except Exception as error:
            await log.add_message(MessageKind.ERROR, str(error))
        finally:
            self._run = None
            await self._finish_reply()
            self._busy = False
            self._set_activity("")
            await self._handle_undelivered_prompts(start_follow_up=completed)

    async def _show_events(self, events: AsyncIterable[AgentStreamEvent | HandleResponseEvent]) -> None:
        log = self._message_log
        async for event in events:
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                self._set_activity(WRITING_STATUS)
                await self._finish_reply()
                self._reply = await log.add_reply()
                await log.append_to_reply(self._reply, event.part.content)
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                if self._reply is None:
                    self._reply = await log.add_reply()
                await log.append_to_reply(self._reply, event.delta.content_delta)
            elif isinstance(event, FunctionToolCallEvent):
                await self._finish_reply()
                self._set_activity(f"Using {event.part.tool_name}…")
                await log.add_tool_call(
                    tool_call_id=event.part.tool_call_id,
                    tool_name=event.part.tool_name,
                    arguments=event.part.args_as_json_str(),
                )
            elif isinstance(event, FunctionToolResultEvent):
                self._set_activity(THINKING_STATUS)
                result, outcome = tool_result_summary(event.part)
                log.complete_tool_call(tool_call_id=event.part.tool_call_id, result=result, outcome=outcome)
            elif isinstance(event, EnqueuedMessagesEvent):
                await self._show_delivered_prompt(event.enqueue_id)

    async def _finish_reply(self) -> None:
        if self._reply is not None:
            await self._reply.finish()
            self._reply = None

    async def _save_message_history(self, message_history: list[ModelMessage]) -> None:
        self._state.message_history = message_history
        await self._config.workspace.write_message_history(message_history=message_history)

    async def _restore_history(self) -> None:
        workspace = self._config.workspace
        try:
            history = await workspace.read_message_history()
        except ConversationHistoryError as error:
            archive_name = await workspace.archive_message_history()
            await self._message_log.add_message(
                MessageKind.ERROR, f"{error}\nMoved it to {archive_name} and started a new conversation."
            )
            return
        self._state.message_history = history
        entries = transcript_entries(history)
        shown = entries[-RESTORED_ENTRY_LIMIT:]
        await self._message_log.show_transcript(shown, hidden_count=len(entries) - len(shown))

    # Steering queue

    def _enqueue_waiting_prompts(self) -> None:
        """Hand queued prompts to the running agent, which reads them at its next model request."""
        if self._run is not None:
            for queued in self._queue:
                if queued.enqueue_id is None:
                    queued.enqueue_id = self._run.enqueue(queued.text)
        self._prompt.show_queued(tuple(queued.text for queued in self._queue))

    async def _show_delivered_prompt(self, enqueue_id: str) -> None:
        delivered = [queued for queued in self._queue if queued.enqueue_id == enqueue_id]
        for queued in delivered:
            self._queue.remove(queued)
            await self._finish_reply()
            await self._message_log.add_message(MessageKind.USER, queued.text)
        self._prompt.show_queued(tuple(queued.text for queued in self._queue))

    async def _handle_undelivered_prompts(self, *, start_follow_up: bool) -> None:
        """Send prompts the finished run never read as a new turn, or return them to the input after an interruption."""
        undelivered = "\n\n".join(queued.text for queued in self._queue)
        self._queue.clear()
        self._prompt.show_queued(())
        if not undelivered:
            return
        if start_follow_up:
            await self._message_log.add_message(MessageKind.USER, undelivered)
            self._start_turn(undelivered)
        else:
            self._prompt.value = "\n\n".join(part for part in (undelivered, self._prompt.value) if part)

    # Presentation helpers

    def _set_activity(self, activity: str) -> None:
        self._activity = activity
        self._refresh_status()

    def _refresh_status(self) -> None:
        if self._activity:
            self._status.text = f"{self._activity} · enter to queue a message · esc to interrupt"
        else:
            self._status.text = _key_hints(self._prompt.value)

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
    return "enter to send · /help for commands · ctrl+c to quit"


def run_interactive_session(*, workspace: ScriptWorkspace, model_name: str = DEFAULT_MODEL_NAME) -> None:
    """Run the interactive terminal UI until the user quits."""
    config = TuiConfig(
        workspace=workspace,
        agent=create_writer_agent(model_name=model_name),
        initial_model_name=model_name,
    )
    StorylineTui(config).run()
