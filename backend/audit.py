"""Append-only audit trail of every agent-loop step: output/audit_trail.json.

The file is one JSON array. A new record replaces the array's closing "]" with
",<record>]", so earlier records (and earlier runs) are never rewritten and the file
stays valid JSON. A file lock keeps concurrent writers from clashing. If the file does
not end in "]", the writer refuses to touch it rather than risk losing history.
"""

import fcntl
import json
import os
import re
from pathlib import Path
from typing import Any

from backend.models import AuditRecord

HW_DIR = Path(__file__).resolve().parent.parent
AUDIT_PATH = Path(os.environ.get("CC_AUDIT_PATH") or HW_DIR / "output" / "audit_trail.json")
MAX_TEXT_CHARS = 2_000  # longer strings are cut, with a note saying how much was dropped


def mask(value: Any) -> Any:
    """Remove emails, phone numbers, and card numbers from every string in a record."""
    if isinstance(value, str):
        value = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email removed]", value)
        value = re.sub(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{1,7}\b", "[card number removed]", value)
        value = re.sub(r"(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b", "[phone removed]", value)
        if len(value) > MAX_TEXT_CHARS:
            value = value[:MAX_TEXT_CHARS] + f"... [{len(value) - MAX_TEXT_CHARS} more characters cut]"
        return value
    if isinstance(value, dict):
        return {k: mask(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask(v) for v in value]
    return value


class AuditTrail:
    def __init__(self, path: Path = AUDIT_PATH):
        self.path = Path(path)

    def append(self, record: AuditRecord) -> None:
        data = mask(record.model_dump(mode="json"))
        line = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a+b") as f:  # append mode: every write lands at the current end of file
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size == 0:
                    f.write(b"[\n" + line + b"\n]\n")
                else:
                    f.seek(max(0, size - 256))
                    tail = f.read()
                    close = tail.rstrip().rfind(b"]")
                    if close < 0 or not tail.rstrip().endswith(b"]"):
                        raise RuntimeError(f"{self.path} does not end with ']'; not appending so no history is lost.")
                    close_at = size - len(tail) + close
                    start = max(0, close_at - 256)
                    f.seek(start)
                    before = f.read(close_at - start)
                    content_end = start + len(before.rstrip())  # last non-blank byte before "]"
                    f.truncate(content_end)
                    f.write((b"\n" if before.rstrip().endswith(b"[") else b",\n") + line + b"\n]\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
