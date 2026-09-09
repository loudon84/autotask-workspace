"""IMAP modified UTF-7 for mailbox names (Chinese folders)."""

from __future__ import annotations

import base64
import re


def encode_modified_utf7(text: str) -> str:
    result: list[str] = []
    buf: list[str] = []

    def flush_buf() -> None:
        if not buf:
            return
        raw = "".join(buf).encode("utf-16-be")
        b64 = base64.b64encode(raw).decode("ascii").replace("+", ",").rstrip("=")
        result.append("&" + b64 + "-")
        buf.clear()

    for ch in text:
        if 0x20 <= ord(ch) <= 0x7E:
            flush_buf()
            if ch == "&":
                result.append("&-")
            else:
                result.append(ch)
        else:
            buf.append(ch)
    flush_buf()
    return "".join(result)


def decode_modified_utf7(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        b64 = match.group(1).replace(",", "+")
        try:
            pad = "=" * (-len(b64) % 4)
            return base64.b64decode(b64 + pad).decode("utf-16-be", errors="replace")
        except Exception:
            return match.group(0)

    return re.sub(r"&([^-]*)-", repl, text).replace("&-", "&")
