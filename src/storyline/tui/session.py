"""Interactive terminal interface for the writing agent."""

import sys
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from dataclasses import dataclass

import pydantic_ai
from textual.app import App, ComposeResult
from textual.worker import Worker

from storyline.agent import DEFAULT_MODEL_NAME, ModelNameError, create_writer_agent, validate_model_name
from storyline.room import (
    ActivityChanged,
    AgendaChanged,
    ConversationReplaced,
    DraftRestored,
    ModelChanged,
    Notice,
    Operation,
    QueueChanged,
    ReplyDelta,
    ReplyFinished,
    ReplyStarted,
    RoomBusyError,
    RoomEvent,
    StoryFilesChanged,
    StoryRoom,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    UserMessageAdded,
)
from storyline.tui.agenda_panel import AgendaPanel
from storyline.tui.message_log import AgentReply, MessageLog
from storyline.tui.models import MessageKind, PromptCommand, TuiConfig, TuiState
from storyline.tui.prompt import PromptBlock
from storyline.tui.status_line import StatusLine
from storyline.workspace import Story, StoryLibrary, StorySelectionError, Workspace, WorkspaceEditError

if sys.platform == "win32":
    from storyline.tui.windows_input import ModifierAwareWindowsDriver

# Pydantic AI's first-run banner writes to the terminal Textual is drawing on.
pydantic_ai.BANNER_ENABLED = False

THINKING_STATUS = "Thinking…"
WRITING_STATUS = "Writing…"
INTERRUPTED_NOTICE = "Interrupted."
BUSY_NOTICE = "The agent is working · wait or press esc first."
STORY_HINT = "/story <name> opens a story · /new <name> creates one"


@dataclass(frozen=True)
class SlashCommand(PromptCommand):
    """A prompt command together with the handler that receives its argument."""

    run: Callable[[str], Awaitable[None]]


class StorylineTui(App[None]):
    """A streamed chat interface with slash commands, interruption and steering.

    It offers each room operation as a slash command or a key (``OPERATION_BINDINGS``) and draws each room event with
    one handler (``EVENT_HANDLERS``); ``tests/test_tui_parity.py`` fails when either misses one.
    """

    CSS = """
    StorylineTui, Screen { background: ansi_default; }
    """
    BINDINGS = [("ctrl+c", "quit", "Quit"), ("escape", "interrupt_or_clear", "Interrupt or clear")]
    ENABLE_COMMAND_PALETTE = False

    OPERATION_BINDINGS: Mapping[Operation, str] = {
        Operation.LIST_STORIES: "/stories",
        Operation.CREATE_STORY: "/new",
        Operation.OPEN_STORY: "/story",
        Operation.SEND_PROMPT: "enter",
        Operation.INTERRUPT: "escape",
        Operation.SET_MODEL: "/model",
        Operation.UNDO_LAST_TURN: "/undo",
        Operation.CLEAR_CONVERSATION: "/clear",
        Operation.READ_SCRIPT: "/script",
        Operation.LIST_LORE: "/lore",
        Operation.READ_LORE: "/lore",
    }
    """How the terminal offers each operation: a slash command, or a key."""

    EVENT_HANDLERS: Mapping[type, str] = {
        UserMessageAdded: "_show_user_message",
        ReplyStarted: "_show_reply_started",
        ReplyDelta: "_show_reply_delta",
        ReplyFinished: "_show_reply_finished",
        ToolCallStarted: "_show_tool_call_started",
        ToolCallFinished: "_show_tool_call_finished",
        ActivityChanged: "_show_activity",
        QueueChanged: "_show_queue",
        AgendaChanged: "_show_agenda",
        StoryFilesChanged: "_show_story_files_changed",
        TurnFinished: "_show_turn_finished",
        ConversationReplaced: "_show_conversation_replaced",
        DraftRestored: "_show_draft",
        ModelChanged: "_show_model_changed",
        Notice: "_show_notice",
    }
    """The method that draws each kind of room event."""

    def __init__(self, config: TuiConfig) -> None:
        # Native ANSI colors let the terminal's own (possibly transparent) background show through.
        super().__init__(ansi_color=True)
        self._config = config
        self._state = TuiState(default_model_name=config.initial_model_name)
        self._replies: dict[str, AgentReply] = {}
        self._activity = ""
        self._stop_listening: Callable[[], None] | None = None
        self._commands = {
            command.name: command
            for command in (
                SlashCommand(name="/help", description="List commands and keys", run=self._help_command),
                SlashCommand(name="/model", description="Show or set the active model", run=self._model_command),
                SlashCommand(name="/stories", description="List the stories in the workspace", run=self._stories_command),
                SlashCommand(name="/story", description="Show or switch the active story", run=self._story_command),
                SlashCommand(name="/new", description="Create a story and switch to it", run=self._new_command),
                SlashCommand(name="/script", description="Show the story text", run=self._script_command),
                SlashCommand(name="/lore", description="List lore files, or show one with /lore <file>", run=self._lore_command),
                SlashCommand(name="/undo", description="Remove the last exchange and put your message back to edit", run=self._undo_command),
                SlashCommand(name="/clear", description="Start a new conversation", run=self._clear_command),
                SlashCommand(name="/quit", description="Exit Storyline", run=self._quit_command),
            )
        }

    def compose(self) -> ComposeResult:
        yield AgendaPanel(id="agenda")
        yield MessageLog(id="messages")
        yield PromptBlock(commands=tuple(self._commands.values()))
        yield StatusLine(id="footer")

    async def on_mount(self) -> None:
        self._prompt.placeholder = self._prompt_placeholder()
        self._refresh_status()
        self._prompt.focus_input()
        await self._open_initial_story()

    async def on_prompt_block_submitted(self, message: PromptBlock.Submitted) -> None:
        text = message.value
        if not text:
            return
        if text.startswith("/"):
            self._prompt.clear()
            await self._run_command(text)
            return
        room = await self._require_room()
        if room is None:
            return
        self._prompt.clear()
        await room.send_prompt(text)

    def on_prompt_block_changed(self, _: PromptBlock.Changed) -> None:
        self._refresh_status()

    def on_message_log_reached_bottom(self, _: MessageLog.ReachedBottom) -> None:
        self._status.has_unseen_messages = False

    def on_message_log_new_messages(self, _: MessageLog.NewMessages) -> None:
        self._status.has_unseen_messages = True

    def action_interrupt_or_clear(self) -> None:
        """Stop the running agent turn, or clear the prompt when the agent is idle."""
        if self._state.room is not None and self._state.room.busy:
            self._state.room.interrupt()
        else:
            self._prompt.clear()
            self._prompt.focus_input()

    @property
    def _busy(self) -> bool:
        return self._state.room is not None and self._state.room.busy

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
        else:
            try:
                validate_model_name(argument)
            except ModelNameError as error:
                await self._message_log.add_message(MessageKind.ERROR, str(error))
                return
            if self._state.room is not None:
                await self._state.room.set_model(argument)
            else:
                self._state.default_model_name = argument
                await self._show_model_changed(ModelChanged(model_name=argument))

    async def _stories_command(self, _: str) -> None:
        await self._message_log.add_message(MessageKind.SYSTEM, await self._story_list())

    async def _story_command(self, argument: str) -> None:
        story = self._state.story
        if not argument:
            await self._message_log.add_message(
                MessageKind.SYSTEM,
                f"Active story: {story.name}" if story is not None else f"No story is open · {STORY_HINT}",
            )
            return
        if story is not None and story.name == argument:
            await self._message_log.add_message(MessageKind.SYSTEM, f"Already working on {argument}.")
            return
        if await self._refuse_while_busy():
            return
        try:
            opened = await self._config.library.switch(name=argument)
        except StorySelectionError as error:
            await self._message_log.add_message(MessageKind.ERROR, f"{error} · /stories lists stories")
            return
        await self._activate(opened)
        await self._message_log.add_message(MessageKind.SYSTEM, f"Switched to {opened.name}.")

    async def _new_command(self, argument: str) -> None:
        if not argument:
            await self._message_log.add_message(MessageKind.ERROR, "Name the story: /new <name>")
            return
        if await self._refuse_while_busy():
            return
        try:
            created = await self._config.library.create(name=argument)
        except StorySelectionError as error:
            await self._message_log.add_message(MessageKind.ERROR, str(error))
            return
        await self._activate(created)
        await self._message_log.add_message(MessageKind.SYSTEM, f"Created {created.name}.")

    async def _script_command(self, _: str) -> None:
        room = await self._require_room()
        if room is None:
            return
        script = await room.read_script()
        body = f"script.md · {len(script)} characters\n\n{script}" if script else "script.md is empty."
        await self._message_log.add_message(MessageKind.SYSTEM, body)

    async def _lore_command(self, argument: str) -> None:
        room = await self._require_room()
        if room is None:
            return
        if argument:
            try:
                text = await room.read_lore(argument)
            except WorkspaceEditError as error:
                await self._message_log.add_message(MessageKind.ERROR, str(error))
                return
            await self._message_log.add_message(MessageKind.SYSTEM, f"{argument} · {len(text)} characters\n\n{text}")
            return
        lines = [f"{lore.filename}  {lore.summary or '(missing summary)'}" for lore in await room.list_lore()]
        await self._message_log.add_message(MessageKind.SYSTEM, "\n".join(lines) or "No lore files.")

    async def _clear_command(self, _: str) -> None:
        room = await self._require_room()
        if room is None:
            return
        try:
            await room.clear_conversation()
        except RoomBusyError:
            await self._message_log.add_message(MessageKind.ERROR, BUSY_NOTICE)
            return
        await self._message_log.add_message(MessageKind.SYSTEM, "Started a new conversation. Story and lore are unchanged.")

    async def _undo_command(self, _: str) -> None:
        room = await self._require_room()
        if room is None:
            return
        try:
            undone = await room.undo_last_turn()
        except RoomBusyError:
            await self._message_log.add_message(MessageKind.ERROR, BUSY_NOTICE)
            return
        if undone:
            await self._message_log.add_message(MessageKind.SYSTEM, "Removed the last exchange; your message is back in the input. Story files are unchanged.")
        else:
            await self._message_log.add_message(MessageKind.SYSTEM, "Nothing to undo.")

    async def _quit_command(self, _: str) -> None:
        self.exit()

    async def _refuse_while_busy(self) -> bool:
        if self._busy:
            await self._message_log.add_message(MessageKind.ERROR, BUSY_NOTICE)
        return self._busy

    # Stories

    async def _open_initial_story(self) -> None:
        try:
            story = await self._config.library.open_initial(requested=self._config.requested_story)
        except StorySelectionError as error:
            await self._message_log.add_message(MessageKind.ERROR, str(error))
            story = None
        if story is None:
            await self._message_log.add_message(MessageKind.SYSTEM, f"Choose a story to work on.\n\n{await self._story_list()}")
        else:
            await self._activate(story)

    async def _activate(self, story: Story) -> None:
        """Make ``story`` the active one and show its own conversation."""
        if self._stop_listening is not None:
            self._stop_listening()
        room = await StoryRoom.open(story=story, agent=self._config.agent, default_model_name=self._state.model_name, spawn=self._run_as_worker)
        self._stop_listening = room.add_listener(self._show_event)
        self._state.room = room
        self._prompt.placeholder = self._prompt_placeholder()
        await self._message_log.clear()
        self._replies.clear()
        snapshot = room.snapshot()
        archived = snapshot.archived_conversation
        if archived is not None:
            await self._message_log.add_message(MessageKind.ERROR, f"{archived.reason}\nMoved it to {archived.archive_name} and started a new conversation.")
        else:
            await self._message_log.show_transcript(snapshot.entries, hidden_count=snapshot.hidden_entries)
        await self._agenda_panel.show_items(snapshot.agenda)
        if snapshot.agenda_error is not None:
            await self._message_log.add_message(MessageKind.ERROR, snapshot.agenda_error)
        if snapshot.model_from_story:
            await self._message_log.add_message(MessageKind.SYSTEM, f"Using {snapshot.model_name}, the model last used with {snapshot.story}.")

    def _run_as_worker(self, turns: Coroutine[None, None, None]) -> Worker[None]:
        """Run the room's turns as a worker, which ties them to the app and lets tests wait for them."""
        return self.run_worker(turns, group="agent", exclusive=False)

    async def _require_room(self) -> StoryRoom | None:
        """Return the active story's room, or explain how to open a story."""
        if self._state.room is None:
            await self._message_log.add_message(MessageKind.ERROR, f"No story is open · {STORY_HINT}")
        return self._state.room

    async def _story_list(self) -> str:
        names = await self._config.library.list_stories()
        if not names:
            return "This workspace has no stories yet · /new <name> creates one"
        active = self._state.story.name if self._state.story is not None else None
        lines = [f"{'*' if name == active else ' '} {name}" for name in names]
        return "\n".join([*lines, "", STORY_HINT])

    # Room events

    async def _show_event(self, event: RoomEvent) -> None:
        await getattr(self, self.EVENT_HANDLERS[type(event)])(event)

    async def _show_user_message(self, event: UserMessageAdded) -> None:
        await self._message_log.add_message(MessageKind.USER, event.text)

    async def _show_reply_started(self, event: ReplyStarted) -> None:
        self._replies[event.reply_id] = await self._message_log.add_reply()

    async def _show_reply_delta(self, event: ReplyDelta) -> None:
        reply = self._replies.get(event.reply_id)
        if reply is not None:
            await self._message_log.append_to_reply(reply, event.text)

    async def _show_reply_finished(self, event: ReplyFinished) -> None:
        reply = self._replies.pop(event.reply_id, None)
        if reply is not None:
            await reply.finish()

    async def _show_tool_call_started(self, event: ToolCallStarted) -> None:
        await self._message_log.add_tool_call(tool_call_id=event.tool_call_id, tool_name=event.tool_name, arguments=event.arguments)

    async def _show_tool_call_finished(self, event: ToolCallFinished) -> None:
        self._message_log.complete_tool_call(tool_call_id=event.tool_call_id, result=event.result, outcome=event.outcome)

    async def _show_activity(self, event: ActivityChanged) -> None:
        match event.activity:
            case "thinking":
                self._set_activity(THINKING_STATUS)
            case "writing":
                self._set_activity(WRITING_STATUS)
            case "using_tool":
                self._set_activity(f"Using {event.tool_name}…")
            case "idle":
                self._set_activity("")

    async def _show_queue(self, event: QueueChanged) -> None:
        self._prompt.show_queued(event.prompts)

    async def _show_agenda(self, event: AgendaChanged) -> None:
        await self._agenda_panel.show_items(event.items)

    async def _show_story_files_changed(self, _: StoryFilesChanged) -> None:
        """Do nothing: the terminal shows the script and lore only when asked with /script and /lore."""

    async def _show_turn_finished(self, event: TurnFinished) -> None:
        if event.outcome == "interrupted":
            await self._message_log.add_message(MessageKind.SYSTEM, INTERRUPTED_NOTICE)
        elif event.error is not None:
            await self._message_log.add_message(MessageKind.ERROR, event.error)

    async def _show_conversation_replaced(self, event: ConversationReplaced) -> None:
        await self._message_log.clear()
        self._replies.clear()
        await self._message_log.show_transcript(event.entries, hidden_count=event.hidden_entries)

    async def _show_draft(self, event: DraftRestored) -> None:
        self._prompt.value = "\n\n".join(part for part in (event.text, self._prompt.value) if part)
        self._prompt.focus_input()

    async def _show_model_changed(self, event: ModelChanged) -> None:
        self._prompt.placeholder = self._prompt_placeholder()
        note = " (from the next turn)" if self._busy else ""
        await self._message_log.add_message(MessageKind.SYSTEM, f"Model set to: {event.model_name}{note}")

    async def _show_notice(self, event: Notice) -> None:
        await self._message_log.add_message(MessageKind.ERROR if event.level == "error" else MessageKind.SYSTEM, event.text)

    # Presentation helpers

    def _set_activity(self, activity: str) -> None:
        self._activity = activity
        self._message_log.show_activity(activity)
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
    def _agenda_panel(self) -> AgendaPanel:
        return self.query_one(AgendaPanel)

    @property
    def _prompt(self) -> PromptBlock:
        return self.query_one(PromptBlock)

    @property
    def _status(self) -> StatusLine:
        return self.query_one(StatusLine)

    def _prompt_placeholder(self) -> str:
        story_name = self._state.story.name if self._state.story is not None else "no story"
        return f"> [{story_name} · {self._state.model_name}]"


def _key_hints(prompt: str) -> str:
    if prompt.startswith("/"):
        return "tab to complete · enter to run · esc to clear"
    if prompt:
        return "enter to send · shift+enter for a new line · esc to clear"
    return "enter to send · /help for commands · ctrl+c to quit"


def run_interactive_session(*, workspace: Workspace, story_name: str | None = None, model_name: str = DEFAULT_MODEL_NAME) -> None:
    """Run the interactive terminal UI until the user quits."""
    config = TuiConfig(
        library=StoryLibrary(workspace),
        agent=create_writer_agent(model_name=model_name),
        initial_model_name=model_name,
        requested_story=story_name,
    )
    app = StorylineTui(config)
    if sys.platform == "win32":
        app.driver_class = ModifierAwareWindowsDriver
    app.run()
