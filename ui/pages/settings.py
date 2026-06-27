"""Settings page: edit config.json values (DB path, OCR path, downloads, polling, logging)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config.settings import save_settings


class SettingsPage(QWidget):
    def __init__(self, context) -> None:
        super().__init__()
        self._context = context

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Changes are saved to config.json. Path changes require an app restart.")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form_box = QWidget()
        form_box.setObjectName("card")
        form = QFormLayout(form_box)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)

        s = context.settings
        self.accounts_file_input = QLineEdit(s.accounts_file)
        self.download_folder_input = QLineEdit(s.download_folder)
        self.database_path_input = QLineEdit(s.database_path)
        self.tesseract_path_input = QLineEdit(s.tesseract_path)

        self.polling_interval_input = QSpinBox()
        self.polling_interval_input.setRange(1, 1440)
        self.polling_interval_input.setSuffix(" min")
        self.polling_interval_input.setValue(s.polling_interval_minutes)

        self.log_level_input = QComboBox()
        self.log_level_input.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_input.setCurrentText(s.log_level)

        form.addRow("Accounts file", self.accounts_file_input)
        form.addRow("Download folder", self.download_folder_input)
        form.addRow("Database path", self.database_path_input)
        form.addRow("Tesseract path", self.tesseract_path_input)
        form.addRow("Polling interval", self.polling_interval_input)
        form.addRow("Log level", self.log_level_input)

        layout.addWidget(form_box)
        layout.addWidget(self._build_publish_section(s))

        self.status_label = QLabel("")
        self.status_label.setObjectName("pageSubtitle")
        layout.addWidget(self.status_label)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)
        layout.addStretch()

    def _build_publish_section(self, s) -> QWidget:
        box = QWidget()
        box.setObjectName("card")
        form = QFormLayout(box)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)

        section_label = QLabel("Auto-Publish (Destination Account)")
        section_label.setObjectName("cardTitle")
        form.addRow(section_label)

        self.ig_dest_access_token_input = QLineEdit(s.ig_dest_access_token)
        self.ig_dest_access_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ig_dest_business_account_id_input = QLineEdit(s.ig_dest_business_account_id)
        self.media_public_base_url_input = QLineEdit(s.media_public_base_url)

        self.max_publish_per_cycle_input = QSpinBox()
        self.max_publish_per_cycle_input.setRange(1, 50)
        self.max_publish_per_cycle_input.setValue(s.max_publish_per_cycle)

        self.max_publish_per_day_input = QSpinBox()
        self.max_publish_per_day_input.setRange(1, 100)
        self.max_publish_per_day_input.setValue(s.max_publish_per_day)

        self.publish_retry_max_attempts_input = QSpinBox()
        self.publish_retry_max_attempts_input.setRange(1, 20)
        self.publish_retry_max_attempts_input.setValue(s.publish_retry_max_attempts)

        self.publish_retry_backoff_minutes_input = QSpinBox()
        self.publish_retry_backoff_minutes_input.setRange(1, 1440)
        self.publish_retry_backoff_minutes_input.setSuffix(" min")
        self.publish_retry_backoff_minutes_input.setValue(s.publish_retry_backoff_minutes)

        form.addRow("Graph API access token", self.ig_dest_access_token_input)
        form.addRow("IG business account ID", self.ig_dest_business_account_id_input)
        form.addRow("Media public base URL", self.media_public_base_url_input)
        form.addRow("Max publishes / cycle", self.max_publish_per_cycle_input)
        form.addRow("Max publishes / day", self.max_publish_per_day_input)
        form.addRow("Retry attempts before giving up", self.publish_retry_max_attempts_input)
        form.addRow("Retry backoff (base)", self.publish_retry_backoff_minutes_input)

        return box

    def _save(self) -> None:
        s = self._context.settings
        s.accounts_file = self.accounts_file_input.text().strip()
        s.download_folder = self.download_folder_input.text().strip()
        s.database_path = self.database_path_input.text().strip()
        s.tesseract_path = self.tesseract_path_input.text().strip()
        s.polling_interval_minutes = self.polling_interval_input.value()
        s.log_level = self.log_level_input.currentText()
        s.ig_dest_access_token = self.ig_dest_access_token_input.text().strip()
        s.ig_dest_business_account_id = self.ig_dest_business_account_id_input.text().strip()
        s.media_public_base_url = self.media_public_base_url_input.text().strip()
        s.max_publish_per_cycle = self.max_publish_per_cycle_input.value()
        s.max_publish_per_day = self.max_publish_per_day_input.value()
        s.publish_retry_max_attempts = self.publish_retry_max_attempts_input.value()
        s.publish_retry_backoff_minutes = self.publish_retry_backoff_minutes_input.value()
        save_settings(s)
        self.status_label.setText("Saved. Restart the app for path changes to take effect.")
