from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPaintEvent, QPainter, QFont, QColor
from PyQt6.QtWidgets import QWidget

from core.GUI.themes import ACTIVE_THEME
from core.project.project import Project


class BasePanel(QWidget):
    """A panel is any main gui panel that can be shown.
    These are children of frames."""

    def __init__(self, parent, project: Project):
        super().__init__(parent)

        self.panel_type = 'BasePanel'
        self.project = project

class ErrorPanel(BasePanel):
    """A panel to indicate an internal error"""

    def __init__(self, parent, project: Project):
        super().__init__(parent, project)

        self.panel_type = 'ErrorPanel'

    def paintEvent(self, event: QPaintEvent):
        """Draw an error indicator """
        painter = QPainter(self)

        # Fill entire widget with error background colour
        painter.fillRect(QRect(0, 0, self.width(), self.height()), QColor(ACTIVE_THEME.error))

        # Configure text rendering
        painter.setPen(QColor(ACTIVE_THEME.on_error))
        font = QFont()
        font.setBold(True)
        font.setPointSize(24)
        painter.setFont(font)

        # Draw centred ERROR text
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "ERROR")
