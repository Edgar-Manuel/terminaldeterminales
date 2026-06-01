from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, TabbedContent, TabPane

from .core.agents import Agent
from .core.config import AppConfig
from .core.memory import SharedMemory
from .core.shell import ShellRunner
from .widgets.chat_panel import ChatPanel
from .widgets.kanban import KanbanBoard
from .widgets.shell_panel import ShellPanel


class BridgeTerminal(App):
    """Bridge Terminal: a terminal of terminals running multiple AI models."""

    CSS = """
    Screen { background: $surface; }
    #main { height: 1fr; }
    #panels {
        grid-size: 2 2;
        grid-gutter: 1 1;
        width: 2fr;
        height: 1fr;
    }
    #side { width: 1fr; min-width: 40; height: 1fr; }
    #broadcast { dock: bottom; height: 3; }
    #broadcast Input { width: 1fr; }
    .auto-exec-on { background: $success 30%; }
    """

    BINDINGS = [
        Binding("ctrl+b", "focus_broadcast", "Broadcast"),
        Binding("ctrl+e", "toggle_auto_exec", "Auto-exec"),
        Binding("ctrl+k", "focus_kanban", "Kanban"),
        Binding("ctrl+s", "focus_shell", "Shell"),
        Binding("ctrl+l", "clear_focused", "Clear panel"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("f1", "show_help", "Help"),
    ]

    auto_exec: reactive[bool] = reactive(False)

    def __init__(self, config_path: str = "config.json") -> None:
        super().__init__()
        self.cfg = AppConfig.load(config_path)
        self.memory = SharedMemory(self.cfg.db_path)
        self.shell_runner = ShellRunner(self.cfg.workspace)
        self.agents: list[Agent] = []
        self.panels: list[ChatPanel] = []
        self.title = "Bridge Terminal"
        self.sub_title = "multi-agent TUI"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            yield Grid(id="panels")
            with Vertical(id="side"):
                with TabbedContent(initial="tab-kanban"):
                    with TabPane("Kanban", id="tab-kanban"):
                        yield KanbanBoard(self.memory, self.cfg.kanban_columns)
                    with TabPane("Shell", id="tab-shell"):
                        yield ShellPanel(self.shell_runner)
        with Horizontal(id="broadcast"):
            yield Input(
                placeholder="Broadcast a TODOS los paneles (Ctrl+B) | prefijo @id para uno solo",
                id="broadcast-input",
            )
        yield Footer()

    async def on_mount(self) -> None:
        await self.memory.init()

        grid = self.query_one("#panels", Grid)
        for panel_cfg in self.cfg.panels[:4]:
            agent = Agent.from_config(panel_cfg, self.memory)
            self.agents.append(agent)
            chat = ChatPanel(agent, self.shell_runner, auto_exec=self.auto_exec)
            self.panels.append(chat)
            await grid.mount(chat)

        self.notify(
            f"Cargados {len(self.panels)} agentes. F1 para ayuda.",
            severity="information",
        )

    def watch_auto_exec(self, value: bool) -> None:
        for p in self.panels:
            p.auto_exec = value
        self.sub_title = f"auto-exec: {'ON' if value else 'OFF'}"

    def action_toggle_auto_exec(self) -> None:
        self.auto_exec = not self.auto_exec
        self.notify(
            f"Auto-exec de bloques shell: {'ON' if self.auto_exec else 'OFF'}",
            severity="warning" if self.auto_exec else "information",
        )

    def action_focus_broadcast(self) -> None:
        self.query_one("#broadcast-input", Input).focus()

    def action_focus_kanban(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-kanban"

    def action_focus_shell(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-shell"

    def action_clear_focused(self) -> None:
        focused = self.focused
        while focused is not None and not isinstance(focused, ChatPanel):
            focused = focused.parent  # type: ignore[assignment]
        if isinstance(focused, ChatPanel):
            for msg in list(focused._messages):
                msg.remove()
            focused._messages.clear()

    def action_show_help(self) -> None:
        self.notify(
            "Ctrl+B broadcast | Ctrl+E auto-exec | Ctrl+K kanban | Ctrl+S shell | "
            "Ctrl+L limpiar panel | @<id> en broadcast = enviar a un solo agente",
            timeout=10,
        )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "broadcast-input":
            return
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

        target_id = None
        if text.startswith("@"):
            head, _, rest = text.partition(" ")
            target_id = head[1:]
            text = rest.strip()
            if not text:
                self.notify("escribe un mensaje despues de @id", severity="warning")
                return

        targets = self.panels
        if target_id:
            targets = [p for p in self.panels if p.agent.config.id == target_id]
            if not targets:
                self.notify(f"agente '{target_id}' no encontrado", severity="error")
                return

        await asyncio.gather(*(p.send(text) for p in targets))


def main() -> None:
    BridgeTerminal().run()


if __name__ == "__main__":
    main()
