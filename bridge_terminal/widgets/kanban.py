from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Static

from ..core.memory import SharedMemory


class KanbanCard(Static):
    DEFAULT_CSS = """
    KanbanCard {
        background: $boost;
        border: tall $primary 50%;
        margin: 0 0 1 0;
        padding: 0 1;
        height: auto;
    }
    KanbanCard:hover { background: $accent 30%; }
    """

    def __init__(self, task: dict) -> None:
        super().__init__()
        self.task = task
        self.update_render()

    def update_render(self) -> None:
        title = self.task["title"]
        assignee = self.task.get("assignee") or "-"
        tid = self.task["id"]
        self.update(f"[b]#{tid}[/b] {title}\n[dim]@{assignee}[/dim]")


class KanbanColumn(Vertical):
    DEFAULT_CSS = """
    KanbanColumn {
        width: 1fr;
        min-width: 22;
        border: round $primary;
        padding: 0 1;
        margin: 0 1 0 0;
    }
    KanbanColumn > Label { text-style: bold; color: $accent; }
    KanbanColumn VerticalScroll { height: 1fr; }
    """

    def __init__(self, name: str) -> None:
        super().__init__()
        self.column_name = name
        self.slug = "".join(c if c.isalnum() else "-" for c in name).strip("-").lower() or "col"
        self.border_title = f" {name} "

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id=f"col-{self.slug}")


class KanbanBoard(Vertical):
    DEFAULT_CSS = """
    KanbanBoard { height: 1fr; }
    KanbanBoard > Horizontal#cols { height: 1fr; }
    KanbanBoard > Horizontal#controls { height: 3; dock: bottom; }
    KanbanBoard #new-title { width: 1fr; }
    KanbanBoard #new-assignee { width: 18; }
    """

    def __init__(self, memory: SharedMemory, columns: list[str]) -> None:
        super().__init__()
        self.memory = memory
        self.column_names = columns
        self._columns: dict[str, KanbanColumn] = {}

    def compose(self) -> ComposeResult:
        cols = Horizontal(id="cols")
        yield cols
        controls = Horizontal(id="controls")
        yield controls

    def on_mount(self) -> None:
        cols = self.query_one("#cols", Horizontal)
        for name in self.column_names:
            col = KanbanColumn(name)
            self._columns[name] = col
            cols.mount(col)

        controls = self.query_one("#controls", Horizontal)
        controls.mount(Input(placeholder="Nueva tarea...", id="new-title"))
        controls.mount(Input(placeholder="@assignee", id="new-assignee"))
        controls.mount(Button("+ Add", id="add", variant="success"))
        controls.mount(Button(">>", id="move", variant="primary"))
        controls.mount(Button("X", id="del", variant="error"))

        self.run_worker(self.refresh_tasks(), exclusive=True)

    async def refresh_tasks(self) -> None:
        for col in self._columns.values():
            scroll = col.query_one(VerticalScroll)
            await scroll.remove_children()

        tasks = await self.memory.list_tasks()
        for task in tasks:
            col = self._columns.get(task["column"]) or self._columns[self.column_names[0]]
            scroll = col.query_one(VerticalScroll)
            scroll.mount(KanbanCard(task))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        title_input = self.query_one("#new-title", Input)
        assignee_input = self.query_one("#new-assignee", Input)
        bid = event.button.id

        if bid == "add":
            title = title_input.value.strip()
            if not title:
                return
            assignee = assignee_input.value.strip() or None
            await self.memory.add_task(title, "", self.column_names[0], assignee)
            title_input.value = ""
            assignee_input.value = ""
            await self.refresh_tasks()
        elif bid == "move":
            task_id = self._selected_id(title_input.value)
            if task_id is None:
                return
            tasks = await self.memory.list_tasks()
            cur = next((t for t in tasks if t["id"] == task_id), None)
            if not cur:
                return
            idx = self.column_names.index(cur["column"])
            nxt = self.column_names[min(idx + 1, len(self.column_names) - 1)]
            await self.memory.move_task(task_id, nxt)
            title_input.value = ""
            await self.refresh_tasks()
        elif bid == "del":
            task_id = self._selected_id(title_input.value)
            if task_id is None:
                return
            await self.memory.delete_task(task_id)
            title_input.value = ""
            await self.refresh_tasks()

    @staticmethod
    def _selected_id(text: str) -> int | None:
        text = text.strip()
        if text.startswith("#"):
            text = text[1:]
        try:
            return int(text)
        except ValueError:
            return None
