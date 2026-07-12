"""Sanitize text before database insert."""


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("\x00", "").replace("\u0000", "").strip()
