from math import floor

from PyQt6.QtCore import QRect, Qt, QPointF, QPoint
from PyQt6.QtGui import QImage, QColor, QFont, QPainter, QPen, QTransform, QBrush, QPolygonF

from core.GUI.themes import ACTIVE_THEME
from core.application_state import ApplicationState


class TimelineObject:
    """Base class for timeline objects in video editing platform.

    Assumptions: Only one timeline, and each object appears once on it. Items are contiguous.

    New timeline object types must be registered in the timeline object registry (core.timeline_objects.timeline_objects_type_registry.py)

    Coordinate system:
    - Duration measured in frames
    - Viewport uses normalised coordinates: width=1, height=1/aspect_ratio
    - Position on timeline managed externally by timeline/generator
    """

    def __init__(self, application_state: ApplicationState, name="Error Object", serial_representation=None, object_resource=None):
        self.application_state = application_state
        self.object_name = name

        self.can_play_video = False  # Will this object be queued for video processing
        self.can_play_audio = False  # Will this object be queued for audio processing

        self.project_frame_rate = application_state.project_settings.playback_codec.frame_rate.get_value()  # Project framerate in fps, set when added to timeline
        self.project_sample_rate = application_state.project_settings.playback_codec.sample_rate.get_value() # Project sample rate in Hz, set when added to timeline

        self.duration = 1  # How long will the object be onscreen for in frames
        self.true_duration = None  # How long can the object actually run for? None = Unlimited. Must be set by the class. Is not serialised.
        self.start_offset = 0  # How many frames to skip at the start of media (eg video/audio)
        self.enabled = True

        self.ui_color = ACTIVE_THEME.error
        self.ui_text_color = ACTIVE_THEME.on_error
        self.ui_is_selected = False

        self.handle_outline = Qt.GlobalColor.gray
        self.handle_fill = Qt.GlobalColor.white
        self.bounding_box_outline = Qt.GlobalColor.white

        self.rotation_handle_length = 30  # px distance from bounding box to rotation handle
        self.rotation_center_handle_size = 8  # px diameter of the rotation center handle

        # None is used to indicate that it should be filled with default values. Set by children as appropriate.
        self.viewport_overlay_bounding_rect: QRect | None = None  # Bounding box of the object. Only set width and height, offset is set in the transform
        self.viewport_transform: QTransform | None = None  # Transform applied to object when rendered to viewport
        self.rotation_center: QPointF | None = None  # Custom center of rotation. Used only when actively rotating the object. Will be set to reasonable value if none in paint_viewport_overlay

        if serial_representation is not None:
            self.deserialise_object(serial_representation)

    def render_on_frame_buffer(self, frame_number, frame_buffer: QImage):
        """Update viewport element for the given frame.

        Called when rendering a new video frame. Directly modifies frame_buffer.

        Args:
            frame_number: Frame index to render (0-based)
            frame_buffer: Image to render onto (QImage)
        """
        assert self.can_play_video  # An object not supporting video was asked for video
        if not self.enabled:
            return
        if frame_number >= self.duration:
            return

        # Subclasses implement viewport element updates here
        # Make sure to use the viewport_transform here
        pass

    def get_audio_samples(self, start_sample, sample_count):
        """Retrieve audio samples for the specified range.

        Args:
            start_sample: Starting sample position (0-based)
            sample_count: Number of samples to retrieve

        Returns:
            Numpy array of audio samples, or None if no audio
        """
        assert self.can_play_audio  # An object not supporting audio was asked for audio
        return None

    def register_properties(self):
        """Define properties that can be edited in the properties panel.

        TODO This component has not been drafted yet.
        """
        raise NotImplementedError

    def serialise_object(self):
        """Generate a dictionary serialisation of the object.
        The serialised format is guaranteed to store the type of the object itself, and is guaranteed to match an entry in the type registry"""
        data = {'object_type': 'BaseTimelineObject', 'duration': self.duration, 'enabled': self.enabled, 'name': self.object_name, 'start_offset': self.start_offset}
        if self.viewport_transform is not None:
            data['viewport_transform'] = [self.viewport_transform.m11(), self.viewport_transform.m12(), self.viewport_transform.m13(),
                                       self.viewport_transform.m21(), self.viewport_transform.m22(), self.viewport_transform.m23(),
                                       self.viewport_transform.m31(), self.viewport_transform.m32(), self.viewport_transform.m33()]
        if self.rotation_center is not None:
            data['rotation_center'] = [self.rotation_center.x(), self.rotation_center.y()]
        if self.viewport_overlay_bounding_rect is not None:
            data['viewport_box'] = [self.viewport_overlay_bounding_rect.width(), self.viewport_overlay_bounding_rect.height()]
        return data

    def deserialise_object(self, serial_representation):
        """Reverse a dictionary serialisation into the object.
        If the object requires a resource, the resource manager must already be set up in the app state"""
        self.duration = serial_representation.get('duration', 1)
        self.start_offset = serial_representation.get('start_offset', 0)
        self.enabled = serial_representation.get('enabled', True)
        self.object_name = serial_representation.get('name', 'Error Object')

        if 'viewport_transform' in serial_representation:
            self.viewport_transform = QTransform(*serial_representation['viewport_transform'])
        if 'rotation_center' in serial_representation:
            self.rotation_center = QPointF(*serial_representation['rotation_center'])
        if 'viewport_box' in serial_representation:
            self.viewport_overlay_bounding_rect = QRect(0, 0, *serial_representation['viewport_box'])

    def attempt_change_object_duration(self, desired_start_offset: int=None, desired_duration: int=None):
        """Try to change the duration and how many frames to skip at the start.
        Will return the actual values that get accepted.
        Attempt to accept the start offset first, then fit duration"""
        if desired_duration is None:
            desired_duration = self.duration
        if desired_start_offset is None:
            desired_start_offset = self.start_offset

        if self.true_duration is None:
            self.start_offset = max(0, desired_start_offset)
            self.duration = max(1, desired_duration)
        else:
            self.start_offset = max(0, min(self.true_duration - 1, desired_start_offset))
            remaining = self.true_duration - self.start_offset
            self.duration = min(remaining, max(1, desired_duration))

        return self.start_offset, self.duration

    def paint_ui_representation(self, painter: QPainter, rect: QRect, active_handle: str | None = None):
        """Render the UI element on the timeline track.

        Args:
            painter: QPainter instance
            rect: QRect to paint within
            active_handle: str or None indicating where to draw highlights
        """
        # Fill with rounded rectangle background
        painter.setBrush(QColor(self.ui_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 4, 4)

        # Draw outline
        outline_color = ACTIVE_THEME.selected_widget if self.ui_is_selected else ACTIVE_THEME.surface
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(outline_color), 1))
        painter.drawRoundedRect(rect, 4, 4)

        # Draw text in top-left
        painter.setPen(QColor(self.ui_text_color))
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)

        # Add padding from edges
        text_rect = rect.adjusted(4, 2, -4, -2)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.object_name)

        # Draw hover highlights
        if active_handle is not None:
            painter.setPen(Qt.PenStyle.NoPen)

            if active_handle == 'left':
                # Draw left handle cap
                handle_width = 4
                handle_rect = QRect(rect.x(), rect.y(), handle_width, rect.height())
                painter.setBrush(QColor(ACTIVE_THEME.on_primary))
                painter.drawRect(handle_rect)

            elif active_handle == 'right':
                # Draw right handle cap
                handle_width = 4
                handle_rect = QRect(rect.x() + rect.width() - handle_width, rect.y(), handle_width, rect.height())
                painter.setBrush(QColor(ACTIVE_THEME.on_primary))
                painter.drawRect(handle_rect)

            elif active_handle == 'top':
                # Darken the body with semi-transparent overlay
                painter.setBrush(QColor(0, 0, 0, 40))
                painter.drawRoundedRect(rect, 4, 4)

    def paint_viewport_overlay(self, painter: QPainter, frame_to_widget: QTransform):
        """Render the element in the video viewport.

        Args:
            painter: QPainter instance
            frame_to_widget: QTransform mapping from canonical frame space to widget space
        """
        # If not visible on viewport, do not render overlays
        if not self.can_play_video:
            return
        # If there is no bounding rectangle or transform, do not render
        if self.viewport_overlay_bounding_rect is None or self.viewport_transform is None:
            return
        if not self.ui_is_selected:
            return

        # Define the rotation center as the center of the object
        if self.rotation_center is None:
            self.rotation_center = QPointF(self.viewport_overlay_bounding_rect.width() / 2, self.viewport_overlay_bounding_rect.height() / 2)

        # Get corner points from bounding rect (origin at 0,0 since offset is in transform)
        rect = self.viewport_overlay_bounding_rect
        corners = [
            QPointF(0, 0),
            QPointF(rect.width(), 0),
            QPointF(rect.width(), rect.height()),
            QPointF(0, rect.height())
        ]

        # Combine transforms: object space -> frame space -> widget space
        complete_transform = self.viewport_transform * frame_to_widget

        # Map corners to widget space
        top_left = complete_transform.map(corners[0])
        top_right = complete_transform.map(corners[1])
        bottom_right = complete_transform.map(corners[2])
        bottom_left = complete_transform.map(corners[3])

        # Calculate midpoint positions
        top_mid = QPointF((top_left.x() + top_right.x()) / 2, (top_left.y() + top_right.y()) / 2)
        right_mid = QPointF((top_right.x() + bottom_right.x()) / 2, (top_right.y() + bottom_right.y()) / 2)
        bottom_mid = QPointF((bottom_right.x() + bottom_left.x()) / 2, (bottom_right.y() + bottom_left.y()) / 2)
        left_mid = QPointF((bottom_left.x() + top_left.x()) / 2, (bottom_left.y() + top_left.y()) / 2)

        # Calculate rotation handle position
        edge_vector = QPointF(top_right.x() - top_left.x(), top_right.y() - top_left.y())
        edge_length = (edge_vector.x() ** 2 + edge_vector.y() ** 2) ** 0.5
        if edge_length > 0:
            edge_vector = QPointF(edge_vector.x() / edge_length, edge_vector.y() / edge_length)
        normal_vector = QPointF(-edge_vector.y(), edge_vector.x())
        rotate_handle = QPointF(top_mid.x() + normal_vector.x() * self.rotation_handle_length, top_mid.y() + normal_vector.y() * self.rotation_handle_length)

        # Draw bounding box
        painter.setPen(QPen(self.bounding_box_outline, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        polygon = QPolygonF([top_left, top_right, bottom_right, bottom_left])
        painter.drawPolygon(polygon)

        # Draw line from top midpoint to rotation handle
        painter.drawLine(top_mid, rotate_handle)

        # Draw handles
        painter.setPen(QPen(self.handle_outline, 1))
        painter.setBrush(QBrush(self.handle_fill))
        circle_radius = 3
        for handle in [top_left, top_right, bottom_right, bottom_left, top_mid, right_mid, bottom_mid, left_mid, rotate_handle]:
            painter.drawEllipse(handle, circle_radius, circle_radius)

        # Draw the rotation center handle
        rotation_center_widget = complete_transform.map(self.rotation_center)
        painter.setPen(QPen(self.handle_fill, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawLine(
            QPointF(rotation_center_widget.x() - self.rotation_center_handle_size, rotation_center_widget.y()),
            QPointF(rotation_center_widget.x() + self.rotation_center_handle_size, rotation_center_widget.y())
        )
        painter.drawLine(
            QPointF(rotation_center_widget.x(), rotation_center_widget.y() - self.rotation_center_handle_size),
            QPointF(rotation_center_widget.x(), rotation_center_widget.y() + self.rotation_center_handle_size)
        )
        painter.drawEllipse(rotation_center_widget, self.rotation_center_handle_size, self.rotation_center_handle_size)

    def check_viewport_mouse_collision(self, mouse_pos: QPointF) -> bool:
        """Determines if the mouse clicked on the object"""
        if self.viewport_overlay_bounding_rect is None or self.viewport_transform is None:
            return False

        inverted_transform, invertible = self.viewport_transform.inverted()
        if not invertible:
            return False

        local_pos = inverted_transform.map(mouse_pos)
        return self.viewport_overlay_bounding_rect.contains(QPoint(floor(local_pos.x()), floor(local_pos.y())))

    def set_application_state(self, application_state: ApplicationState):
        self.application_state = application_state


# WIP long term: implement separate export implementations to focus on speed
