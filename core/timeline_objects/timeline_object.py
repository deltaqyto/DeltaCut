from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QImage, QColor, QFont, QPainter, QPen

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
        return {'object_type': 'BaseTimelineObject', 'duration': self.duration, 'enabled': self.enabled, 'name': self.object_name, 'start_offset': self.start_offset}

    def deserialise_object(self, serial_representation):
        """Reverse a dictionary serialisation into the object.
        If the object requires a resource, the resource manager must already be set up in the app state"""
        self.duration = serial_representation.get('duration', 1)
        self.start_offset = serial_representation.get('start_offset', 0)
        self.enabled = serial_representation.get('enabled', True)
        self.object_name = serial_representation.get('name', 'Error Object')

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

    def paint_ui_representation(self, painter: QPainter, rect: QRect):
        """Render the UI element on the timeline track.

        Args:
            painter: QPainter instance
            rect: QRect to paint within
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

    def paint_viewport_overlay(self, painter, widget):
        """Render the element in the video viewport.

        Args:
            painter: QPainter instance
            widget: QWidget being painted on
        """
        raise NotImplementedError

    def get_viewport_bounding_rect(self):
        """Return the bounding rectangle in normalised viewport coordinates.

        Returns:
            QRectF in normalised space (width=1, height=1/aspect_ratio)
        """
        raise NotImplementedError

    def set_application_state(self, application_state: ApplicationState):
        self.application_state = application_state


# WIP long term: implement separate export implementations to focus on speed
