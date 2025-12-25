from math import ceil

from PyQt6.QtCore import QPoint, Qt, QRectF
from PyQt6.QtGui import QPaintEvent, QPainter, QPen, QColor, QMouseEvent, QResizeEvent, QPainterPath
from PyQt6.QtWidgets import QWidget

from core.GUI.panel.base_panel import BasePanel
from core.GUI.themes import ACTIVE_THEME
from core.GUI.panel.panel_type_registry import PANEL_TYPE_REGISTRY, DEFAULT_PANEL_TYPE
from core.project.project import Project


class CornerWidget(QWidget):
    """Draws a radius sliver at a corner"""
    def __init__(self, parent, rotation:int, radius:int):
        super().__init__(parent)
        self.rotation = rotation
        self.radius = radius
        self.colour = QColor(QColor(ACTIVE_THEME.divider))

        self.setFixedSize(radius, radius)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)  # Makes this widget not clickable

        self.painter = QPainter(self)

    def paintEvent(self, event:QPaintEvent):
        """Draw antialiased sliver"""
        self.painter.begin(self)

        self.painter.translate(self.width() / 2, self.height() / 2)
        self.painter.rotate(self.rotation)
        self.painter.translate(-self.width() / 2, -self.height() / 2)
        self.painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect_path = QPainterPath()
        rect_path.addRect(QRectF(0, 0, self.width(), self.height()))

        circle_path = QPainterPath()
        circle_path.addEllipse(QRectF(0, 0, self.radius * 2, self.radius * 2))

        sliver_path = rect_path.subtracted(circle_path)
        self.painter.fillPath(sliver_path, self.colour)
        self.painter.end()
        event.accept()


class Frame(QWidget):
    """Base adjustable GUI unit, allows splitting into two sub-frames for different display windows"""

    def  __init__(self, parent, project: Project, panel_type=DEFAULT_PANEL_TYPE, serialised_data=None):
        super().__init__(parent)
        self.project = project

        self.is_bisected: bool = False
        self.vertical_bisection: bool = False
        self.division_ratio: float = 0.5

        self.painter = QPainter()
        self.pen = QPen()
        self.pen.setColor(QColor(ACTIVE_THEME.divider))

        # Mouse drag handling
        self.corner_collider_radius = 12  # px
        self.divider_collider_radius = 4  # px
        self.bisection_drag_threshold = 100  # px
        self.divider_collapse_distance = 20  # px

        self.divider_visual_width = 2  # px

        self.drag_start_position = QPoint(0, 0)
        self.is_dragging = False
        self.started_corner_drag = False 
        self.is_dragging_divider = False

        self.corner_widgets = [CornerWidget(self, 0, self.corner_collider_radius),
                               CornerWidget(self, 90, self.corner_collider_radius),
                               CornerWidget(self, 270, self.corner_collider_radius),
                               CornerWidget(self, 180, self.corner_collider_radius)]
        self.update_corner_widgets()
        self.show_corner_widgets()

        self.subframe_a: Frame | None = None
        self.subframe_b: Frame | None = None

        self.panel_type = panel_type

        self.child_panel: BasePanel | None = None
        self.create_child_panel() if serialised_data is None else None

        if serialised_data is not None:
            self.deserialise_layout(serialised_data)


    def serialise_layout(self):
        """Serialise frame and sub frames/child panels"""
        return {'frame': {'is_bisected': self.is_bisected, 'vertical': self.vertical_bisection, 'division_ratio': self.division_ratio},
                'child_a': self.subframe_a.serialise_layout() if self.subframe_a is not None else None,
                'child_b': self.subframe_b.serialise_layout() if self.subframe_b is not None else None,
                'panel_type': self.child_panel.panel_type if self.child_panel is not None else None}

    def deserialise_layout(self, serialised_data):
        """Restore frame and sub-frames/child panel from serialisation"""
        self.is_dragging = False
        self.started_corner_drag = False
        self.is_dragging_divider = False

        self.subframe_a.setParent(None) if self.subframe_a is not None else None
        self.subframe_a.destroy() if self.subframe_a is not None else None
        self.subframe_a = None

        self.subframe_b.setParent(None) if self.subframe_b is not None else None
        self.subframe_b.destroy() if self.subframe_b is not None else None
        self.subframe_b = None

        self.child_panel.setParent(None) if self.child_panel is not None else None
        self.child_panel.destroy() if self.child_panel is not None else None
        self.child_panel = None

        self.is_bisected = serialised_data['frame']['is_bisected']
        self.vertical_bisection = serialised_data['frame']['vertical']
        self.division_ratio = serialised_data['frame']['division_ratio']
        self.panel_type = serialised_data['panel_type']

        if self.is_bisected:
            self.create_subframes(serialised_data['child_a'], serialised_data['child_b'])
        else:
            self.create_child_panel()
        self.update()

    def create_child_panel(self):
        """Create a child panel based on panel type and registry"""
        self.child_panel = PANEL_TYPE_REGISTRY[self.panel_type](self, self.project) if self.panel_type is not None else None
        self.child_panel.resize(self.width(), self.height())
        self.child_panel.show()
        self.update_corner_widgets()
        self.show_corner_widgets()

    def create_subframes(self, serialised_data_a=None, serialised_data_b=None):
        """Create and display brand new subframes.
        Frame A gets the current panel type"""

        self.subframe_a = Frame(self, self.project, self.panel_type, serialised_data=serialised_data_a)
        self.subframe_b = Frame(self, self.project, DEFAULT_PANEL_TYPE, serialised_data=serialised_data_b)
        self.update_subframe_dimensions()
        self.subframe_a.show()
        self.subframe_b.show()
        self.hide_corner_widgets()

    def update_subframe_dimensions(self):
        """Recompute subframe dimensions and update each"""
        split_pos = self.get_divider_position()
        half_visual_width = ceil(self.divider_visual_width / 2)

        if self.vertical_bisection:
            self.subframe_a.setGeometry(0, 0, split_pos - half_visual_width, self.height())
            self.subframe_b.setGeometry(split_pos + half_visual_width, 0, self.width() - (split_pos + half_visual_width), self.height())
        else:
            self.subframe_a.setGeometry(0, 0, self.width(), split_pos - half_visual_width)
            self.subframe_b.setGeometry(0, split_pos + half_visual_width, self.width(), self.height() - (split_pos + half_visual_width))
        self.subframe_a.update()
        self.subframe_b.update()

    def update_corner_widgets(self):
        """Update position of corner widgets"""
        self.corner_widgets[0].move(0, 0)
        self.corner_widgets[1].move(self.width() - self.corner_collider_radius, 0)
        self.corner_widgets[2].move(0, self.height() - self.corner_collider_radius)
        self.corner_widgets[3].move(self.width() - self.corner_collider_radius, self.height() - self.corner_collider_radius)

    def show_corner_widgets(self):
        """Show and raise corner widgets to the top"""
        [corner.show() for corner in self.corner_widgets]
        [corner.raise_() for corner in self.corner_widgets]
    def hide_corner_widgets(self):
        """Hide corner widgets"""
        [corner.hide() for corner in self.corner_widgets]

    def resizeEvent(self, event:QResizeEvent):
        """Resize subframes if resized"""
        if self.is_bisected:
            self.update_subframe_dimensions()
        else:
            self.update_corner_widgets()
            self.child_panel.resize(self.width(), self.height())
        QWidget.resizeEvent(self, event)

    def paintEvent(self, event:QPaintEvent):
        """Draw divider if visible"""
        self.painter.begin(self)
        self.painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.pen.setWidth(self.divider_visual_width)
        self.painter.setPen(self.pen)

        if self.is_bisected:
            if self.vertical_bisection:  # The screen is cut vertically into left and right
                self.painter.drawLine(round(self.width() * self.division_ratio), 0, round(self.width() * self.division_ratio), self.height())
            else:  # The screen is cut horizontally into top and bottom
                self.painter.drawLine(0, round(self.height() * self.division_ratio), self.width(), round(self.height() * self.division_ratio))
        self.painter.end()
        event.accept()

    def get_divider_position(self):
        """Get pixel distance from divider midline to origin.
        Provided along the relevant axis based on bisection direction"""
        assert self.is_bisected, f"Cannot get divider position for non bisected frame"
        full_edge_size = self.width() if self.vertical_bisection else self.height()
        return round(full_edge_size * self.division_ratio)

    def get_divider_ratio(self, position: QPoint):
        """Get division ratio given a position.
        Provided along the relevant axis based on bisection direction"""
        assert self.is_bisected, f"Cannot get divider position for non bisected frame"
        full_edge_size = self.width() if self.vertical_bisection else self.height()
        distance_along_axis = min(self.width(), max(position.x(), 0)) if self.vertical_bisection else min(self.height(), max(position.y(), 0))

        return distance_along_axis / full_edge_size

    def mousePressEvent(self, event: QMouseEvent):
        """Part of frame bisection logic.
        Starts either resizing an existing divider, or making a new one"""
        self.is_dragging = True
        self.is_dragging_divider = False
        self.started_corner_drag = False

        self.drag_start_position = event.position().toPoint()
        if self.is_bisected: # Are we clicking on the divider?

            if self.vertical_bisection:
                if abs(self.drag_start_position.x() - self.get_divider_position()) <= self.divider_collider_radius and \
                    self.corner_collider_radius < self.drag_start_position.y() < self.height() - self.corner_collider_radius:
                    self.is_dragging_divider = True
            else:
                if abs(self.drag_start_position.y() - self.get_divider_position()) <= self.divider_collider_radius and \
                    self.corner_collider_radius < self.drag_start_position.x() < self.width() - self.corner_collider_radius:
                    self.is_dragging_divider = True


        else: # Did we click near a corner?
            corners = [(0, 0), (0, self.height()), (self.width(), 0), (self.width(), self.height())]
            corner_distances = [((self.drag_start_position.x() - corner[0]) ** 2 +
                                 (self.drag_start_position.y() - corner[1]) ** 2) ** 0.5 for corner in corners]
            if any([corner_distance < self.corner_collider_radius for corner_distance in corner_distances]):
                self.started_corner_drag = True
                self.grabMouse()
        QWidget.mousePressEvent(self, event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Runs on each mouse movement. Updates divider positions,
        creates new dividers, and updates highlights"""
        # is this a hover or drag?
        if self.is_dragging:
            mouse_location = event.position().toPoint()
            drag_distance = ((self.drag_start_position.x() - mouse_location.x()) ** 2 +
                             (self.drag_start_position.y() - mouse_location.y()) ** 2) ** 0.5

            # Handle divider dragging:
            if self.is_dragging_divider:
                assert self.is_bisected, f"Reached divider drag routine without being divided"
                if self.started_corner_drag:  # is this a fresh bisection?
                    # TODO this feels unintuitive. It is hard to intentionally make a thin cut
                    x_distance = min(mouse_location.x(), self.width() - mouse_location.x())
                    y_distance = min(mouse_location.y(), self.height() - mouse_location.y())
                    self.vertical_bisection = x_distance > y_distance

                snap_divider = False
                keep_frame_a = False
                if self.vertical_bisection:
                    if mouse_location.x() < self.divider_collapse_distance:  # Near left edge, get rid of A
                        snap_divider = True
                        keep_frame_a = False
                    elif mouse_location.x() > self.width() - self.divider_collapse_distance:  # Near right edge, get rid of B
                        snap_divider = True
                        keep_frame_a = True
                else:
                    if mouse_location.y() < self.divider_collapse_distance:  # Near top edge, get rid of A
                        snap_divider = True
                        keep_frame_a = False
                    elif mouse_location.y() > self.height() - self.divider_collapse_distance:  # Near bottom edge, get rid of B
                        snap_divider = True
                        keep_frame_a = True

                if snap_divider:
                    self.division_ratio = 1.0 if keep_frame_a else 0.0
                else:
                    self.division_ratio = self.get_divider_ratio(mouse_location)
                self.update_subframe_dimensions()
                self.update()  # Trigger a re-draw to reflect changes

            else: # Try to create the divider
                if self.started_corner_drag and drag_distance >= self.bisection_drag_threshold:
                    self.is_bisected = True
                    self.is_dragging_divider = True
                    # Spawn the subframes
                    self.child_panel.setParent(None) if self.child_panel is not None else None
                    self.child_panel.destroy() if self.child_panel is not None else None
                    self.child_panel = None
                    self.create_subframes()
                    self.update()  # Trigger a re-draw to reflect changes

                # TODO perhaps draw a visual element to show progress towards bisection



        # TODO update highlight decals (hover and click)
        # else:  # Update hover elements
        #     if self.is_bisected:
        #         # Highlight the divider line
        #         raise NotImplementedError
        #     else:
        #         # highlight the relevant corner radius
        #         raise NotImplementedError
        #


        QWidget.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Removes bisections and clears flags"""
        if self.is_bisected and self.division_ratio in [0.0, 1.0]:
            self.is_bisected = False

            self.panel_type = self.subframe_a.panel_type  # Copy back the panel type before destroying it

            self.subframe_a.setParent(None)
            self.subframe_b.setParent(None)

            self.subframe_a.destroy()
            self.subframe_b.destroy()

            self.subframe_a = None
            self.subframe_b = None

            self.create_child_panel()
            self.update_corner_widgets()
            self.show_corner_widgets()
            self.update()

        self.is_dragging = False
        self.started_corner_drag = False
        self.is_dragging_divider = False
        self.releaseMouse()

        QWidget.mouseReleaseEvent(self, event)
