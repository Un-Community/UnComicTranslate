import os
from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QTimer
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.spin_box import MSpinBox
from ..dayu_widgets.browser import MClickBrowserFileToolButton
from ..dayu_widgets.check_box import MCheckBox

class TextRenderingPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        
        # Timer to debounce font updates
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(300)  # 300ms delay
        self._update_timer.timeout.connect(self._do_font_update)

        # Font section
        font_layout = QtWidgets.QVBoxLayout()
        min_font_layout = QtWidgets.QHBoxLayout()
        max_font_layout = QtWidgets.QHBoxLayout()
        min_font_label = MLabel(self.tr("Minimum Font Size:"))
        max_font_label = MLabel(self.tr("Maximum Font Size:"))

        self.min_font_spinbox = MSpinBox().small()
        self.min_font_spinbox.setFixedWidth(60)
        self.min_font_spinbox.setMaximum(100)
        self.min_font_spinbox.setValue(9)

        self.max_font_spinbox = MSpinBox().small()
        self.max_font_spinbox.setFixedWidth(60)
        self.max_font_spinbox.setMaximum(100)
        self.max_font_spinbox.setValue(40)

        min_font_layout.addWidget(min_font_label)
        min_font_layout.addWidget(self.min_font_spinbox)
        min_font_layout.addStretch()

        max_font_layout.addWidget(max_font_label)
        max_font_layout.addWidget(self.max_font_spinbox)
        max_font_layout.addStretch()

        font_label = MLabel(self.tr("Font:")).h4()

        font_browser_layout = QtWidgets.QHBoxLayout()
        import_font_label = MLabel(self.tr("Import Font:"))
        self.font_browser = MClickBrowserFileToolButton(multiple=True)
        self.font_browser.set_dayu_filters([".ttf", ".ttc", ".otf", ".woff", ".woff2"])
        self.font_browser.setToolTip(self.tr("Import the Font to use for Rendering Text on Images"))

        font_browser_layout.addWidget(import_font_label)
        font_browser_layout.addWidget(self.font_browser)
        font_browser_layout.addStretch()

        font_layout.addWidget(font_label)
        font_layout.addLayout(font_browser_layout)
        font_layout.addLayout(min_font_layout)
        font_layout.addLayout(max_font_layout)

        # Font list section
        font_list_label = MLabel(self.tr("Available Fonts:"))
        font_layout.addSpacing(10)
        font_layout.addWidget(font_list_label)
        
        # Search box and Select All/Deselect All button
        search_and_select_layout = QtWidgets.QHBoxLayout()
        
        from ..dayu_widgets.line_edit import MLineEdit
        self.font_search_box = MLineEdit()
        self.font_search_box.setPlaceholderText(self.tr("Search fonts..."))
        self.font_search_box.textChanged.connect(self.filter_fonts)
        
        from ..dayu_widgets.push_button import MPushButton
        self.select_all_button = MPushButton(self.tr("Select All"))
        self.select_all_button.clicked.connect(self.toggle_select_all)
        self.select_all_button.setFixedWidth(100)
        
        search_and_select_layout.addWidget(self.font_search_box)
        search_and_select_layout.addWidget(self.select_all_button)
        
        font_layout.addLayout(search_and_select_layout)
        
        # Scroll area for font list
        self.font_list_widget = QtWidgets.QWidget()
        self.font_list_layout = QtWidgets.QVBoxLayout(self.font_list_widget)
        self.font_list_layout.setContentsMargins(0, 0, 0, 0)
        self.font_list_layout.addStretch()
        
        font_scroll = QtWidgets.QScrollArea()
        font_scroll.setWidgetResizable(True)
        font_scroll.setWidget(self.font_list_widget)
        font_scroll.setMaximumHeight(200)
        font_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        font_layout.addWidget(font_scroll)
        
        # Dictionary to store font checkboxes
        self.font_checkboxes = {}

        # Uppercase
        self.uppercase_checkbox = MCheckBox(self.tr("Render Text in UpperCase"))

        layout.addWidget(self.uppercase_checkbox)
        layout.addSpacing(10)
        layout.addLayout(font_layout)
        layout.addSpacing(10)
        layout.addStretch(1)
    
    def add_font_to_list(self, font_path: str, font_family: str, checked: bool = True):
        """Add a font checkbox to the list"""
        if font_family in self.font_checkboxes:
            return
        
        checkbox = MCheckBox(font_family)
        checkbox.setChecked(checked)
        checkbox.setProperty('font_path', font_path)
        
        # Connect checkbox state change to parent's save method
        checkbox.stateChanged.connect(self._on_font_checkbox_changed)
        
        # Insert before the stretch
        self.font_list_layout.insertWidget(self.font_list_layout.count() - 1, checkbox)
        self.font_checkboxes[font_family] = checkbox
    
    def _on_font_checkbox_changed(self):
        """Called when any font checkbox is changed"""
        # Use timer to debounce multiple rapid changes
        self._update_timer.stop()
        self._update_timer.start()
    
    def _do_font_update(self):
        """Actually perform the font update after debounce delay"""
        # Find SettingsPage (parent of SettingsPageUI)
        settings_page = None
        parent = self.parent()
        while parent:
            if parent.__class__.__name__ == 'SettingsPage':
                settings_page = parent
                break
            parent = parent.parent()
        
        if settings_page and hasattr(settings_page, 'save_selected_fonts'):
            settings_page.save_selected_fonts()
            
            # Find main window - need to go up through QStackedWidget to ComicTranslateUI
            current = settings_page.parent()
            main_window = None
            while current:
                if hasattr(current, 'load_selected_fonts'):
                    main_window = current
                    break
                current = current.parent()
            
            if main_window:
                main_window.load_selected_fonts()
                # Apply changes to current block if any
                if hasattr(main_window, 'text_ctrl'):
                    main_window.text_ctrl.on_font_dropdown_change(main_window.font_dropdown.currentText())
    
    def remove_font_from_list(self, font_family: str):
        """Remove a font checkbox from the list"""
        if font_family in self.font_checkboxes:
            checkbox = self.font_checkboxes[font_family]
            self.font_list_layout.removeWidget(checkbox)
            checkbox.deleteLater()
            del self.font_checkboxes[font_family]
    
    def get_selected_fonts(self):
        """Get list of selected font families"""
        return [family for family, checkbox in self.font_checkboxes.items() if checkbox.isChecked()]
    
    def clear_font_list(self):
        """Clear all font checkboxes"""
        for font_family in list(self.font_checkboxes.keys()):
            self.remove_font_from_list(font_family)
    
    def filter_fonts(self, search_text: str):
        """Filter font list based on search text"""
        search_text = search_text.lower()
        for font_family, checkbox in self.font_checkboxes.items():
            if search_text in font_family.lower():
                checkbox.setVisible(True)
            else:
                checkbox.setVisible(False)
    
    def toggle_select_all(self):
        """Toggle between Select All and Deselect All"""
        # Check if all visible fonts are selected
        visible_checkboxes = [cb for cb in self.font_checkboxes.values() if cb.isVisible()]
        if not visible_checkboxes:
            return
        
        all_checked = all(cb.isChecked() for cb in visible_checkboxes)
        
        # Toggle all visible checkboxes
        for checkbox in visible_checkboxes:
            checkbox.setChecked(not all_checked)
        
        # Update button text
        if all_checked:
            self.select_all_button.setText(self.tr("Select All"))
        else:
            self.select_all_button.setText(self.tr("Deselect All"))
