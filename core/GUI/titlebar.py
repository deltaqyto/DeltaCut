"""
Implementation using frameless window by ZhiYiYo @ https://github.com/zhiyiYo/PyQt-Frameless-Window
"""

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget

from qframelesswindow import TitleBar

from core.GUI.themes import ACTIVE_THEME

class ApplicationTitleBar(TitleBar):
    """ Custom title bar """

    def __init__(self, parent):
        super().__init__(parent)

        # Create background widget for title bar colour
        self.backgroundWidget = QWidget(self)
        self.backgroundWidget.setStyleSheet(f"""
                    QWidget {{
                        background-color: {ACTIVE_THEME.background};
                    }}
                """)
        self.backgroundWidget.lower()

        # Min button
        self.minBtn.setNormalColor(QColor(ACTIVE_THEME.protected_resize_button_text))
        self.minBtn.setNormalBackgroundColor(QColor(ACTIVE_THEME.protected_resize_button))
        self.minBtn.setHoverColor(QColor(ACTIVE_THEME.protected_resize_button_text))
        self.minBtn.setHoverBackgroundColor(QColor(ACTIVE_THEME.protected_resize_button_hover))
        self.minBtn.setPressedColor(QColor(ACTIVE_THEME.protected_resize_button_text))
        self.minBtn.setPressedBackgroundColor(QColor(ACTIVE_THEME.protected_resize_button_press))

        # Max button
        self.maxBtn.setNormalColor(QColor(ACTIVE_THEME.protected_resize_button_text))
        self.maxBtn.setNormalBackgroundColor(QColor(ACTIVE_THEME.protected_resize_button))
        self.maxBtn.setHoverColor(QColor(ACTIVE_THEME.protected_resize_button_text))
        self.maxBtn.setHoverBackgroundColor(QColor(ACTIVE_THEME.protected_resize_button_hover))
        self.maxBtn.setPressedColor(QColor(ACTIVE_THEME.protected_resize_button_text))
        self.maxBtn.setPressedBackgroundColor(QColor(ACTIVE_THEME.protected_resize_button_press))

        # Close button
        self.closeBtn.setNormalColor(QColor(ACTIVE_THEME.protected_resize_button_text))
        self.closeBtn.setNormalBackgroundColor(QColor(ACTIVE_THEME.protected_close_button))
        self.closeBtn.setHoverColor(QColor(ACTIVE_THEME.protected_close_button_text))
        self.closeBtn.setHoverBackgroundColor(QColor(ACTIVE_THEME.protected_close_button_hover))
        self.closeBtn.setPressedColor(QColor(ACTIVE_THEME.protected_close_button_text))
        self.closeBtn.setPressedBackgroundColor(QColor(ACTIVE_THEME.protected_close_button_press))
        # TODO add fade animations to color changes

    def resizeEvent(self, event):
        """Update shape of titlebar block"""
        super().resizeEvent(event)
        self.backgroundWidget.setGeometry(0, 0, self.width(), self.height())
