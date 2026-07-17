from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


APP_NAME = "DesignProcessor"


def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def _user_data_dir() -> Path:
    if os.name == "nt":
        base_dir = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    data_dir = base_dir / APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


CREDENTIALS_PATH = _bundle_dir() / "credentials.json"
TOKEN_PATH = _user_data_dir() / "token.json"
LEGACY_TOKEN_PATH = _user_data_dir() / "token.pickle"

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]

SPREADSHEET_MIME = "application/vnd.google-apps.spreadsheet"
FOLDER_MIME = "application/vnd.google-apps.folder"
TEXT_FILE_MIMES = {"text/plain"}


@dataclass(frozen=True)
class DriveItem:
    id: str
    name: str
    mime_type: str = ""


@dataclass(frozen=True)
class GoogleServices:
    creds: Credentials
    drive: Any
    sheets: Any


def get_credentials() -> Credentials:
    creds = _load_token()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            TOKEN_PATH.unlink(missing_ok=True)
            creds = None

    if not creds or not creds.valid:
        if not CREDENTIALS_PATH.exists():
            raise FileNotFoundError(
                f"OAuth config file was not found: {CREDENTIALS_PATH}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)

    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_google_services() -> GoogleServices:
    creds = get_credentials()
    return GoogleServices(
        creds=creds,
        drive=build("drive", "v3", credentials=creds),
        sheets=build("sheets", "v4", credentials=creds),
    )


def has_saved_token() -> bool:
    return TOKEN_PATH.exists()


def revoke_credentials() -> None:
    TOKEN_PATH.unlink(missing_ok=True)
    LEGACY_TOKEN_PATH.unlink(missing_ok=True)


def list_spreadsheets(drive_service: Any) -> list[DriveItem]:
    return list_drive_items(
        drive_service,
        query=f"mimeType='{SPREADSHEET_MIME}' and trashed=false",
        fields="nextPageToken, files(id, name, mimeType)",
    )


def list_folders(drive_service: Any) -> list[DriveItem]:
    return list_drive_items(
        drive_service,
        query=f"mimeType='{FOLDER_MIME}' and trashed=false",
        fields="nextPageToken, files(id, name, mimeType)",
    )


def list_design_text_files(drive_service: Any, folder_id: str) -> list[DriveItem]:
    items = list_drive_items(
        drive_service,
        query=f"'{folder_id}' in parents and trashed=false",
        fields="nextPageToken, files(id, name, mimeType)",
    )
    return [item for item in items if is_text_design_file(item)]


def list_drive_items(
    drive_service: Any,
    *,
    query: str,
    fields: str,
    page_size: int = 200,
) -> list[DriveItem]:
    page_token: str | None = None
    items: list[DriveItem] = []

    while True:
        response = (
            drive_service.files()
            .list(
                q=query,
                fields=fields,
                pageSize=page_size,
                pageToken=page_token,
                orderBy="name_natural",
            )
            .execute()
        )
        items.extend(_drive_items_from_response(response.get("files", [])))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return sorted(items, key=lambda item: item.name.casefold())


def is_text_design_file(item: DriveItem) -> bool:
    if item.mime_type in TEXT_FILE_MIMES:
        return True
    return item.name.lower().endswith(".txt")


def _drive_items_from_response(files: Iterable[dict[str, Any]]) -> list[DriveItem]:
    return [
        DriveItem(
            id=str(file["id"]),
            name=str(file["name"]),
            mime_type=str(file.get("mimeType", "")),
        )
        for file in files
        if file.get("id") and file.get("name")
    ]


def _load_token() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None

    try:
        return Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    except ValueError:
        TOKEN_PATH.unlink(missing_ok=True)
        return None
