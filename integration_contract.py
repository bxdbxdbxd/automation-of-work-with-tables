from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessingSelection:
    file_id: str
    journal_id: str
    base_id: str


def build_processing_selection(
    *, file_id: str, journal_id: str, base_id: str
) -> ProcessingSelection:
    if not file_id or not journal_id or not base_id:
        raise ValueError("Не удалось получить file_id, journal_id или base_id.")
    if journal_id == base_id:
        raise ValueError("Таблица-журнал и таблица-база должны быть разными.")
    return ProcessingSelection(
        file_id=file_id,
        journal_id=journal_id,
        base_id=base_id,
    )
