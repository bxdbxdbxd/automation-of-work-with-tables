from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessingSelection:
    file_id: str
    journal_id: str
    base_id: str
    journal_sheet: str
    base_sheet: str


def build_processing_selection(
    *, file_id: str, journal_id: str, base_id: str, journal_sheet: str, base_sheet: str
) -> ProcessingSelection:
    if not file_id or not journal_id or not base_id or not journal_sheet or not base_sheet:
        raise ValueError("Не удалось получить все ID таблиц или названия листов.")
    if journal_id == base_id and journal_sheet == base_sheet:
        raise ValueError("Таблица-журнал и таблица-база (и их листы) не должны полностью совпадать.")
    return ProcessingSelection(
        file_id=file_id,
        journal_id=journal_id,
        base_id=base_id,
        journal_sheet=journal_sheet,
        base_sheet=base_sheet,
    )