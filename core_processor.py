from __future__ import annotations

from typing import Any

from algoritm.run_scripts import content_second_tab_by_ids
from google_client import GoogleServices, build_google_services


def run_full_processing(
    file_id: str,
    journal_id: str,
    base_id: str,
    services: GoogleServices | None = None,
) -> str:
    services = services or build_google_services()
    result = content_second_tab_by_ids(
        services.sheets,
        services.drive,
        file_id,
        journal_id,
        base_id,
    )
    updated_range = _extract_updated_range(result)
    if updated_range:
        return f"Строка добавлена в таблицу-базу: {updated_range}"
    return "Обработка завершена, строка добавлена в таблицу-базу."


def _extract_updated_range(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    updates = result.get("updates", {})
    if not isinstance(updates, dict):
        return None
    updated_range = updates.get("updatedRange")
    return str(updated_range) if updated_range else None
