from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Input, Static

from ..core.shell import ShellRunner


class ShellPanel(Container):
    """A small interactive shell bound to the sandbox workspace."""

    DEFAULT_CSS = """
    ShellPanel { border: round $warning; padding: 0 1; height: 1fr; }
    ShellPanel > VerticalScroll { height: 1fr; }
    ShellPanel Input { dock: bottom; }
    """

    def __init__(self, runner: ShellRunner, **kwargs) -> None:
        super().__init__(**kwargs)
        self.runner = runner
        self.border_title = "  $ shell (sandbox)  "
        self._scroll: VerticalScroll | None = None
        self._buffer = ""
        self._output: Static | None = None

    def compose(self) -> ComposeResult:
        self._scroll = VerticalScroll()
        yield self._scroll
        yield Input(placeholder=f"comando en {self.runner.workspace} ...")

    def on_mount(self) -> None:
        assert self._scroll is not None
        self._output = Static(Text(f"workspace: {self.runner.workspace}\n", style="dim"))
        self._scroll.mount(self._output)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if not cmd:
            return
        event.input.value = ""
        self._buffer += f"\n$ {cmd}\n"
        self._refresh()
        async for line in self.runner.stream(cmd):
            self._buffer += line
            self._refresh()

    def _refresh(self) -> None:
        if self._output is None or self._scroll is None:
            return
        self._output.update(Text(self._buffer))
        self._scroll.scroll_end(animate=False)
