import math
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

        self.handle_size = 5  # px radius of the transform handles
        self.rotation_handle_length = 30  # px distance from bounding box to rotation handle
        self.rotation_center_handle_size = 8  # px radius of the rotation center handle

        # Mouse state variables
        self.handle_locations: list[QPointF] = [QPointF(), QPointF(), QPointF(), QPointF(),  # top left, top right, bottom right, bottom left
                                                QPointF(), QPointF(), QPointF(), QPointF(),  # mid top, right, bottom, left
                                                QPointF()]  # Rotation handle
        self.selected_handle: int | None = None  # Index into the handle location array
        self.handle_start_position: QPointF | None = None  # Location from which the currently selected handle started
        self.drag_start_transform: QTransform = QTransform()  # Transform when the drag event started
        self.drag_anchor: int = 0  # Which handle is considered fixed in place
        self.drag_axis: str = ""  # Which way to drag the handle. Contents depend on drag type
        self.is_dragging_corner: bool = False
        self.is_dragging_edge: bool = False
        self.is_dragging_rotate: bool = False
        self.is_dragging_center: bool = False
        self.is_dragging_transform: bool = False

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

        # Calculate midpoint positions in object space
        top_mid = QPointF(rect.width() / 2, 0)
        right_mid = QPointF(rect.width(), rect.height() / 2)
        bottom_mid = QPointF(rect.width() / 2, rect.height())
        left_mid = QPointF(0, rect.height() / 2)

        # Calculate rotation handle position in object space (extending upward from top edge)
        rotate_handle = QPointF(rect.width() / 2, -self.rotation_handle_length)

        # Store handles in object space
        self.handle_locations = [corners[0], corners[1], corners[2], corners[3], top_mid, right_mid, bottom_mid, left_mid, rotate_handle]

        # Combine transforms: object space -> frame space -> widget space
        complete_transform = self.viewport_transform * frame_to_widget

        # Transform corners to widget space for drawing
        top_left = complete_transform.map(corners[0])
        top_right = complete_transform.map(corners[1])
        bottom_right = complete_transform.map(corners[2])
        bottom_left = complete_transform.map(corners[3])

        # Transform midpoints to widget space for drawing
        top_mid_widget = complete_transform.map(top_mid)
        rotate_handle_widget = complete_transform.map(rotate_handle)

        # Draw bounding box
        painter.setPen(QPen(self.bounding_box_outline, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        polygon = QPolygonF([top_left, top_right, bottom_right, bottom_left])
        painter.drawPolygon(polygon)

        # Draw line from top midpoint to rotation handle
        painter.drawLine(top_mid_widget, rotate_handle_widget)

        # Draw handles
        painter.setPen(QPen(self.handle_outline, 1))
        for i, handle in enumerate(self.handle_locations):
            if i == self.selected_handle:
                painter.setBrush(QBrush(self.handle_outline))
            else:
                painter.setBrush(QBrush(self.handle_fill))
            handle_widget = complete_transform.map(handle)
            painter.drawEllipse(handle_widget, self.handle_size, self.handle_size)

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

    def check_viewport_mouse_collision(self, mouse_pos: QPointF, frame_to_widget: QTransform) -> bool:
        """Determines if the mouse clicked on the object"""
        if self.viewport_overlay_bounding_rect is None or self.viewport_transform is None:
            return False

        inverted_transform, invertible = self.viewport_transform.inverted()
        if not invertible:
            return False

        local_pos = inverted_transform.map(mouse_pos)

        collision = self.viewport_overlay_bounding_rect.contains(QPoint(floor(local_pos.x()), floor(local_pos.y())))
        if collision:
            return True

        # If selected, check the transform handles as well
        if self.ui_is_selected:
            # Convert handle size from window pixels to framebuffer pixels
            origin_widget = frame_to_widget.map(QPointF(0, 0))
            unit_widget = frame_to_widget.map(QPointF(1, 0))
            scale = ((unit_widget.x() - origin_widget.x()) ** 2 + (unit_widget.y() - origin_widget.y()) ** 2) ** 0.5
            handle_size_fb = self.handle_size / scale

            # Check handles in framebuffer space
            for i, handle_local in enumerate(self.handle_locations):
                handle_fb = self.viewport_transform.map(handle_local)
                distance = ((handle_fb.x() - mouse_pos.x()) ** 2 + (handle_fb.y() - mouse_pos.y()) ** 2) ** 0.5
                if distance < handle_size_fb:
                    return True

            rotation_center = self.viewport_transform.map(self.rotation_center)
            distance = ((rotation_center.x() - mouse_pos.x()) ** 2 + (rotation_center.y() - mouse_pos.y()) ** 2) ** 0.5
            if distance < self.rotation_center_handle_size / scale:
                return True

        return False

    def set_application_state(self, application_state: ApplicationState):
        self.application_state = application_state

    def viewport_mouse_press(self, mouse_pos: QPointF, frame_to_widget: QTransform) -> bool:
        """Returns if an update is required for the viewport frame"""
        need_update = False

        self.is_dragging_corner = False
        self.is_dragging_edge = False
        self.is_dragging_rotate = False
        self.is_dragging_center = False
        self.is_dragging_transform = False
        self.drag_start_transform = self.viewport_transform

        last_selected_handle = self.selected_handle
        self.selected_handle = None
        # Convert handle size from window pixels to framebuffer pixels
        origin_widget = frame_to_widget.map(QPointF(0, 0))
        unit_widget = frame_to_widget.map(QPointF(1, 0))
        scale = ((unit_widget.x() - origin_widget.x()) ** 2 + (unit_widget.y() - origin_widget.y()) ** 2) ** 0.5
        handle_size_fb = self.handle_size / scale

        # Check handles in framebuffer space
        for i, handle_local in enumerate(self.handle_locations):
            handle_fb = self.viewport_transform.map(handle_local)
            distance = ((handle_fb.x() - mouse_pos.x()) ** 2 + (handle_fb.y() - mouse_pos.y()) ** 2) ** 0.5
            if distance < handle_size_fb:
                self.selected_handle = i
                break  # Priority given to corners when overlapping
        if last_selected_handle != self.selected_handle:
            need_update = True

        rotation_center_collision = False
        if self.rotation_center is not None:
            rotation_center_fb = self.viewport_transform.map(self.rotation_center)
            rotation_center_handle_size_fb = self.rotation_center_handle_size / scale
            distance_to_center = ((rotation_center_fb.x() - mouse_pos.x()) ** 2 + (rotation_center_fb.y() - mouse_pos.y()) ** 2) ** 0.5
            if distance_to_center < rotation_center_handle_size_fb:
                rotation_center_collision = True

        if self.selected_handle in [0, 1, 2, 3]:  # Corner handle
            self.is_dragging_corner = True
            self.handle_start_position = self.handle_locations[self.selected_handle]
            self.drag_anchor = {0: 2, 1: 3, 2: 0, 3: 1}[self.selected_handle]  # Diagonally opposite handle is the anchor
            self.drag_axis = ""  # Unnecessary for this task
        elif self.selected_handle in [4, 5, 6, 7]:  # Edge handle
            self.is_dragging_edge = True
            self.handle_start_position = self.handle_locations[self.selected_handle]
            self.drag_anchor = {4: 6, 5: 7, 6: 4, 7: 5}[self.selected_handle]  # Directly opposite handle is the anchor
            self.drag_axis = {4: 'y', 5: 'x', 6: 'y', 7: 'x'}[self.selected_handle]
        elif self.selected_handle == 8:  # Rotation handle
            self.is_dragging_rotate = True
            self.handle_start_position = self.handle_locations[self.selected_handle]
        elif rotation_center_collision:  # Rotation center
            self.is_dragging_center = True
        else:  # Translation
            self.is_dragging_transform = True
            self.handle_start_position = mouse_pos  # Store the mouse position to compute the offset later

        return need_update

    def viewport_mouse_move(self, mouse_pos: QPointF, frame_to_widget: QTransform) -> tuple[bool, bool]:
        """Returns if an update is required for the viewport frame, if a re-render of the framebuffer is required"""
        if self.is_dragging_corner:
            self.viewport_transform = self.compute_corner_transform(mouse_pos, self.drag_start_transform, self.handle_start_position)
            return True, True
        elif self.is_dragging_edge:
            self.viewport_transform = self.compute_edge_transform(mouse_pos, self.drag_start_transform, self.handle_start_position)
            return True, True
        elif self.is_dragging_rotate:
            self.viewport_transform = self.compute_rotation_transform(mouse_pos, self.drag_start_transform, self.handle_start_position)
            return True, True
        elif self.is_dragging_center:
            # Transform mouse position from framebuffer to object space
            inverted, invertible = self.drag_start_transform.inverted()
            if invertible:
                self.rotation_center = inverted.map(mouse_pos)
            return True, True
        elif self.is_dragging_transform:
            self.viewport_transform = self.compute_translation_transform(mouse_pos, self.drag_start_transform, self.handle_start_position)
            return True, True

        # Check for hover updates
        need_update = False
        last_selected_handle = self.selected_handle
        self.selected_handle = None
        # Convert handle size from window pixels to framebuffer pixels
        origin_widget = frame_to_widget.map(QPointF(0, 0))
        unit_widget = frame_to_widget.map(QPointF(1, 0))
        scale = ((unit_widget.x() - origin_widget.x()) ** 2 + (unit_widget.y() - origin_widget.y()) ** 2) ** 0.5
        handle_size_fb = self.handle_size / scale

        # Check handles in framebuffer space
        for i, handle_local in enumerate(self.handle_locations):
            handle_fb = self.viewport_transform.map(handle_local)
            distance = ((handle_fb.x() - mouse_pos.x()) ** 2 + (handle_fb.y() - mouse_pos.y()) ** 2) ** 0.5
            if distance < handle_size_fb:
                self.selected_handle = i
                break
        if last_selected_handle != self.selected_handle:
            need_update = True

        return need_update, False

    def viewport_mouse_release(self, mouse_pos: QPointF) -> bool:
        """Returns if an update is required for the viewport frame"""
        self.is_dragging_corner = False
        self.is_dragging_edge = False
        self.is_dragging_rotate = False
        self.is_dragging_center = False
        self.is_dragging_transform = False
        return False

    def compute_corner_transform(self, mouse_framebuffer_pos: QPointF, drag_start_transform: QTransform, handle_start_position: QPointF) -> QTransform:
        """Compute new transform when dragging a corner handle.

        Scales the object around the anchor corner (diagonally opposite to dragged corner).
        The anchor remains fixed in framebuffer space whilst the dragged corner follows the mouse.
        """
        # Get positions in object space
        anchor_obj = self.handle_locations[self.drag_anchor]
        handle_obj = handle_start_position

        # Transform mouse position from framebuffer to object space
        inverted, invertible = drag_start_transform.inverted()
        if not invertible:
            return self.viewport_transform

        mouse_obj = inverted.map(mouse_framebuffer_pos)

        # Compute deltas in object space
        delta_original = QPointF(handle_obj.x() - anchor_obj.x(), handle_obj.y() - anchor_obj.y())
        delta_target = QPointF(mouse_obj.x() - anchor_obj.x(), mouse_obj.y() - anchor_obj.y())

        # Check for degenerate cases
        if abs(delta_original.x()) < 0.001 or abs(delta_original.y()) < 0.001:
            return self.viewport_transform
        if abs(delta_target.x()) < 0.001 or abs(delta_target.y()) < 0.001:
            return self.viewport_transform

        # Compute scale factors
        sx = delta_target.x() / delta_original.x()
        sy = delta_target.y() / delta_original.y()

        # Build local scale transform centred at anchor in object space
        local_scale = QTransform()
        local_scale.translate(anchor_obj.x(), anchor_obj.y())
        local_scale.scale(sx, sy)
        local_scale.translate(-anchor_obj.x(), -anchor_obj.y())

        # Compose with existing transform
        return local_scale * drag_start_transform

    def compute_edge_transform(self, mouse_framebuffer_pos: QPointF, drag_start_transform: QTransform, handle_start_position: QPointF) -> QTransform:
        """Compute new transform when dragging an edge handle.

        Scales the object perpendicular to the anchor edge (opposite edge).
        The anchor edge remains fixed in framebuffer space whilst the dragged edge follows the mouse.
        """
        # Get positions in object space
        anchor_obj = self.handle_locations[self.drag_anchor]
        handle_obj = handle_start_position

        # Transform mouse position from framebuffer to object space
        inverted, invertible = drag_start_transform.inverted()
        if not invertible:
            return self.viewport_transform

        mouse_obj = inverted.map(mouse_framebuffer_pos)

        # Compute deltas in object space
        delta_original = QPointF(handle_obj.x() - anchor_obj.x(), handle_obj.y() - anchor_obj.y())
        delta_target = QPointF(mouse_obj.x() - anchor_obj.x(), mouse_obj.y() - anchor_obj.y())

        # Determine scaling axis and compute scale factor
        if self.drag_axis == 'y':
            if abs(delta_original.y()) < 0.001:
                return self.viewport_transform
            if abs(delta_target.y()) < 0.001:
                return self.viewport_transform

            sx = 1.0  # Preserve X scale
            sy = delta_target.y() / delta_original.y()
        else:  # 'x'
            if abs(delta_original.x()) < 0.001:
                return self.viewport_transform
            if abs(delta_target.x()) < 0.001:
                return self.viewport_transform

            sx = delta_target.x() / delta_original.x()
            sy = 1.0  # Preserve Y scale

        # Build local scale transform centred at anchor in object space
        local_scale = QTransform()
        local_scale.translate(anchor_obj.x(), anchor_obj.y())
        local_scale.scale(sx, sy)
        local_scale.translate(-anchor_obj.x(), -anchor_obj.y())

        # Compose with existing transform
        return local_scale * drag_start_transform

    def compute_rotation_transform(self, mouse_framebuffer_pos: QPointF, drag_start_transform: QTransform, handle_start_position: QPointF) -> QTransform:
        """Compute new transform when dragging the rotation handle.

        Rotates the object around self.rotation_center (in object space).
        If rotation_center is None, returns the current transform unchanged.
        The rotation is applied incrementally in framebuffer space, preserving
        the existing scale and position whilst only modifying rotation.
        """
        # Check if rotation centre is set
        if self.rotation_center is None:
            return self.viewport_transform

        # Map rotation centre to framebuffer space (this point remains fixed)
        center_fb = drag_start_transform.map(self.rotation_center)

        # Map handle start position to framebuffer space
        handle_fb_start = drag_start_transform.map(handle_start_position)

        # Calculate vectors from centre to handle start and to mouse
        dx_start = handle_fb_start.x() - center_fb.x()
        dy_start = handle_fb_start.y() - center_fb.y()

        dx_current = mouse_framebuffer_pos.x() - center_fb.x()
        dy_current = mouse_framebuffer_pos.y() - center_fb.y()

        # Check for degenerate case: mouse too close to rotation centre
        dist_start = (dx_start ** 2 + dy_start ** 2) ** 0.5
        dist_current = (dx_current ** 2 + dy_current ** 2) ** 0.5

        if dist_start < 1.0 or dist_current < 1.0:
            return self.viewport_transform

        # Calculate angles
        angle_start = math.atan2(dy_start, dx_start)
        angle_current = math.atan2(dy_current, dx_current)

        # Compute incremental rotation angle
        rotation_angle = angle_current - angle_start
        rotation_degrees = math.degrees(rotation_angle)

        # Create a rotation transform in framebuffer space around the rotation centre
        rotation_transform = QTransform()
        rotation_transform.translate(center_fb.x(), center_fb.y())
        rotation_transform.rotate(rotation_degrees)
        rotation_transform.translate(-center_fb.x(), -center_fb.y())

        return drag_start_transform * rotation_transform

    def compute_translation_transform(self, mouse_framebuffer_pos: QPointF, drag_start_transform: QTransform, handle_start_position: QPointF) -> QTransform:
        """Compute new transform when dragging the object (no handle selected).

        Translates the entire object in framebuffer space. The translation delta is computed
        between the current mouse position and the drag start position, then applied to
        preserve the object's scale and rotation whilst shifting its position.
        """
        # Calculate translation delta in framebuffer space
        dx = mouse_framebuffer_pos.x() - handle_start_position.x()
        dy = mouse_framebuffer_pos.y() - handle_start_position.y()

        # Create translation transform in framebuffer space
        translation = QTransform()
        translation.translate(dx, dy)

        return drag_start_transform * translation

# WIP long term: implement separate export implementations to focus on speed
