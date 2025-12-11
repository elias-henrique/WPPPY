from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class MessageMedia:
    mimetype: str
    data: str
    filename: Optional[str] = None
    filesize: Optional[int] = None

    @classmethod
    def from_file(cls, file_path: str) -> "MessageMedia":
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode()
        return cls(mimetype=mimetype, data=data, filename=path.name, filesize=path.stat().st_size)

    def to_json(self) -> Dict[str, Any]:
        return {
            "mimetype": self.mimetype,
            "data": self.data,
            "filename": self.filename,
            "filesize": self.filesize,
        }


@dataclass
class Contact:
    id: str
    name: Optional[str]
    pushname: Optional[str]
    is_business: bool
    is_me: bool
    raw: Dict[str, Any]

    @classmethod
    def from_js(cls, payload: Dict[str, Any]) -> "Contact":
        wid = payload.get("id", {}).get("_serialized") or payload.get("id")
        return cls(
            id=wid,
            name=payload.get("name"),
            pushname=payload.get("pushname"),
            is_business=bool(payload.get("isBusiness", False)),
            is_me=bool(payload.get("isMe", False)),
            raw=payload,
        )


@dataclass
class Chat:
    id: str
    name: str
    unread_count: int
    is_group: bool
    raw: Dict[str, Any]

    @classmethod
    def from_js(cls, payload: Dict[str, Any]) -> "Chat":
        wid = payload.get("id", {}).get("_serialized") or payload.get("id")
        return cls(
            id=wid,
            name=payload.get("name") or payload.get("formattedTitle") or "",
            unread_count=int(payload.get("unreadCount") or 0),
            is_group=payload.get("isGroup", False),
            raw=payload,
        )


@dataclass
class Message:
    id: str
    body: str
    from_me: bool
    chat_id: Optional[str]
    timestamp: Optional[int]
    type: str
    raw: Dict[str, Any]

    @classmethod
    def from_js(cls, payload: Dict[str, Any]) -> "Message":
        msg_id = payload.get("id", {}).get("_serialized") or payload.get("id")
        chat_id = payload.get("id", {}).get("remote") or payload.get("chatId")
        return cls(
            id=msg_id,
            body=payload.get("body") or "",
            from_me=bool(payload.get("id", {}).get("fromMe", payload.get("fromMe", False))),
            chat_id=chat_id,
            timestamp=payload.get("t") or payload.get("timestamp"),
            type=payload.get("type") or payload.get("messageType", "unknown"),
            raw=payload,
        )

