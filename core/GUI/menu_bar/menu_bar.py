from PyQt6.QtWidgets import QMenuBar

from core.GUI.themes import ACTIVE_THEME


class MenuBar(QMenuBar):
    """Wrapper for QMenuBar with styling"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Apply menu button colours
        self.setStyleSheet(f"""
            QMenuBar {{
                background-color: {ACTIVE_THEME.protected_menu_button};
                color: {ACTIVE_THEME.protected_menu_button_text};
            }}
            QMenuBar::item {{
                background-color: {ACTIVE_THEME.protected_menu_button};
                color: {ACTIVE_THEME.protected_menu_button_text};
            }}
            QMenuBar::item:selected {{
                background-color: {ACTIVE_THEME.protected_menu_button_hover};
            }}
            QMenuBar::item:pressed {{
                background-color: {ACTIVE_THEME.protected_menu_button_hover};
            }}
            
            QMenu {{
                background-color: transparent;
                color: {ACTIVE_THEME.protected_menu_button_text};
                border: 1px solid {ACTIVE_THEME.divider};
            }}
            QMenu::item {{
                background-color: transparent;
                color: {ACTIVE_THEME.protected_menu_button_text};
                padding: 5px 20px;
            }}
            QMenu::item:selected {{
                background-color: {ACTIVE_THEME.protected_menu_button_hover};
                color: {ACTIVE_THEME.protected_menu_button_text};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {ACTIVE_THEME.divider};
                margin: 5px 0px;
            }}
            QMenu::item:selected shortcut {{
                color: {ACTIVE_THEME.protected_menu_button_hint_text};
            }}
            QMenu::item shortcut {{
                color: {ACTIVE_THEME.protected_menu_button_hint_text};
            }}
        """)
