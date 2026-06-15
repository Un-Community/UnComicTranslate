from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Signal, QSettings, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QDesktopServices
import json
import logging
from dataclasses import asdict, is_dataclass
import os
import shutil

from .settings_ui import SettingsPageUI
from app.account.auth.auth_client import AuthClient, USER_INFO_GROUP, \
    EMAIL_KEY, TIER_KEY, CREDITS_KEY, MONTHLY_CREDITS_KEY
from app.account.config import API_BASE_URL, FRONTEND_BASE_URL

logger = logging.getLogger(__name__)

# Dictionary to map old model names to the newest versions in settings
OCR_MIGRATIONS = {
    "GPT-4o":       "GPT-4.1-mini",
    "Gemini-2.5-Flash": "Gemini-2.0-Flash",
}

TRANSLATOR_MIGRATIONS = {
    "GPT-4o":              "GPT-4.1",
    "GPT-4o mini":         "GPT-4.1-mini",
    "Gemini Free (Web)":   "Gemini-2.5-Flash",
    "Gemini-2.0-Flash":    "Gemini-2.5-Flash",
    "Gemini-2.0-Pro":      "Gemini-2.5-Flash",
    "Gemini-2.5-Pro":      "Gemini-2.5-Pro",
    "Claude-3-Opus":       "Claude-4.5-Sonnet",
    "Claude-4-Sonnet":     "Claude-4.5-Sonnet",
    "Claude-3-Haiku":    "Claude-4.5-Haiku",
    "Claude-3.5-Haiku":   "Claude-4.5-Haiku",
}

INPAINTER_MIGRATIONS = {
    "MI-GAN": "AOT",
}

class SettingsPage(QtWidgets.QWidget):
    theme_changed = Signal(str)
    font_imported = Signal(str)

    def __init__(self, parent=None):
        super(SettingsPage, self).__init__(parent)

        self.ui = SettingsPageUI(self)
        self._setup_connections()
        self._loading_settings = False
        
        # Initialize AuthClient
        self.auth_client = AuthClient(API_BASE_URL, FRONTEND_BASE_URL)
        self.auth_client.auth_success.connect(self.handle_auth_success)
        self.auth_client.auth_error.connect(self.handle_auth_error)
        self.auth_client.auth_cancelled.connect(self.handle_auth_cancelled)
        self.auth_client.request_login_view.connect(self.show_login_view)
        self.auth_client.logout_success.connect(self.handle_logout_success)
        self.auth_client.session_check_finished.connect(self.handle_session_check_finished)

        self.user_email = None
        self.user_tier = None
        self.user_credits = None
        self.user_monthly_credits = None

        # Use the Settings UI directly; inner content is scrollable on the
        # right side (see settings_ui.py). This keeps the left navbar fixed.
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.ui)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def _setup_connections(self):
        # Connect signals to slots
        self.ui.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        self.ui.lang_combo.currentTextChanged.connect(self.on_language_changed)
        self.ui.font_browser.sig_files_changed.connect(self.import_font)
        
        # Account connections (Now integrated into Credentials)
        self.ui.credentials_page.sig_sign_in_clicked.connect(self.start_sign_in)
        self.ui.credentials_page.sig_sign_out_clicked.connect(self.sign_out)
        self.ui.credentials_page.sig_buy_credits_clicked.connect(self.open_pricing_page)

    def on_theme_changed(self, theme: str):
        self.theme_changed.emit(theme)

    def get_language(self):
        return self.ui.lang_combo.currentText()
    
    def get_theme(self):
        return self.ui.theme_combo.currentText()

    def get_tool_selection(self, tool_type):
        tool_combos = {
            'translator': self.ui.translator_combo,
            'ocr': self.ui.ocr_combo,
            'inpainter': self.ui.inpainter_combo,
            'detector': self.ui.detector_combo
        }
        return tool_combos[tool_type].currentText()

    def is_gpu_enabled(self):
        return self.ui.use_gpu_checkbox.isChecked()

    def get_llm_settings(self):
        return {
            'extra_context': self.ui.extra_context.toPlainText(),
            'image_input_enabled': self.ui.image_checkbox.isChecked(),
            'temperature': float(self.ui.temp_edit.text()),
            'top_p': float(self.ui.top_p_edit.text()),
            'max_tokens': int(self.ui.max_tokens_edit.text()),
        }

    def get_export_settings(self):
        settings = {
            'export_raw_text': self.ui.raw_text_checkbox.isChecked(),
            'export_translated_text': self.ui.translated_text_checkbox.isChecked(),
            'export_inpainted_image': self.ui.inpainted_image_checkbox.isChecked(),
            'export_web_json': self.ui.web_json_checkbox.isChecked(),
            'save_as': {}
        }
        for file_type in self.ui.from_file_types:
            settings['save_as'][f'.{file_type}'] = self.ui.export_widgets[f'.{file_type}_save_as'].currentText()
        return settings

    def get_credentials(self, service: str = ""):
        save_keys = self.ui.save_keys_checkbox.isChecked()

        def _get_val(widget_key):
            w = self.ui.credential_widgets.get(widget_key)
            if isinstance(w, QtWidgets.QLineEdit):
                return w.text()
            elif isinstance(w, QtWidgets.QListWidget):
                item = w.currentItem()
                return item.text() if item else None
            elif isinstance(w, QtWidgets.QCheckBox):
                return w.isChecked()
            return None

        if service:
            internal_service = self.ui.value_mappings.get(service, service)
            creds = {'save_key': save_keys}
            if internal_service == "Microsoft Azure":
                creds.update({
                    'api_key_ocr': _get_val("Microsoft Azure_api_key_ocr"),
                    'api_key_translator': _get_val("Microsoft Azure_api_key_translator"),
                    'region_translator': _get_val("Microsoft Azure_region"),
                    'endpoint': _get_val("Microsoft Azure_endpoint"),
                })
            elif internal_service == "Custom":
                for field in ("api_key", "api_url", "model"):
                    creds[field] = _get_val(f"Custom_{field}")
            elif internal_service == "Yandex":
                creds['api_key'] = _get_val("Yandex_api_key")
                creds['folder_id'] = _get_val("Yandex_folder_id")
            elif internal_service == "Ollama":
                creds['api_url'] = _get_val("Ollama_api_url")
                creds['selected_model'] = _get_val("Ollama_model_list")
            elif internal_service == "DeeLX":
                creds.update({
                    'self_hosted': _get_val("DeeLX_self_hosted"),
                    'url': _get_val("DeeLX_url"),
                })
            elif internal_service == "9Router":
                creds['api_url'] = _get_val("9Router_api_url")
                creds['api_key'] = _get_val("9Router_api_key")
                model = _get_val("9Router_model_list")
                if model:
                    creds['selected_model'] = model
            elif internal_service == "Googletrans":
                pass
            else:
                # Standard LLM platforms
                creds['api_key'] = _get_val(f"{internal_service}_api_key")
                # Also include selected model if it exists in the UI
                model = _get_val(f"{internal_service}_model_list")
                if model:
                    creds['selected_model'] = model

            return creds

        # no `service` passed → recurse over all known services
        return {s: self.get_credentials(s) for s in self.ui.credential_services}
        
    def get_hd_strategy_settings(self):
        strategy = self.ui.inpaint_strategy_combo.currentText()
        settings = {
            'strategy': strategy
        }

        if strategy == self.ui.tr("Resize"):
            settings['resize_limit'] = self.ui.resize_spinbox.value()
        elif strategy == self.ui.tr("Crop"):
            settings['crop_margin'] = self.ui.crop_margin_spinbox.value()
            settings['crop_trigger_size'] = self.ui.crop_trigger_spinbox.value()

        return settings

    def get_all_settings(self):
        return {
            'language': self.get_language(),
            'theme': self.get_theme(),
            'tools': {
                'translator': self.get_tool_selection('translator'),
                'ocr': self.get_tool_selection('ocr'),
                'detector': self.get_tool_selection('detector'),
                'inpainter': self.get_tool_selection('inpainter'),
                'use_gpu': self.is_gpu_enabled(),
                'hd_strategy': self.get_hd_strategy_settings()
            },
            'llm': self.get_llm_settings(),
            'export': self.get_export_settings(),
            'credentials': self.get_credentials(),
            'save_keys': self.ui.save_keys_checkbox.isChecked(),
            'selected_fonts': self.ui.text_rendering_page.get_selected_fonts(),
        }

    def import_font(self, file_paths: list[str]):

        file_paths = [f for f in file_paths 
                      if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]

        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
        font_folder_path = os.path.join(project_root, 'resources', 'fonts')

        if not os.path.exists(font_folder_path):
            os.makedirs(font_folder_path)

        if file_paths:
            for file in file_paths:
                shutil.copy(file, font_folder_path)
                
            font_files = [os.path.join(font_folder_path, f) for f in os.listdir(font_folder_path) 
                      if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]
            
            font_families = []
            for font in font_files:
                font_family = self.add_font_family(font)
                font_families.append(font_family)
                # Add to font list in UI
                self.ui.text_rendering_page.add_font_to_list(font, font_family, checked=True)
            
            if font_families:
                self.font_imported.emit(font_families[0])
            
            # Save selected fonts to settings
            self.save_selected_fonts()

    def select_color(self, outline = False):
        default_color = QtGui.QColor('#000000') if not outline else QtGui.QColor('#FFFFFF')
        color_dialog = QtWidgets.QColorDialog()
        color_dialog.setCurrentColor(default_color)
        
        if color_dialog.exec() == QtWidgets.QDialog.Accepted:
            color = color_dialog.selectedColor()
            if color.isValid():
                button = self.ui.color_button if not outline else self.ui.outline_color_button
                button.setStyleSheet(
                    f"background-color: {color.name()}; border: none; border-radius: 5px;"
                )
                button.setProperty('selected_color', color.name())

    # With the mappings, settings are saved with English values and loaded in the selected language
    def save_settings(self):
        settings = QSettings("UnComicLabs", "UnComicTranslate")
        all_settings = self.get_all_settings()

        def process_group(group_key, group_value, settings_obj: QSettings):
            """Helper function to process a group and its nested values."""
            if is_dataclass(group_value):
                group_value = asdict(group_value)
            if isinstance(group_value, dict):
                settings_obj.beginGroup(group_key)
                for sub_key, sub_value in group_value.items():
                    process_group(sub_key, sub_value, settings_obj)
                settings_obj.endGroup()
            elif isinstance(group_value, list):
                # Handle lists directly without mapping
                settings_obj.setValue(group_key, group_value)
            else:
                # Convert value to English using mappings if available
                mapped_value = self.ui.value_mappings.get(group_value, group_value)
                settings_obj.setValue(group_key, mapped_value)

        for key, value in all_settings.items():
            process_group(key, value, settings)

        # Save selected fonts
        self.save_selected_fonts()

        # Save credentials separately if save_keys is checked
        credentials = self.get_credentials()
        save_keys = self.ui.save_keys_checkbox.isChecked()
        settings.beginGroup('credentials')
        settings.setValue('save_keys', save_keys)
        if save_keys:
            for service, cred in credentials.items():
                translated_service = self.ui.value_mappings.get(service, service)
                if translated_service == "Microsoft Azure":
                    settings.setValue(f"{translated_service}_api_key_ocr", cred['api_key_ocr'])
                    settings.setValue(f"{translated_service}_api_key_translator", cred['api_key_translator'])
                    settings.setValue(f"{translated_service}_region_translator", cred['region_translator'])
                    settings.setValue(f"{translated_service}_endpoint", cred['endpoint'])
                elif translated_service == "Custom":
                    settings.setValue(f"{translated_service}_api_key", cred['api_key'])
                    settings.setValue(f"{translated_service}_api_url", cred['api_url'])
                    settings.setValue(f"{translated_service}_model", cred['model'])
                elif translated_service == "Yandex":
                    settings.setValue(f"{translated_service}_api_key", cred['api_key'])
                    settings.setValue(f"{translated_service}_folder_id", cred['folder_id'])
                elif translated_service == "Ollama":
                    settings.setValue(f"{translated_service}_api_url", cred['api_url'])
                    if 'selected_model' in cred and cred['selected_model']:
                        settings.setValue(f"{translated_service}_selected_model", cred['selected_model'])
                elif translated_service in ["Google Gemini", "Open AI GPT", "OpenRouter", "Anthropic Claude", "Deepseek", "Groq", "HuggingFace"]:
                    settings.setValue(f"{translated_service}_api_key", cred['api_key'])
                    if 'selected_model' in cred and cred['selected_model']:
                        settings.setValue(f"{translated_service}_selected_model", cred['selected_model'])
                elif translated_service == "DeeLX":
                    settings.setValue(f"{translated_service}_self_hosted", cred['self_hosted'])
                    settings.setValue(f"{translated_service}_url", cred['url'])
                elif translated_service == "9Router":
                    settings.setValue(f"{translated_service}_api_url", cred['api_url'])
                    settings.setValue(f"{translated_service}_api_key", cred['api_key'])
                    if 'selected_model' in cred and cred['selected_model']:
                        settings.setValue(f"{translated_service}_selected_model", cred['selected_model'])
                elif translated_service == "Googletrans":
                    pass
                else:
                    settings.setValue(f"{translated_service}_api_key", cred['api_key'])
        else:
            settings.remove('credentials')  # Clear all credentials if save_keys is unchecked
        settings.endGroup()

    def load_settings(self):
        self._loading_settings = True
        settings = QSettings("UnComicLabs", "UnComicTranslate")

        # Load language
        language = settings.value('language', 'English')
        translated_language = self.ui.reverse_mappings.get(language, language)
        self.ui.lang_combo.setCurrentText(translated_language)

        # Load theme
        theme = settings.value('theme', 'Dark')
        translated_theme = self.ui.reverse_mappings.get(theme, theme)
        self.ui.theme_combo.setCurrentText(translated_theme)
        self.theme_changed.emit(translated_theme)

        # Load tools settings
        settings.beginGroup('tools')
        raw_translator = settings.value('translator', 'Google Gemini')
        translator = TRANSLATOR_MIGRATIONS.get(raw_translator, raw_translator)
        # If the loaded translator is an old model name (e.g. GPT-4.1), map it to a platform
        MODEL_TO_PLATFORM = {
            "GPT-4.1": "Open AI GPT",
            "GPT-4.1-mini": "Open AI GPT",
            "Gemini-2.5-Flash": "Google Gemini",
            "Gemini-2.5-Pro": "Google Gemini",
            "Deepseek-v3": "Deepseek",
            "Claude-4.5-Sonnet": "Anthropic Claude",
            "Claude-4.5-Haiku": "Anthropic Claude",
            "Llama-3-70b": "Groq",
        }
        if translator in MODEL_TO_PLATFORM:
            translator = MODEL_TO_PLATFORM[translator]
            
        translated_translator = self.ui.reverse_mappings.get(translator, translator)
        self.ui.translator_combo.setCurrentText(translated_translator)

        raw_ocr = settings.value('ocr', 'Default')
        ocr = OCR_MIGRATIONS.get(raw_ocr, raw_ocr)
        translated_ocr = self.ui.reverse_mappings.get(ocr, ocr)
        self.ui.ocr_combo.setCurrentText(translated_ocr)

        raw_inpainter = settings.value('inpainter', 'LaMa')
        inpainter = INPAINTER_MIGRATIONS.get(raw_inpainter, raw_inpainter)
        translated_inpainter = self.ui.reverse_mappings.get(inpainter, inpainter)
        self.ui.inpainter_combo.setCurrentText(translated_inpainter)

        detector = settings.value('detector', 'RT-DETR-V2')
        translated_detector = self.ui.reverse_mappings.get(detector, detector)
        self.ui.detector_combo.setCurrentText(translated_detector)

        self.ui.use_gpu_checkbox.setChecked(settings.value('use_gpu', False, type=bool))

        # Load HD strategy settings
        settings.beginGroup('hd_strategy')
        strategy = settings.value('strategy', 'Resize')
        translated_strategy = self.ui.reverse_mappings.get(strategy, strategy)
        self.ui.inpaint_strategy_combo.setCurrentText(translated_strategy)
        if strategy == 'Resize':
            self.ui.resize_spinbox.setValue(settings.value('resize_limit', 960, type=int))
        elif strategy == 'Crop':
            self.ui.crop_margin_spinbox.setValue(settings.value('crop_margin', 512, type=int))
            self.ui.crop_trigger_spinbox.setValue(settings.value('crop_trigger_size', 512, type=int))
        settings.endGroup()  # hd_strategy
        settings.endGroup()  # tools

        # Load LLM settings
        settings.beginGroup('llm')
        self.ui.extra_context.setPlainText(settings.value('extra_context', ''))
        self.ui.image_checkbox.setChecked(settings.value('image_input_enabled', False, type=bool))
        temp = settings.value('temperature', 1.0, type=float)
        self.ui.temp_edit.setText(f"{temp:.2f}")
        top_p = settings.value('top_p', 0.95, type=float)
        self.ui.top_p_edit.setText(f"{top_p:.2f}")
        max_tokens = settings.value('max_tokens', 4096, type=int)
        self.ui.max_tokens_edit.setText(str(max_tokens))
        settings.endGroup()

        # Load export settings
        settings.beginGroup('export')
        self.ui.raw_text_checkbox.setChecked(settings.value('export_raw_text', False, type=bool))
        self.ui.translated_text_checkbox.setChecked(settings.value('export_translated_text', False, type=bool))
        self.ui.inpainted_image_checkbox.setChecked(settings.value('export_inpainted_image', False, type=bool))
        self.ui.web_json_checkbox.setChecked(settings.value('export_web_json', False, type=bool))
        settings.beginGroup('save_as')
        
        # Default mappings for file format conversion
        default_save_as = {
            '.pdf': 'pdf',
            '.epub': 'pdf',
            '.cbr': 'cbz',
            '.cbz': 'cbz',
            '.cb7': 'cb7',
            '.cbt': 'cbz',
            '.zip': 'zip',
            '.rar': 'zip'
        }
        
        for file_type in self.ui.from_file_types:
            file_ext = f'.{file_type}'
            default_value = default_save_as.get(file_ext, file_type)
            self.ui.export_widgets[f'{file_ext}_save_as'].setCurrentText(settings.value(file_ext, default_value))
        settings.endGroup()  # save_as
        settings.endGroup()  # export

        # Load credentials
        settings.beginGroup('credentials')
        save_keys = settings.value('save_keys', False, type=bool)
        self.ui.save_keys_checkbox.setChecked(save_keys)
        if save_keys:
            for service in self.ui.credential_services:
                translated_service = self.ui.value_mappings.get(service, service)
                if translated_service == "Microsoft Azure":
                    self.ui.credential_widgets["Microsoft Azure_api_key_ocr"].setText(settings.value(f"{translated_service}_api_key_ocr", ''))
                    self.ui.credential_widgets["Microsoft Azure_api_key_translator"].setText(settings.value(f"{translated_service}_api_key_translator", ''))
                    self.ui.credential_widgets["Microsoft Azure_region"].setText(settings.value(f"{translated_service}_region_translator", ''))
                    self.ui.credential_widgets["Microsoft Azure_endpoint"].setText(settings.value(f"{translated_service}_endpoint", ''))
                elif translated_service == "Custom":
                    self.ui.credential_widgets[f"{translated_service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
                    self.ui.credential_widgets[f"{translated_service}_api_url"].setText(settings.value(f"{translated_service}_api_url", ''))
                    self.ui.credential_widgets[f"{translated_service}_model"].setText(settings.value(f"{translated_service}_model", ''))
                elif translated_service == "Yandex":
                    self.ui.credential_widgets[f"{translated_service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
                    self.ui.credential_widgets[f"{translated_service}_folder_id"].setText(settings.value(f"{translated_service}_folder_id", ''))
                elif translated_service == "Ollama":
                    self.ui.credential_widgets[f"{translated_service}_api_url"].setText(settings.value(f"{translated_service}_api_url", ''))
                    selected_model = settings.value(f"{translated_service}_selected_model", '')
                    if selected_model:
                        model_list_widget = self.ui.credential_widgets[f"{translated_service}_model_list"]
                        model_list_widget.clear()
                        model_list_widget.addItem(selected_model)
                        model_list_widget.setCurrentRow(0)
                elif translated_service in ["Google Gemini", "Open AI GPT", "OpenRouter", "Anthropic Claude", "Deepseek", "Groq", "HuggingFace"]:
                    self.ui.credential_widgets[f"{translated_service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
                    selected_model = settings.value(f"{translated_service}_selected_model", '')
                    if selected_model:
                        model_list_widget = self.ui.credential_widgets[f"{translated_service}_model_list"]
                        model_list_widget.clear()
                        model_list_widget.addItem(selected_model)
                        model_list_widget.setCurrentRow(0)
                elif translated_service == "Comic Translate (Official)":
                    # For Official, we only load the selected model
                    selected_model = settings.value(f"{translated_service}_selected_model", '')
                    if selected_model:
                        model_list_widget = self.ui.credential_widgets[f"{translated_service}_model_list"]
                        model_list_widget.clear()
                        model_list_widget.addItem(selected_model)
                        model_list_widget.setCurrentRow(0)
                elif translated_service == "DeeLX":
                    self.ui.credential_widgets[f"{translated_service}_self_hosted"].setChecked(settings.value(f"{translated_service}_self_hosted", False, type=bool))
                    self.ui.credential_widgets[f"{translated_service}_url"].setText(settings.value(f"{translated_service}_url", ''))
                elif translated_service == "9Router":
                    self.ui.credential_widgets[f"{translated_service}_api_url"].setText(settings.value(f"{translated_service}_api_url", 'http://localhost:20128/v1'))
                    self.ui.credential_widgets[f"{translated_service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
                    selected_model = settings.value(f"{translated_service}_selected_model", '')
                    if selected_model:
                        model_list_widget = self.ui.credential_widgets[f"{translated_service}_model_list"]
                        model_list_widget.clear()
                        model_list_widget.addItem(selected_model)
                        model_list_widget.setCurrentRow(0)
                elif translated_service == "Googletrans":
                    pass
                else:
                    self.ui.credential_widgets[f"{translated_service}_api_key"].setText(settings.value(f"{translated_service}_api_key", ''))
        settings.endGroup()
        self.ui.credentials_page.update_status_indicators()
        
        # Load user info and update account view
        self._load_user_info_from_settings()
        self._update_account_view()
        
        # Load selected fonts
        self.load_selected_fonts()
        
        # Check session if logged in
        if self.is_logged_in():
            self.auth_client.check_session_async()

        self._loading_settings = False

    def on_language_changed(self, new_language):
        if not self._loading_settings:  
            self.show_restart_dialog()

    def show_restart_dialog(self):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle(self.tr("Restart Required"))
        msg_box.setText(self.tr("Please restart the application for the language changes to take effect."))
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def get_min_font_size(self):
        return int(self.ui.min_font_spinbox.value())
    
    def get_max_font_size(self):
        return int(self.ui.max_font_spinbox.value())

    def add_font_family(self, font_input: str) -> QFont:
        # Check if font_input is a file path
        if os.path.splitext(font_input)[1].lower() in [".ttf", ".ttc", ".otf", ".woff", ".woff2"]:
            font_id = QFontDatabase.addApplicationFont(font_input)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    return font_families[0]
        
        # If not a file path or loading failed, treat as font family name
        return font_input

    def start_sign_in(self):
        """Initiates the authentication flow."""
        official_widget = self.ui.credentials_page.platform_widgets.get("Comic Translate (Official)")
        if official_widget:
            official_widget.sign_in_btn.setText(self.tr("Signing in..."))
            official_widget.sign_in_btn.setEnabled(False)
        self.auth_client.start_auth_flow()

    def cancel_sign_in(self):
        """Cancels the active authentication flow."""
        self.auth_client.cancel_auth_flow()

    def show_login_view(self, url: str):
        """Opens the login URL in the system browser."""
        QDesktopServices.openUrl(QUrl(url))

    def handle_auth_success(self, user_info: dict):
        """Handles successful authentication."""
        self._reset_sign_in_button()
        self.user_email = user_info.get('email')
        self.user_tier = user_info.get('tier')
        self.user_credits = user_info.get('credits')
        self.user_monthly_credits = user_info.get('monthly_credits')
        self._save_user_info_to_settings()
        self._update_account_view()

    def handle_auth_error(self, error_message: str):
        """Handles authentication errors."""
        self._reset_sign_in_button()
        if "cancelled" not in error_message.lower():
            QtWidgets.QMessageBox.warning(self, self.tr("Sign In Error"), error_message)

    def handle_auth_cancelled(self):
        """Handles the signal emitted when the auth flow is cancelled."""
        self._reset_sign_in_button()

    def _reset_sign_in_button(self):
        official_widget = self.ui.credentials_page.platform_widgets.get("Comic Translate (Official)")
        if official_widget:
            official_widget.sign_in_btn.setText(self.tr("Sign In to Official Account"))
            try:
                official_widget.sign_in_btn.setEnabled(True)
            except Exception: pass

    def sign_out(self):
        """Initiates the sign-out process."""
        if QtWidgets.QMessageBox.question(self, self.tr("Sign Out"), self.tr("Are you sure?")) == QtWidgets.QMessageBox.Yes:
            self.auth_client.logout()

    def handle_logout_success(self):
        """Handles successful logout."""
        self.user_email = None
        self.user_tier = None
        self.user_credits = None
        self.user_monthly_credits = None
        self._update_account_view()

    def handle_session_check_finished(self, is_valid: bool):
        if not is_valid:
            self.auth_client.logout()

    def is_logged_in(self):
        return self.auth_client.is_authenticated()

    def _update_account_view(self):
        """Updates the UI elements on the Credentials -> Official page based on login state."""
        official_widget = self.ui.credentials_page.platform_widgets.get("Comic Translate (Official)")
        if not official_widget:
            return

        if self.is_logged_in():
            official_widget.official_logged_out_widget.hide()
            official_widget.official_logged_in_widget.show()
            
            official_widget.official_email_label.setText(f"{self.tr('Email:')} {self.user_email or self.tr('N/A')}")
            
            credits_text = self.tr("N/A")
            if isinstance(self.user_credits, dict):
                total = self.user_credits.get('total', 0)
                credits_text = f"{total:,}"
            elif self.user_credits is not None:
                credits_text = f"{int(self.user_credits):,}"
            
            official_widget.official_credits_label.setText(f"{self.tr('Credits:')} {credits_text}")
        else:
            official_widget.official_logged_in_widget.hide()
            official_widget.official_logged_out_widget.show()
            official_widget.sign_in_btn.setText(self.tr("Sign In to Official Account"))
        
        self.ui.credentials_page.update_status_indicators()

    def open_pricing_page(self):
        QDesktopServices.openUrl(QUrl(f"{FRONTEND_BASE_URL}/pricing/"))

    def _load_user_info_from_settings(self):
        settings = QSettings("UnComicLabs", "UnComicTranslate")
        settings.beginGroup(USER_INFO_GROUP)
        self.user_email = settings.value(EMAIL_KEY, None)
        self.user_tier = settings.value(TIER_KEY, None)
        self.user_credits = settings.value(CREDITS_KEY, None)
        self.user_monthly_credits = settings.value(MONTHLY_CREDITS_KEY, None)
        if isinstance(self.user_credits, str):
            try: self.user_credits = json.loads(self.user_credits)
            except Exception: pass
        settings.endGroup()

    def _save_user_info_to_settings(self):
        settings = QSettings("UnComicLabs", "UnComicTranslate")
        settings.beginGroup(USER_INFO_GROUP)
        settings.setValue(EMAIL_KEY, self.user_email)
        settings.setValue(TIER_KEY, self.user_tier)
        settings.setValue(MONTHLY_CREDITS_KEY, self.user_monthly_credits)
        if isinstance(self.user_credits, dict):
            settings.setValue(CREDITS_KEY, json.dumps(self.user_credits))
        else:
            settings.setValue(CREDITS_KEY, self.user_credits)
        settings.endGroup()

    def save_selected_fonts(self):
        """Save selected fonts to settings"""
        settings = QSettings("UnComicLabs", "UnComicTranslate")
        selected_fonts = self.ui.text_rendering_page.get_selected_fonts()
        settings.setValue('selected_fonts', selected_fonts)
    
    def load_selected_fonts(self):
        """Load selected fonts from settings and populate the font list"""
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..'))
        font_folder_path = os.path.join(project_root, 'resources', 'fonts')
        
        # Clear existing font list
        self.ui.text_rendering_page.clear_font_list()
        
        # Load selected fonts from settings
        settings = QSettings("UnComicLabs", "UnComicTranslate")
        selected_fonts = settings.value('selected_fonts', None)
        
        # If selected_fonts is None (first time), select all fonts by default
        first_time = selected_fonts is None
        if not isinstance(selected_fonts, list):
            selected_fonts = []
        
        # Add system fonts first
        font_db = QFontDatabase()
        system_fonts = font_db.families()
        for font_family in sorted(system_fonts):
            # Check if this font was previously selected, or select all if first time
            is_selected = (font_family in selected_fonts) if not first_time else True
            self.ui.text_rendering_page.add_font_to_list('', font_family, checked=is_selected)
        
        # Get all custom font files
        if os.path.exists(font_folder_path):
            font_files = [os.path.join(font_folder_path, f) for f in os.listdir(font_folder_path) 
                          if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]
            
            # Add custom fonts to the list
            for font_path in font_files:
                font_family = self.add_font_family(font_path)
                # Check if this font was previously selected, or select all if first time
                is_selected = (font_family in selected_fonts) if not first_time else True
                # Only add if not already in system fonts
                if font_family not in system_fonts:
                    self.ui.text_rendering_page.add_font_to_list(font_path, font_family, checked=is_selected)
        
        # If first time, save the default selection (all fonts)
        if first_time:
            self.save_selected_fonts()


