from __future__ import annotations

import importlib
import importlib.util
import sys
from collections import Counter
from typing import Any, Callable

from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from google_client import (
    DriveItem,
    GoogleServices,
    build_google_services,
    has_saved_token,
    list_design_text_files,
    list_folders,
    list_spreadsheets,
    revoke_credentials,
)
from integration_contract import build_processing_selection


class Worker(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, task: Callable[[], Any]):
        super().__init__()
        self._task = task

    def run(self) -> None:
        try:
            self.result.emit(self._task())
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class DesignApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.services: GoogleServices | None = None
        self._threads: list[QThread] = []
        self._workers: list[Worker] = []
        self._active_folder_id: str | None = None

        self.init_ui()
        QTimer.singleShot(0, self.refresh_resources)

    def init_ui(self) -> None:
        self.setWindowTitle("Design Processor")
        self.resize(760, 520)
        self.setMinimumSize(520, 420)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header = QLabel(
            "Выберите две Google-таблицы, их рабочие листы, папку с TXT-дизайнами и файл для обработки."
        )
        header.setWordWrap(True)
        root_layout.addWidget(header)

        sources_group = QGroupBox("Google Drive")
        sources_layout = QFormLayout(sources_group)
        sources_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        sources_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.journal_combo = self._create_combo("Таблица-журнал заказа дизайнов")
        self.journal_sheet_combo = self._create_combo("Выберите лист журнала")
        self.base_combo = self._create_combo("Таблица-база дизайнов")
        self.base_sheet_combo = self._create_combo("Выберите лист базы")
        self.folder_combo = self._create_combo("Папка с текстовыми файлами дизайнов")
        self.file_combo = self._create_combo("TXT-файл дизайна")

        # Привязка событий изменения таблиц
        self.journal_combo.currentIndexChanged.connect(self.on_journal_selected)
        self.base_combo.currentIndexChanged.connect(self.on_base_selected)
        self.folder_combo.currentIndexChanged.connect(self.on_folder_selected)

        sources_layout.addRow("Таблица-журнал:", self.journal_combo)
        sources_layout.addRow("Лист журнала:", self.journal_sheet_combo)
        sources_layout.addRow("Таблица-база:", self.base_combo)
        sources_layout.addRow("Лист базы:", self.base_sheet_combo)
        sources_layout.addRow("Папка с дизайнами:", self.folder_combo)
        sources_layout.addRow("Файл дизайна:", self.file_combo)
        root_layout.addWidget(sources_group)

        buttons_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Обновить списки")
        self.refresh_btn.clicked.connect(self.refresh_resources)
        self.logout_btn = QPushButton("Выйти из аккаунта")
        self.logout_btn.clicked.connect(self.on_logout)
        self.submit_btn = QPushButton("Запустить обработку")
        self.submit_btn.clicked.connect(self.on_submit)
        buttons_layout.addWidget(self.refresh_btn)
        buttons_layout.addWidget(self.logout_btn)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.submit_btn)
        root_layout.addLayout(buttons_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        root_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Готово к авторизации")
        self.status_label.setWordWrap(True)
        root_layout.addWidget(self.status_label)
        root_layout.addStretch(1)

        self._set_controls_enabled(False)

    def _create_combo(self, placeholder: str) -> QComboBox:
        combo = QComboBox()
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.setMinimumContentsLength(20)
        combo.setPlaceholderText(placeholder)
        return combo

    def refresh_resources(self) -> None:
        self._set_busy(True, "Авторизация и загрузка таблиц/папок...")
        self._set_controls_enabled(False)
        self._clear_combo(self.journal_combo)
        self._clear_combo(self.journal_sheet_combo)
        self._clear_combo(self.base_combo)
        self._clear_combo(self.base_sheet_combo)
        self._clear_combo(self.folder_combo)
        self._clear_combo(self.file_combo)
        self._active_folder_id = None

        if not has_saved_token():
            try:
                QApplication.processEvents()
                self.services = build_google_services()
            except Exception as exc:
                self._on_worker_error("Не удалось загрузить ресурсы", str(exc))
                return

        def task() -> tuple[GoogleServices, list[DriveItem], list[DriveItem]]:
            services = self.services or build_google_services()
            return services, list_spreadsheets(services.drive), list_folders(services.drive)

        self._run_worker(task, self._on_resources_loaded, "Не удалось загрузить ресурсы")

    def _on_resources_loaded(
        self, payload: tuple[GoogleServices, list[DriveItem], list[DriveItem]]
    ) -> None:
        self.services, spreadsheets, folders = payload
        self._populate_combo(self.journal_combo, spreadsheets)
        self._populate_combo(self.base_combo, spreadsheets)
        self._populate_combo(self.folder_combo, folders)
        self._clear_combo(self.file_combo)
        self._set_busy(False)

        self.status_label.setText(
            f"Загружено таблиц: {len(spreadsheets)}; папок: {len(folders)}. "
            "Выберите таблицы и папку для продолжения."
        )
        self._set_controls_enabled(True)

    def on_journal_selected(self) -> None:
        journal = self._current_item(self.journal_combo)
        self._clear_combo(self.journal_sheet_combo)
        if not self.services or not journal:
            return

        self._set_busy(True, f"Загрузка листов для «{journal.name}»...")
        self.journal_sheet_combo.setEnabled(False)

        def task() -> list[str]:
            spreadsheet = self.services.sheets.spreadsheets().get(spreadsheetId=journal.id).execute()
            return [sheet['properties']['title'] for sheet in spreadsheet.get('sheets', [])]

        self._run_worker(task, self._on_journal_sheets_loaded, "Не удалось загрузить листы журнала")

    def _on_journal_sheets_loaded(self, sheets: list[str]) -> None:
        self.journal_sheet_combo.blockSignals(True)
        self.journal_sheet_combo.clear()
        for sheet in sheets:
            self.journal_sheet_combo.addItem(sheet, sheet)
        self.journal_sheet_combo.blockSignals(False)
        self.journal_sheet_combo.setEnabled(True)
        self._set_busy(False)

    def on_base_selected(self) -> None:
        base = self._current_item(self.base_combo)
        self._clear_combo(self.base_sheet_combo)
        if not self.services or not base:
            return

        self._set_busy(True, f"Загрузка листов для «{base.name}»...")
        self.base_sheet_combo.setEnabled(False)

        def task() -> list[str]:
            spreadsheet = self.services.sheets.spreadsheets().get(spreadsheetId=base.id).execute()
            return [sheet['properties']['title'] for sheet in spreadsheet.get('sheets', [])]

        self._run_worker(task, self._on_base_sheets_loaded, "Не удалось загрузить листы базы")

    def _on_base_sheets_loaded(self, sheets: list[str]) -> None:
        self.base_sheet_combo.blockSignals(True)
        self.base_sheet_combo.clear()
        for sheet in sheets:
            self.base_sheet_combo.addItem(sheet, sheet)
        self.base_sheet_combo.blockSignals(False)
        self.base_sheet_combo.setEnabled(True)
        self._set_busy(False)

    def on_folder_selected(self) -> None:
        folder = self._current_item(self.folder_combo)
        self._clear_combo(self.file_combo)

        if not self.services or not folder:
            return

        self._active_folder_id = folder.id
        self._set_busy(True, f"Загрузка TXT-файлов из папки «{folder.name}»...")
        self.file_combo.setEnabled(False)

        def task() -> tuple[str, list[DriveItem]]:
            return folder.id, list_design_text_files(self.services.drive, folder.id)

        self._run_worker(task, self._on_files_loaded, "Не удалось загрузить файлы")

    def _on_files_loaded(self, payload: tuple[str, list[DriveItem]]) -> None:
        folder_id, files = payload
        if folder_id != self._active_folder_id:
            return

        self._populate_combo(self.file_combo, files)
        self.file_combo.setEnabled(True)
        self._set_busy(False)

        if files:
            self.status_label.setText(f"Найдено TXT-файлов: {len(files)}")
        else:
            self.status_label.setText("В выбранной папке нет TXT-файлов дизайнов")

    def on_submit(self) -> None:
        journal = self._current_item(self.journal_combo)
        journal_sheet = self.journal_sheet_combo.currentText()
        base = self._current_item(self.base_combo)
        base_sheet = self.base_sheet_combo.currentText()
        folder = self._current_item(self.folder_combo)
        file = self._current_item(self.file_combo)

        if not journal or not journal_sheet or not base or not base_sheet or not folder or not file:
            self._show_warning("Выберите журнал, рабочий лист журнала, базу, рабочий лист базы, папку и файл.")
            return
        if not self.services:
            self._show_warning("Сначала авторизуйтесь и загрузите списки Google Drive.")
            return

        try:
            selection = build_processing_selection(
                file_id=file.id,
                journal_id=journal.id,
                base_id=base.id,
                journal_sheet=journal_sheet,
                base_sheet=base_sheet,
            )
        except ValueError as exc:
            self._show_warning(str(exc))
            return

        self._set_busy(True, "Передача выбранных ID и листов в обработку...")
        self._set_controls_enabled(False)

        def task() -> str:
            return run_processing(
                selection.file_id,
                selection.journal_id,
                selection.base_id,
                selection.journal_sheet,
                selection.base_sheet,
                self.services,
            )

        self._run_worker(task, self._on_processing_finished, "Ошибка обработки")

    def on_logout(self) -> None:
        answer = QMessageBox.question(
            self,
            "Выход из аккаунта",
            "Выйти из Google-аккаунта? При следующем запуске потребуется авторизация.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        revoke_credentials()
        self.services = None
        QApplication.quit()

    def _on_processing_finished(self, result: str) -> None:
        self._set_busy(False)
        self._set_controls_enabled(True)
        self.status_label.setText(result)
        QMessageBox.information(self, "Обработка", result)

    def _populate_combo(self, combo: QComboBox, items: list[DriveItem]) -> None:
        combo.blockSignals(True)
        combo.clear()
        name_counts = Counter(item.name for item in items)
        for item in items:
            label = item.name
            if name_counts[item.name] > 1:
                label = f"{item.name} ({item.id[:8]})"
            combo.addItem(label, item)
            combo.setItemData(
                combo.count() - 1,
                f"{item.name}\nID: {item.id}",
                Qt.ItemDataRole.ToolTipRole,
            )
        combo.blockSignals(False)

    def _clear_combo(self, combo: QComboBox) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.blockSignals(False)

    def _current_item(self, combo: QComboBox) -> DriveItem | None:
        item = combo.currentData()
        return item if isinstance(item, DriveItem) else None

    def _set_busy(self, is_busy: bool, status: str | None = None) -> None:
        self.progress_bar.setVisible(is_busy)
        if status:
            self.status_label.setText(status)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.journal_combo,
            self.journal_sheet_combo,
            self.base_combo,
            self.base_sheet_combo,
            self.folder_combo,
            self.file_combo,
            self.refresh_btn,
            self.logout_btn,
            self.submit_btn,
        ):
            widget.setEnabled(enabled)

    def _show_warning(self, message: str) -> None:
        self.status_label.setText(message)
        QMessageBox.warning(self, "Проверьте выбор", message)

    def _run_worker(
        self,
        task: Callable[[], Any],
        on_success: Callable[[Any], None],
        error_prefix: str,
    ) -> None:
        thread = QThread(self)
        worker = Worker(task)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.result.connect(on_success)
        worker.error.connect(lambda message: self._on_worker_error(error_prefix, message))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._cleanup_worker(thread, worker))

        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()

    def _on_worker_error(self, prefix: str, message: str) -> None:
        self._set_busy(False)
        self._set_controls_enabled(self.services is not None)
        self.refresh_btn.setEnabled(True)
        self.file_combo.setEnabled(self.folder_combo.isEnabled())
        self.journal_sheet_combo.setEnabled(self.journal_combo.isEnabled())
        self.base_sheet_combo.setEnabled(self.base_combo.isEnabled())
        full_message = f"{prefix}: {message}"
        self.status_label.setText(full_message)
        QMessageBox.critical(self, "Ошибка", full_message)

    def _cleanup_worker(self, thread: QThread, worker: Worker) -> None:
        if thread in self._threads:
            self._threads.remove(thread)
        if worker in self._workers:
            self._workers.remove(worker)


def run_processing(
    file_id: str,
    journal_id: str,
    base_id: str,
    journal_sheet: str,
    base_sheet: str,
    services: GoogleServices | None = None,
) -> str:
    if importlib.util.find_spec("core_processor") is None:
        return (
            "Алгоритм второго разработчика пока не подключен.\n"
            "Будут переданы ID и листы:\n"
            f"file_id={file_id}\n"
            f"journal_id={journal_id} (Лист: {journal_sheet})\n"
            f"base_id={base_id} (Лист: {base_sheet})"
        )

    processor = importlib.import_module("core_processor")
    result = processor.run_full_processing(file_id, journal_id, base_id, journal_sheet, base_sheet, services)
    return str(result)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DesignApp()
    window.show()
    sys.exit(app.exec())