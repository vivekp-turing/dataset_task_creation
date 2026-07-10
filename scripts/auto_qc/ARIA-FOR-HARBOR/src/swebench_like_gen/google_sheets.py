from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

from swebench_like_gen.output_writer import CSV_FIELDS

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEETS_FIELDS = [
    field for field in CSV_FIELDS if field not in {"json_path", "error"}
] + ["summary_markdown"]


@dataclass(frozen=True)
class SheetsConfig:
    file_id: str
    quality_sheet_name: str = ""
    list_sheet_name: str = ""
    credentials_path: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.file_id and (self.quality_sheet_name or self.list_sheet_name))


class GoogleSheetsClient:
    def __init__(self, config: SheetsConfig) -> None:
        self.config = config
        self.service = build(
            "sheets",
            "v4",
            credentials=load_credentials(config.credentials_path),
            cache_discovery=False,
        )

    def upsert_quality_result(self, row: dict[str, Any]) -> None:
        if not self.config.quality_sheet_name:
            return
        sheet = self.config.quality_sheet_name
        values = self.get_values(f"{quote_sheet(sheet)}!A:ZZ")
        headers = [str(value) for value in values[0]] if values else []
        if headers != SHEETS_FIELDS:
            self.update_values(f"{quote_sheet(sheet)}!A1", [SHEETS_FIELDS])
            headers = SHEETS_FIELDS
            values = self.get_values(f"{quote_sheet(sheet)}!A:ZZ")

        task_slug = str(row.get("task_slug") or "")
        target_row = find_row_index(values, headers, "task_slug", task_slug)
        row_values = [cell_value(row.get(field, "")) for field in headers]
        if target_row is None:
            self.append_values(f"{quote_sheet(sheet)}!A:ZZ", [row_values])
        else:
            self.update_values(f"{quote_sheet(sheet)}!A{target_row}", [row_values])

    def update_quality_list_acceptance(self, task_slug: str, verdict: str) -> None:
        if not self.config.list_sheet_name:
            return
        sheet = self.config.list_sheet_name
        values = self.get_values(f"{quote_sheet(sheet)}!B:E")
        accepted = verdict.lower() == "accept"
        for offset, row in enumerate(values, start=1):
            if row and str(row[0]).strip() == task_slug:
                self.update_values(
                    f"{quote_sheet(sheet)}!E{offset}",
                    [["TRUE" if accepted else "FALSE"]],
                )
                return

    def get_values(self, range_name: str) -> list[list[Any]]:
        response = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.config.file_id, range=range_name)
            .execute()
        )
        values = response.get("values", [])
        return values if isinstance(values, list) else []

    def update_values(self, range_name: str, values: list[list[Any]]) -> None:
        self.service.spreadsheets().values().update(
            spreadsheetId=self.config.file_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()

    def append_values(self, range_name: str, values: list[list[Any]]) -> None:
        self.service.spreadsheets().values().append(
            spreadsheetId=self.config.file_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()


def load_credentials(credentials_path: str):
    if not credentials_path:
        msg = "Google Sheets sync is enabled, but GOOGLE_SHEETS_CREDENTIALS_PATH is not hardcoded."
        raise RuntimeError(msg)
    return service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SHEETS_SCOPES
    )


def find_row_index(
    values: list[list[Any]], headers: list[str], key: str, expected: str
) -> int | None:
    if not values or key not in headers or not expected:
        return None
    key_index = headers.index(key)
    for row_number, row in enumerate(values[1:], start=2):
        if key_index < len(row) and str(row[key_index]).strip() == expected:
            return row_number
    return None


def cell_value(value: object) -> object:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if value is None:
        return ""
    return value


def quote_sheet(sheet_name: str) -> str:
    escaped = sheet_name.replace("'", "''")
    return f"'{escaped}'"
