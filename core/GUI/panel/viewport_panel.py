from PyQt6.QtCore import QRect, pyqtSlot
from PyQt6.QtGui import QPaintEvent, QPainter, QColor, QTransform, QResizeEvent

from core.GUI.panel.base_panel import BasePanel

from core.GUI.themes import ACTIVE_THEME
from core.project.project import Project


class ViewportPanel(BasePanel):
    """A panel that shows the video output viewport"""

    def __init__(self, parent, project: Project):
        super().__init__(parent, project)
        self.draw_transparency_indicator = False  # TODO make this an accessible setting

        self.project.application_state.signal_frame_buffer_update.connect(self.handle_frame_update)
        self.project.application_state.signal_entry_selection_update.connect(self.handle_entry_selection_update)

        self.current_frame = self.project.application_state.rendered_frame.visual_frame
        self.frame_to_widget: QTransform = QTransform()  # Frame to widget transform
        self.target_rect: QRect = QRect()  # Rectangle containing the visible frame

        self.panel_type = 'ViewportPanel'

        self.checkerboard_light = QColor("#CCCCCC")
        self.checkerboard_dark = QColor("#999999")
        self.transparency_background = QColor("#000000")
        self.checkerboard_size = 16  # px

        self.padding = 32  # px of padding around the frame

        self.update_frame_transform()

    @pyqtSlot()
    def handle_frame_update(self):
        """A new rendered frame is available"""
        self.current_frame = self.project.application_state.rendered_frame.visual_frame
        self.update()

    @pyqtSlot()
    def handle_entry_selection_update(self):
        """Called when the selection status of the entries change"""
        self.update()

    def paintEvent(self, event: QPaintEvent):
        """Draw the frame. Keep aspect ratio"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(QRect(0, 0, self.width(), self.height()), QColor(ACTIVE_THEME.background))

        if self.draw_transparency_indicator:
            self._draw_transparency_checkerboard(self.target_rect.x(), self.target_rect.y(),
                                                 self.target_rect.width(), self.target_rect.height(), painter)
        else:
            painter.fillRect(self.target_rect, self.transparency_background)

        painter.drawImage(self.target_rect, self.current_frame)

        for entry in self.project.application_state.rendered_entries:
            entry.timeline_object.paint_viewport_overlay(painter, self.frame_to_widget)

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

    def resizeEvent(self, event: QResizeEvent):
        """Recalculate frame transform whenever widget is resized"""
        super().resizeEvent(event)
        self.update_frame_transform()

    def update_frame_transform(self):
        """Calculate the transform from frame coordinates to widget coordinates"""
        frame_width = self.current_frame.width()
        frame_height = self.current_frame.height()

        if frame_width == 0 or frame_height == 0:
            self.frame_to_widget = QTransform()
            self.target_rect = QRect()
            return

        frame_aspect = frame_width / frame_height
        widget_aspect = self.width() / self.height()

        if widget_aspect > frame_aspect:
            target_height = max(1, self.height() - self.padding)
            target_width = int(target_height * frame_aspect)
        else:
            target_width = max(1, self.width() - self.padding)
            target_height = int(target_width / frame_aspect)

        x_offset = (self.width() - target_width) // 2
        y_offset = (self.height() - target_height) // 2

        self.target_rect = QRect(x_offset, y_offset, target_width, target_height)

        visual_frame_width = self.project.application_state.rendered_frame.visual_frame.width()
        visual_frame_height = self.project.application_state.rendered_frame.visual_frame.height()
        scale_x = target_width / visual_frame_width
        scale_y = target_height / visual_frame_height

        self.frame_to_widget = QTransform(scale_x, 0, 0,
                                          0, scale_y, 0,
                                          x_offset, y_offset, 1)
