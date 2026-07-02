"""会话持久化和检查点模块。

把 ContextManager 中的消息和 token 统计保存为 JSON，支持后续恢复。
检查点和会话快照分目录保存，便于 CLI 命令分别管理。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PersistenceManager:
    """管理 sessions 和 checkpoints 两类持久化文件。"""

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = store_dir
        self.sessions_dir = store_dir / "sessions"
        self.checkpoints_dir = store_dir / "checkpoints"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, ctx: Any, session_id: str | None = None) -> str:
        """保存当前会话，返回 session id。"""
        sid = session_id or uuid.uuid4().hex[:12]
        self._write_snapshot(self.sessions_dir / f"{sid}.json", sid, ctx)
        return sid

    def load_session(self, session_id: str, ctx: Any) -> None:
        """把指定 session 的 messages 和 token 统计恢复到当前上下文。"""
        data = self._read_json(self.sessions_dir / f"{session_id}.json")
        self._restore(ctx, data)

    def list_sessions(self) -> list[str]:
        """列出所有已保存 session id。"""
        return sorted(p.stem for p in self.sessions_dir.glob("*.json"))

    def create_checkpoint(self, ctx: Any, session_id: str | None = None) -> str:
        """创建检查点，文件名包含时间戳，方便回滚。"""
        sid = session_id or uuid.uuid4().hex[:12]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        cid = f"{sid}_{stamp}"
        self._write_snapshot(self.checkpoints_dir / f"{cid}.json", cid, ctx)
        return cid

    def restore_checkpoint(self, checkpoint_id: str, ctx: Any) -> None:
        """从检查点恢复上下文。"""
        data = self._read_json(self.checkpoints_dir / f"{checkpoint_id}.json")
        self._restore(ctx, data)

    def _write_snapshot(self, path: Path, snapshot_id: str, ctx: Any) -> None:
        """写入 JSON 快照，并限制文件权限。"""
        data = {
            "id": snapshot_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages": ctx.messages,
            "prompt_tokens": ctx.prompt_tokens,
            "completion_tokens": ctx.completion_tokens,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        path.chmod(0o600)

    def _read_json(self, path: Path) -> dict[str, Any]:
        """读取 JSON 文件，不存在时抛出清晰错误。"""
        if not path.exists():
            raise FileNotFoundError(path)
        return json.loads(path.read_text(encoding="utf-8"))

    def _restore(self, ctx: Any, data: dict[str, Any]) -> None:
        """把快照数据写回 ContextManager。"""
        ctx.messages = data.get("messages", ctx.messages)
        ctx.prompt_tokens = int(data.get("prompt_tokens", 0))
        ctx.completion_tokens = int(data.get("completion_tokens", 0))
