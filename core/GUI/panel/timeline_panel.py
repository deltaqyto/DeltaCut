from math import ceil, floor
from time import time

from PyQt6.QtCore import QRect, QLineF, QPointF, QPoint, pyqtSlot
from PyQt6.QtGui import QPaintEvent, QPainter, QColor, QResizeEvent, QMouseEvent

from core.GUI.panel.base_panel import BasePanel
from core.GUI.themes import ACTIVE_THEME
from core.project.project import Project
from core.timeline import TimelineEntry


class TimelinePanel(BasePanel):
    """The timeline panel shows the timeline and manages modifications to it."""

    def __init__(self, parent, project: Project):
        super().__init__(parent, project)

        self.panel_type: str = 'TimelinePanel'
        self.project: Project = project
        self.project.application_state.signal_timeline_content_update.connect(self.handle_timeline_content_update)
        self.project.application_state.signal_timeline_lock_update.connect(self.handle_timeline_lock_update)
        self.project.application_state.signal_frame_number_update.connect(self.handle_frame_number_update)

        self.channel_height: int = 40  # px height of each channel
        self.channel_padding: int = 2  # px padding, applied on either side of the timeline object

        self.minimum_drag_distance: int = 10  # px of drag distance required to unlock drag handle

        self.object_side_handle_width: int = 20  # px region which is considered to be in range of the left/right handles
        self.playhead_collider_width: int = 10  # px size which is considered to be in range of the playhead line
        self.maximum_playhead_drag_update_period: float = 1/10  # Minimum time to wait between triggering updates to the frame_number

        # Mouse handling controls
        self.drag_start_position: QPointF = QPointF()
        self.is_dragging: bool = False
        self.is_dragging_unlocked: bool = False
        self.is_dragging_playhead: bool = False
        self.selected_timeline_entry: TimelineEntry|None = None
        self.selected_entry_handle: str = ''  # top, left, right
        self.selected_entry_frame_offset: int = 0  # px of x offset from start of timeline object to mouse position
        self.drag_pixels_per_frame: float = 0  # Pixels per frame, locked to when a drag starts
        self.last_frame_update_time: float = 0  # Seconds since the last update to the frame number, from dragging the playhead
        self.old_stop_frame: int = 0  # Frame number of the object end. Used for left handle adjustment

        self.viewport_left: int = 0  # First visible frame
        self.viewport_right: int = 0  # Last visible frame
        self.current_frame_number: int = 0  # Frame that is currently rendered on screen

        self.visible_objects: list[TimelineEntry] = []
        self.timeline_object_rects: list[QRect] = []  # Bounding boxes, matches 1:1 with self.visible objects
        self.handle_timeline_content_update()

    @pyqtSlot()
    def handle_timeline_content_update(self):
        """Called when the timeline contents are updated"""
        self.viewport_left = self.project.timeline.get_start()
        self.viewport_right = self.project.timeline.get_duration()
        self.visible_objects = self.project.timeline.get_entries_in_range(self.viewport_left, self.viewport_right)
        self.update_timeline_object_rects()
        self.update()

    @pyqtSlot()
    def handle_timeline_lock_update(self):
        """Called when the timeline lock is set (or released)"""
        self.stop_mouse_action()
        self.update()
        
    @pyqtSlot()
    def handle_frame_number_update(self):
        """Called when the currently visible frame number has been changed"""
        self.current_frame_number = self.project.application_state.current_playback_frame
        self.update()

    def update_timeline_object_rects(self):
        self.timeline_object_rects = []

        pixels_per_frame = self.get_pixels_per_frame()
        
        for timeline_entry in self.visible_objects:
            entry_start = timeline_entry.start_frame
            entry_duration = timeline_entry.timeline_object.duration
            entry_channel = timeline_entry.channel

            # Calculate rectangle for this entry
            x = int((entry_start - self.viewport_left) * pixels_per_frame)
            y = entry_channel * self.channel_height + self.channel_padding
            width = int(entry_duration * pixels_per_frame)
            height = self.channel_height - self.channel_padding * 2

            self.timeline_object_rects.append(QRect(x, y, width, height))


    def paintEvent(self, event: QPaintEvent):
        """Draw the timeline background, and all timeline elements that are visible"""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background
        painter.fillRect(self.rect(), QColor(ACTIVE_THEME.background))

        # Draw dividers
        painter.setPen(QColor(ACTIVE_THEME.surface))
        for channel in range(ceil(self.height() / self.channel_height)):
            painter.drawLine(QLineF(0, channel * self.channel_height, self.width(), channel * self.channel_height))

        # Draw all visible timeline entries
        assert len(self.visible_objects) == len(self.timeline_object_rects), \
            f"Timeline Panel: Visible object and rectangle lists out of sync. Entries: {len(self.visible_objects)}, rects: {len(self.timeline_object_rects)}"
        for timeline_entry, entry_rect in zip(self.visible_objects, self.timeline_object_rects):
            # Delegate drawing to the timeline object's UI element
            timeline_entry.timeline_object.paint_ui_representation(painter, entry_rect)

        playhead_is_onscreen, playhead_x = self.map_frame_to_pixel(self.current_frame_number)
        if playhead_is_onscreen:
            painter.setPen(QColor(ACTIVE_THEME.primary))
            painter.drawLine(QLineF(playhead_x, 0, playhead_x, self.height()))

    def resizeEvent(self, event:QResizeEvent):
        """Refresh the timeline rectangle cache"""
        self.update_timeline_object_rects()

    def mousePressEvent(self, event: QMouseEvent):
        mouse_position: QPoint = QPoint(floor(event.position().x()), floor(event.position().y()))
        pixels_per_frame = self.get_pixels_per_frame()
        self.drag_start_position = event.position()
        self.is_dragging = True
        self.is_dragging_unlocked = False
        self.drag_pixels_per_frame = pixels_per_frame

        assert len(self.visible_objects) == len(self.timeline_object_rects), \
            f"Timeline Panel: Visible object and rectangle lists out of sync. Entries: {len(self.visible_objects)}, rects: {len(self.timeline_object_rects)}"

        # Check for drag on play head
        playhead_is_onscreen, playhead_x = self.map_frame_to_pixel(self.current_frame_number)
        if playhead_is_onscreen and abs(mouse_position.x() - playhead_x) < self.playhead_collider_width:
            self.is_dragging_playhead = True
            return  # Skip checks on timeline objects

        for entry, rect in zip(self.visible_objects, self.timeline_object_rects):
            if not rect.contains(mouse_position):
                entry.timeline_object.ui_is_selected = False
                continue
            if self.selected_timeline_entry is not None:
                self.selected_timeline_entry.timeline_object.ui_is_selected = False

            self.selected_timeline_entry = entry
            self.selected_timeline_entry.timeline_object.ui_is_selected = True
            if rect.x() + rect.width() - mouse_position.x() < self.object_side_handle_width:
                self.selected_entry_handle = 'right'
            elif mouse_position.x() - rect.x() < self.object_side_handle_width:
                self.selected_entry_handle = 'left'
                self.old_stop_frame = self.selected_timeline_entry.start_frame + self.selected_timeline_entry.timeline_object.duration
            else:
                self.selected_entry_handle = 'top'
                self.selected_entry_frame_offset = floor(mouse_position.x() / pixels_per_frame) - entry.start_frame
            self.project.application_state.signal_timeline_content_update.emit()  # Inform other timeline panels that the selection status changed
            break
        event.ignore()

    def mouseMoveEvent(self, event:QMouseEvent):
        if self.project.application_state.is_timeline_locked:
            return

        # Handle playhead movement
        if self.is_dragging_playhead:
            assert self.is_dragging, f"Timeline Panel: Dragging playhead without being in dragging state"
            self.current_frame_number = self.map_pixel_to_frame(event.position().x())
            if time() - self.last_frame_update_time > self.maximum_playhead_drag_update_period:
                frame_buffer = self.project.timeline.render_frame(self.current_frame_number)
                self.project.application_state.current_playback_frame = self.current_frame_number
                self.project.application_state.signal_frame_number_update.emit()
                self.project.application_state.rendered_frame.visual_frame = frame_buffer
                self.project.application_state.signal_frame_buffer_update.emit()
                self.last_frame_update_time = time()
            else:
                self.update()  # Update the timeline pointer to improve apparent smoothness
            return

        if self.is_dragging and not self.is_dragging_unlocked:
            drag_distance = ((event.position().x() - self.drag_start_position.x())**2 + (event.position().y() - self.drag_start_position.y())**2)**0.5
            if drag_distance > self.minimum_drag_distance:
                self.is_dragging_unlocked = True

        if self.is_dragging_unlocked:
            assert self.is_dragging, f"Timeline Panel: Dragging unlocked without being in dragging state"
            if self.selected_entry_handle == "" or self.project.application_state.is_timeline_locked:
                return

            mouse_frame_position = floor(event.position().x() / self.drag_pixels_per_frame)
            # Do we have a handle active? Work out the new channel, start and end frames of the object
            if self.selected_entry_handle == 'top':
                new_channel = floor(event.position().y() / self.channel_height)
                new_start = mouse_frame_position - self.selected_entry_frame_offset
                new_stop = new_start + self.selected_timeline_entry.timeline_object.duration
            elif self.selected_entry_handle == 'left':
                new_channel = self.selected_timeline_entry.channel
                new_start = mouse_frame_position
                new_stop = new_start + self.selected_timeline_entry.timeline_object.duration
            elif self.selected_entry_handle == 'right':
                new_channel = self.selected_timeline_entry.channel
                new_start = self.selected_timeline_entry.start_frame
                new_stop = mouse_frame_position
            else:
                raise AssertionError(f"Timeline Panel: selected entry handle has unknown name: {self.selected_entry_handle}")

            if not self.project.timeline.check_collision(new_start, new_stop, new_channel, ignore_entries=[self.selected_timeline_entry]):
                # Change the shape of the media to this new shape

                if self.selected_entry_handle == 'top':  # Move the entry without changing its start offset
                    self.project.timeline.move_entry(self.selected_timeline_entry, new_start, new_channel)
                elif self.selected_entry_handle == 'left':  # Move the entry's start offset only
                    current_start_offset = self.selected_timeline_entry.timeline_object.start_offset
                    start_frame_change = new_start - self.selected_timeline_entry.start_frame
                    # Shorten the entry by n frames from the start
                    self.selected_timeline_entry.timeline_object.attempt_change_object_duration(desired_start_offset=current_start_offset + start_frame_change,
                                                                                                desired_duration=self.selected_timeline_entry.timeline_object.duration - start_frame_change)
                    # Offset it equally to make it appear it got shortened from the start
                    self.project.timeline.move_entry(self.selected_timeline_entry, new_start, new_channel)
                elif self.selected_entry_handle == 'right':  # Adjust the entry's duration only
                    self.selected_timeline_entry.timeline_object.attempt_change_object_duration(desired_duration=new_stop - new_start)
                    self.selected_timeline_entry.channel = new_channel
                    self.project.application_state.signal_timeline_content_update.emit()  # Other two paths call this implicitly via timeline.move_entry
        event.ignore()

    def mouseReleaseEvent(self, event:QMouseEvent):
        if self.is_dragging_playhead:  # Commit last playback head position
            self.project.application_state.current_playback_frame = self.current_frame_number
            self.project.application_state.signal_frame_number_update.emit()
        self.stop_mouse_action()
        event.ignore()

    def get_pixels_per_frame(self):
        # Calculate frame to pixel conversion
        frame_range = self.viewport_right - self.viewport_left
        if frame_range == 0:
            return 1

        assert frame_range > 0
        return self.width() / frame_range

    def stop_mouse_action(self):
        """Reset mouse handling state"""
        self.is_dragging = False
        self.is_dragging_unlocked = False
        self.is_dragging_playhead = False
        self.selected_entry_handle = ''

    def map_frame_to_pixel(self, frame_number, pixels_per_frame=None) -> tuple[bool, int]:
        """Compute the pixel offset of a timeline frame on the panel's x axis
        Supports override of the pixels per frame constant
        Returns tuple(is this visible on screen, x pixel coordinate)
        """
        if pixels_per_frame is None:
            pixels_per_frame = self.get_pixels_per_frame()
        frame_pixel = pixels_per_frame * (frame_number - self.viewport_left)

        if frame_number < self.viewport_left or frame_number > self.viewport_right:
            return False, frame_pixel  # Off-screen
        return True, frame_pixel

    def map_pixel_to_frame(self, pixel_number, pixels_per_frame=None) -> int:
        """Compute the frame number on the timeline for a given pixel x
        Supports override of the pixels per frame constant
        """

        if pixels_per_frame is None:
            pixels_per_frame = self.get_pixels_per_frame()

        frame_number = self.viewport_left + pixel_number / pixels_per_frame
        return frame_number
