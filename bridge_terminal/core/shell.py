from __future__ import annotations

import asyncio
import os
import re
import shlex
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

CODE_BLOCK_RE = re.compile(r"```(?:sh|bash|shell)\s*\n(.*?)```", re.DOTALL)

DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/(?:\s|$)",
    r"\bmkfs\b",
    r":\(\)\s*\{",  # fork bomb
    r"\bdd\s+if=.*of=/dev/",
    r">\s*/dev/sd[a-z]",
    r"\bchmod\s+-R\s+777\s+/",
    r"\bsudo\s+rm",
]


@dataclass
class ShellResult:
    command: str
    stdout: str
    stderr: str
    returncode: int


def extract_shell_blocks(text: str) -> list[str]:
    """Extract shell code blocks (```sh / ```bash) from a message."""
    return [m.group(1).strip() for m in CODE_BLOCK_RE.finditer(text)]


def is_dangerous(command: str) -> tuple[bool, str]:
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            return True, pattern
    return False, ""


class ShellRunner:
    """Runs commands inside a sandboxed workspace directory."""

    def __init__(self, workspace: Path, timeout: float = 60.0) -> None:
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

    async def run(self, command: str) -> ShellResult:
        danger, pattern = is_dangerous(command)
        if danger:
            return ShellResult(
                command=command,
                stdout="",
                stderr=f"[blocked] dangerous pattern matched: {pattern}",
                returncode=-1,
            )

        env = os.environ.copy()
        env["HOME"] = str(self.workspace)
        env["PWD"] = str(self.workspace)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
                env=env,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )
            return ShellResult(
                command=command,
                stdout=stdout_b.decode("utf-8", errors="replace"),
                stderr=stderr_b.decode("utf-8", errors="replace"),
                returncode=proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
            return ShellResult(
                command=command,
                stdout="",
                stderr=f"[timeout] command exceeded {self.timeout}s",
                returncode=-2,
            )
        except Exception as exc:  # noqa: BLE001
            return ShellResult(
                command=command,
                stdout="",
                stderr=f"[error] {type(exc).__name__}: {exc}",
                returncode=-3,
            )

    async def stream(self, command: str) -> AsyncIterator[str]:
        """Yield stdout/stderr line by line as the process runs."""
        danger, pattern = is_dangerous(command)
        if danger:
            yield f"[blocked] dangerous pattern matched: {pattern}\n"
            return

        env = os.environ.copy()
        env["HOME"] = str(self.workspace)
        env["PWD"] = str(self.workspace)

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(self.workspace),
            env=env,
        )

        assert proc.stdout is not None
        try:
            async for raw in proc.stdout:
                yield raw.decode("utf-8", errors="replace")
        finally:
            await proc.wait()
            yield f"\n[exit {proc.returncode}]\n"


def safe_split(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return [command]
