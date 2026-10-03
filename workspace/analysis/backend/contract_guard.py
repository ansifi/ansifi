"""Block writes to the paid contract git clone. Learnings and in-house stacks stay writable."""
from __future__ import annotations

import shlex
from pathlib import Path

from .workspace import AgentError, workspace_root

# Nested git clone under 01_Build — agent may read, never write.
CONTRACT_CLONE_MARK = "/jcatrysse_ror/redmine"
MUTATING_GIT = {
    "commit",
    "push",
    "add",
    "rm",
    "reset",
    "checkout",
    "merge",
    "rebase",
    "cherry-pick",
    "stash",
}


def path_is_contract_clone(path: Path) -> bool:
    normalized = str(path.resolve()).replace("\\", "/").rstrip("/")
    return normalized.endswith(CONTRACT_CLONE_MARK) or f"{CONTRACT_CLONE_MARK}/" in normalized


def workspace_is_contract() -> bool:
    """True when the active root *is* the contract clone (whole tree read-only)."""
    return path_is_contract_clone(workspace_root())


def assert_writable(action: str = "write", relative_path: str | None = None) -> None:
    from .workspace import resolve_workspace_path

    if relative_path:
        target = resolve_workspace_path(relative_path)
        if path_is_contract_clone(target):
            raise AgentError(
                f"Contract git is read-only for the agent ({action}: {relative_path}). "
                "Write a stack folder at 01_Build root, or studies/learns/. Do not write the contract git."
            )
        return
    if workspace_is_contract():
        raise AgentError(
            f"Contract tree is read-only for the agent ({action}). "
            "Copy the suggestion into your editor; do not let the agent write that git."
        )


def command_mutates_git(command: str) -> bool:
    lowered = command.lower().strip()
    if not lowered.startswith("git") and " git " not in f" {lowered} ":
        return False
    try:
        tokens = shlex.split(lowered)
    except ValueError:
        tokens = lowered.split()
    if tokens and tokens[0] != "git":
        try:
            git_at = tokens.index("git")
            tokens = tokens[git_at:]
        except ValueError:
            return False
    return any(token in MUTATING_GIT for token in tokens[1:])
