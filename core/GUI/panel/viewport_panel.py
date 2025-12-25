from PyQt6.QtCore import QRect, pyqtSlot
from PyQt6.QtGui import QPaintEvent, QPainter, QColor

from core.GUI.panel.base_panel import BasePanel

from core.GUI.themes import ACTIVE_THEME
from core.project.project import Project


class ViewportPanel(BasePanel):
    """A panel that shows the video output viewport"""

    def __init__(self, parent, project: Project):
        super().__init__(parent, project)
        self.draw_transparency_indicator = False  # TODO make this an accessible setting

        self.project.application_state.signal_frame_buffer_update.connect(self.handle_frame_update)

        self.current_frame = self.project.application_state.rendered_frame.visual_frame

        self.panel_type = 'ViewportPanel'

        self.checkerboard_light = QColor("#CCCCCC")
        self.checkerboard_dark = QColor("#999999")
        self.transparency_background = QColor("#000000")
        self.checkerboard_size = 16  # px

    @pyqtSlot()
    def handle_frame_update(self):
        """A new rendered frame is available"""
        self.current_frame = self.project.application_state.rendered_frame.visual_frame
        self.update()

    def paintEvent(self, event: QPaintEvent):
        """Draw the frame. Keep aspect ratio"""
        painter = QPainter(self)

        # Fill entire widget with background colour
        painter.fillRect(QRect(0, 0, self.width(), self.height()), QColor(ACTIVE_THEME.background))

        # Get frame dimensions
        frame_width = self.current_frame.width()
        frame_height = self.current_frame.height()

        assert frame_width != 0 and frame_height != 0, f"Framebuffer has zero area ({frame_width, frame_height}) px"

        # Calculate aspect ratio
        frame_aspect = frame_width / frame_height
        widget_aspect = self.width() / self.height()

        # Determine scaling based on limiting dimension
        if widget_aspect > frame_aspect:
            # Widget is wider, height is limiting
            target_height = self.height()
            target_width = int(target_height * frame_aspect)
        else:
            # Widget is taller, width is limiting
            target_width = self.width()
            target_height = int(target_width / frame_aspect)

        # Centre the frame
        x_offset = (self.width() - target_width) // 2
        y_offset = (self.height() - target_height) // 2

        target_rect = QRect(x_offset, y_offset, target_width, target_height)

        if self.draw_transparency_indicator:
            self._draw_transparency_checkerboard(x_offset, y_offset, target_width, target_height, painter)
        else:
            painter.fillRect(target_rect, self.transparency_background)

        # Draw the frame on top
        painter.drawImage(target_rect, self.current_frame)

    def _draw_transparency_checkerboard(self, x_offset, y_offset, target_width, target_height, painter):
        """
        Utility function to draw the transparency checkerboard.
        I don't like it. It works.
        """
        checker_size = self.checkerboard_size

        for y in range(y_offset, y_offset + target_height, checker_size):
            row = (y - y_offset) // checker_size
            for x in range(x_offset, x_offset + target_width, checker_size):
                # Determine which colour based on position
                col = (x - x_offset) // checker_size

                if (row + col) % 2 == 0:
                    painter.fillRect(x, y, checker_size, checker_size, self.checkerboard_light)
                else:
                    painter.fillRect(x, y, checker_size, checker_size, self.checkerboard_dark)
            # Draw an extra square at the end
            col_count = (target_width - 1) // checker_size
            if (row + col_count) % 2 == 0:
                painter.fillRect(x_offset + (col_count + 1) * checker_size, y, target_width - col_count * checker_size, checker_size, self.checkerboard_dark)
            else:
                painter.fillRect(x_offset + (col_count + 1) * checker_size, y, target_width - col_count * checker_size, checker_size, self.checkerboard_light)

        # Draw the last row
        row = (target_height - 1) // checker_size
        start_y = y_offset + row * checker_size
        for x in range(x_offset, x_offset + target_width, checker_size):
            # Determine which colour based on position
            col = (x - x_offset) // checker_size

            if (row + col) % 2 == 0:
                painter.fillRect(x, start_y + checker_size, checker_size, target_height - row * checker_size, self.checkerboard_dark)
            else:
                painter.fillRect(x, start_y + checker_size, checker_size, target_height - row * checker_size, self.checkerboard_light)
        # Draw an extra square at the end
        col_count = (target_width - 1) // checker_size
        if (row + col_count) % 2 == 0:
            painter.fillRect(x_offset + (col_count + 1) * checker_size, start_y, target_width - col_count * checker_size, target_height - row * checker_size, self.checkerboard_dark)
        else:
            painter.fillRect(x_offset + (col_count + 1) * checker_size, start_y, target_width - col_count * checker_size, target_height - row * checker_size, self.checkerboard_light)
