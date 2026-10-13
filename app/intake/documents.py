"""The original claim file (D-DOC-1): what a claim was filed from, kept so every role can see it
as it was sent. Only JSON, PDF, PNG and JPEG files are kept, recognized by their first bytes (the
content type the browser sent is not trusted); a TIFF scan is read like any other but not kept.
The file name the client gives is reduced to a safe base name (no folders, no control or special
characters, at most 128 characters, ending in the type's extension)."""

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import unquote

EXTENSIONS = {
    "application/json": (".json",),
    "application/pdf": (".pdf",),
    "image/png": (".png",),
    "image/jpeg": (".jpg", ".jpeg"),
}
MAX_NAME = 128
UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")


@dataclass(frozen=True)
class OriginalFile:
    file_name: str
    content_type: str
    content: bytes

    @property
    def size_bytes(self) -> int:
        return len(self.content)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def content_type(data: bytes) -> str | None:
    """The kept type of a claim file from its first bytes, or None for any other file."""
    if data.lstrip(b"\xef\xbb\xbf \t\r\n")[:1] == b"{":
        return "application/json"
    if data[:5] == b"%PDF-":
        return "application/pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return None


def safe_name(name: str | None, claim_id: str, kind: str) -> str:
    """A safe base name with the type's extension; the claim ID when nothing usable is left."""
    text = unquote(name or "")
    text = re.split(r"[\\/]", text)[-1]
    text = UNSAFE.sub("_", text).strip(" ._")
    extensions = EXTENSIONS[kind]
    if not text:
        text = UNSAFE.sub("_", claim_id).strip(" ._") or "claim"
    if not text.lower().endswith(extensions):
        text = f"{text}{extensions[0]}"
    if len(text) > MAX_NAME:
        stem, dot, extension = text.rpartition(".")
        text = f"{stem[: MAX_NAME - len(extension) - 1]}{dot}{extension}"
    return text


def original_file(data: bytes, name: str | None, claim_id: str) -> OriginalFile | None:
    """The file to keep for a claim filed from `data`, or None when its type is not kept."""
    kind = content_type(data)
    if kind is None or not data:
        return None
    return OriginalFile(safe_name(name, claim_id, kind), kind, data)
