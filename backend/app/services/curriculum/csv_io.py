"""CSV helpers for curriculum data pipeline."""

from __future__ import annotations

import csv
from dataclasses import asdict, fields
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


def write_csv(path: Path, rows: list[T]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames = [field.name for field in fields(rows[0])]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def read_csv_as_dicts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_csv(path: Path, row_type: type[T]) -> list[T]:
    dicts = read_csv_as_dicts(path)
    rows: list[T] = []
    for row in dicts:
        if "confidence" in row and row["confidence"]:
            row["confidence"] = float(row["confidence"])
        rows.append(row_type(**row))
    return rows
