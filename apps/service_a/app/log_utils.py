from __future__ import annotations


def token_tail(token: str, length: int = 6) -> str:
    if not token:
        return "-"
    return token[-length:]


def one_line(value: object, limit: int = 300) -> str:
    text = " ".join(str(value).split())
    if len(text) > limit:
        return f"{text[:limit]}..."
    return text
