from PyQt6.QtGui import QImage, QPainter, QTransform
from PyQt6.QtCore import QRectF, QRect

from core.GUI.themes import ACTIVE_THEME
from core.application_state import ApplicationState
from core.resources.image_resource import ImageResource, ImageReadHead
from core.timeline_objects.timeline_object import TimelineObject


class ImageMediaTimelineObject(TimelineObject):
    """Timeline object for image media display.

    Displays a static image for a specified duration.
    Scales image to fit frame while preserving aspect ratio.
    Safely handles None resources by skipping rendering.

    Args:
        object_resource: ImageResource instance or None
        duration: Number of frames to display the image
    """

    def __init__(self, application_state: ApplicationState,  name="Unnamed Image", serial_representation=None, object_resource=None, duration=60):
        super().__init__(application_state, name, serial_representation, object_resource=object_resource)
        self.can_play_audio = False
        self.can_play_video = True

        self.ui_color = ACTIVE_THEME.object_image_ui
        #self.ui_text_color = ???

        self.read_head: ImageReadHead | None = None
        self.object_resource: ImageResource | None = object_resource

        if serial_representation is None:
            self.duration = duration
        else:
            self.deserialise_object(serial_representation)

        assert self.duration >= 1, f"Duration must be at least 1 frame, got {self.duration}"

        if self.object_resource is not None:
            self.set_object_resource(self.object_resource)

    def set_object_resource(self, object_resource):
        """Change or clear the image resource.

        Args:
            object_resource: ImageResource instance or None
        """
        if object_resource is None:
            self.read_head = None
            self.object_resource = None
            self.viewport_overlay_bounding_rect = None
            self.viewport_transform = None
        else:
            self.object_resource = object_resource
            self.read_head = object_resource.get_video_read_head()

            # Infer bounding rect from image dimensions
            rgba_data = self.read_head.read()
            height, width = rgba_data.shape[:2]

            if self.viewport_overlay_bounding_rect is None:
                self.viewport_overlay_bounding_rect = QRect(0, 0, width, height)
            if self.viewport_transform is None:
                # Calculate scaling to fit while preserving aspect ratio
                frame_width = self.application_state.rendered_frame.visual_frame.width()
                frame_height = self.application_state.rendered_frame.visual_frame.height()

                width_scale = frame_width / width
                height_scale = frame_height / height
                scale = min(width_scale, height_scale)

                scaled_width = width * scale
                scaled_height = height * scale

                # Centre the image
                x_offset = (frame_width - scaled_width) / 2
                y_offset = (frame_height - scaled_height) / 2

                self.viewport_transform = QTransform()
                self.viewport_transform.translate(x_offset, y_offset)
                self.viewport_transform.scale(scale, scale)

    def render_on_frame_buffer(self, frame_number, frame_buffer):
        """Update viewport element for the given frame.

        Draws the image scaled to fit the frame buffer while preserving aspect ratio.

        Args:
            frame_number: Frame index to render (0-based)
            frame_buffer: QImage to draw onto
        """
        if self.read_head is None or not self.enabled:
            return
        assert 0 <= frame_number < self.duration, f'Image frame out of range (0, {self.duration}), got {frame_number}'

        # Read single RGBA frame (height, width, 4)
        rgba_data = self.read_head.read()

        # Convert numpy array to QImage
        height, width = rgba_data.shape[:2]
        bytes_per_line = width * 4
        qimage = QImage(rgba_data.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888)

        painter = QPainter(frame_buffer)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setTransform(self.viewport_transform)
        source_rect = QRectF(0, 0, width, height)
        painter.drawImage(source_rect, qimage, source_rect)
        painter.end()

    def serialise_object(self):
        serial = {
            'object_type': 'ImageMediaTimelineObject'
        }
        if self.object_resource is not None:
            serial['resource_id'] = self.object_resource.resource_id
        serialised_data = super().serialise_object()
        serialised_data.update(serial)
        return serialised_data

    def deserialise_object(self, serial_representation):
        super().deserialise_object(serial_representation)
        self.set_object_resource(self.application_state.resource_manager.get_resource_by_resource_id(serial_representation.get('resource_id')) if 'resource_id' in serial_representation else None)
