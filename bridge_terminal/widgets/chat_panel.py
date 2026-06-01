from __future__ import annotations

import asyncio

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Input, Static

from ..core.agents import Agent
from ..core.shell import ShellRunner, extract_shell_blocks


class ChatPanel(Container):
    """A single chat panel bound to one Agent (model + role)."""

    DEFAULT_CSS = """
    ChatPanel {
        border: round $primary;
        padding: 0 1;
        height: 1fr;
    }
    ChatPanel.-focused { border: round $accent; }
    ChatPanel > VerticalScroll { height: 1fr; }
    ChatPanel #status { dock: bottom; height: 1; color: $text-muted; }
    ChatPanel Input { dock: bottom; }
    """

    busy: reactive[bool] = reactive(False)

    def __init__(
        self,
        agent: Agent,
        shell: ShellRunner,
        auto_exec: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self.shell = shell
        self.auto_exec = auto_exec
        self.border_title = f"  {agent.config.title}  "
        self.border_subtitle = f"  {agent.config.role}  "
        self._scroll: VerticalScroll | None = None
        self._status: Static | None = None
        self._messages: list[Static] = []
        self._current_stream: Static | None = None
        self._stream_buffer: str = ""

    def compose(self) -> ComposeResult:
        self._scroll = VerticalScroll(id="scroll")
        yield self._scroll
        self._status = Static("idle", id="status")
        yield self._status
        yield Input(placeholder=f"Mensaje a {self.agent.config.id} ... (Enter para enviar)")

    def _append(self, renderable) -> Static:
        widget = Static(renderable)
        self._messages.append(widget)
        assert self._scroll is not None
        self._scroll.mount(widget)
        self._scroll.scroll_end(animate=False)
        return widget

    def _set_status(self, text: str) -> None:
        if self._status is not None:
            self._status.update(text)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        if not prompt or self.busy:
            return
        event.input.value = ""
        await self.send(prompt)

    async def send(self, prompt: str) -> None:
        if self.busy:
            return
        self.busy = True
        self._set_status("thinking...")

        self._append(Panel(Text(prompt), title="you", border_style="green", expand=True))
        await self.agent.remember_user(prompt)

        messages = await self.agent.build_messages(prompt)

        self._current_stream = self._append(
            Panel(Text("...", style="dim"), title=self.agent.config.id, border_style="cyan", expand=True)
        )
        self._stream_buffer = ""

        try:
            async for chunk in self.agent.client.stream(messages):
                self._stream_buffer += chunk
                self._current_stream.update(
                    Panel(
                        Markdown(self._stream_buffer),
                        title=self.agent.config.id,
                        border_style="cyan",
                        expand=True,
                    )
                )
                assert self._scroll is not None
                self._scroll.scroll_end(animate=False)
        except Exception as exc:  # noqa: BLE001
            self._stream_buffer += f"\n[error] {exc}"
            self._current_stream.update(
                Panel(self._stream_buffer, title=self.agent.config.id, border_style="red")
            )

        final = self._stream_buffer.strip() or "(empty)"
        await self.agent.remember_assistant(final)
        memo_count = await self.agent.extract_memos(final)

        status_bits = []
        if memo_count:
            status_bits.append(f"{memo_count} memo(s) saved")

        blocks = extract_shell_blocks(final)
        if blocks and self.auto_exec:
            for cmd in blocks:
                await self._run_shell_block(cmd)
            status_bits.append(f"{len(blocks)} command(s) executed")
        elif blocks:
            status_bits.append(f"{len(blocks)} shell block(s) detected (auto-exec off)")

        self._set_status(" | ".join(status_bits) if status_bits else "idle")
        self.busy = False

    async def _run_shell_block(self, command: str) -> None:
        self._append(Panel(Text(command, style="yellow"), title="$ shell", border_style="yellow"))
        out_widget = self._append(Panel(Text("", style="dim"), title="output", border_style="magenta"))
        buf = ""
        async for line in self.shell.stream(command):
            buf += line
            out_widget.update(Panel(Text(buf), title="output", border_style="magenta"))
            assert self._scroll is not None
            self._scroll.scroll_end(animate=False)
            await asyncio.sleep(0)
        await self.agent.memory.add_note(
            self.agent.config.id, f"ran `{command}` -> {buf[-200:]}", tag="shell"
        )

    def on_focus(self) -> None:
        self.add_class("-focused")

    def on_blur(self) -> None:
        self.remove_class("-focused")
