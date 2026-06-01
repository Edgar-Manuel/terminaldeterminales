from __future__ import annotations

from dataclasses import dataclass

from .config import PanelConfig
from .memory import SharedMemory
from .models import ModelClient


SHARED_CONTEXT_HEADER = (
    "## SHARED MEMORY (context written by other agents)\n"
    "Read this before answering; you can refer to other agents by id.\n\n"
)


@dataclass
class Agent:
    """An agent is a panel (role + model + system prompt) backed by shared memory."""

    config: PanelConfig
    client: ModelClient
    memory: SharedMemory

    @classmethod
    def from_config(cls, panel: PanelConfig, memory: SharedMemory) -> "Agent":
        return cls(config=panel, client=ModelClient(panel.model), memory=memory)

    async def build_messages(self, user_prompt: str) -> list[dict[str, str]]:
        history = await self.memory.get_history(self.config.id, limit=20)
        notes = await self.memory.recent_notes(limit=10)

        shared = SHARED_CONTEXT_HEADER
        if notes:
            for n in notes:
                tag = f"[{n['tag']}]" if n["tag"] else ""
                shared += f"- @{n['author']} {tag}: {n['content']}\n"
        else:
            shared += "(empty)\n"

        system = (
            f"{self.config.system_prompt}\n\n"
            f"Your agent id is: {self.config.id}\n"
            f"Your role is: {self.config.role}\n"
            f"You can write to shared memory by adding a line:\n"
            f"  MEMO[tag]: short message for other agents\n"
            f"and request shell execution with ```sh ... ``` blocks.\n\n"
            f"{shared}"
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for entry in history:
            messages.append({"role": entry.role, "content": entry.content})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    async def remember_user(self, content: str) -> None:
        await self.memory.add_message(self.config.id, "user", content)

    async def remember_assistant(self, content: str) -> None:
        await self.memory.add_message(self.config.id, "assistant", content)

    async def extract_memos(self, text: str) -> int:
        """Find `MEMO[tag]: ...` lines and write them into shared notes. Returns count."""
        import re

        count = 0
        for match in re.finditer(r"MEMO\[([^\]]*)\]:\s*(.+)", text):
            tag = match.group(1).strip() or None
            body = match.group(2).strip()
            await self.memory.add_note(self.config.id, body, tag)
            count += 1
        return count
