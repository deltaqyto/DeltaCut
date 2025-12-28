from dataclasses import dataclass
import bisect

from PyQt6.QtGui import QImage

from core.application_state import ApplicationState
from core.timeline_objects.generic_timeline_objects import ErrorTimelineObject
from core.timeline_objects.timeline_object import TimelineObject
from core.timeline_objects.timeline_objects_type_registry import TIMELINE_OBJECT_TYPE_REGISTRY


@dataclass
class TimelineEntry:
    start_frame: int
    channel: int
    timeline_object: TimelineObject

    def __lt__(self, other):
        """Comparison for sorting by start_frame"""
        return self.start_frame < other.start_frame


class Timeline:
    def __init__(self, application_state: ApplicationState, serialised_data=None):
        self.application_state = application_state

        # Timeline entries stored as sorted list
        self.timeline: list[TimelineEntry] = []

        if serialised_data is not None:
            self.deserialise_timeline(serialised_data)

    def add_entry(self, start_frame, channel, timeline_object):
        """Add a new entry to the timeline maintaining sorted order"""
        entry = TimelineEntry(start_frame, channel, timeline_object)
        bisect.insort(self.timeline, entry)
        self.application_state.signal_timeline_content_update.emit()

    def get_entries_in_range(self, start_frame, end_frame):
        """Get all entries that are active between start_frame and end_frame"""
        active = []
        for entry in self.timeline:
            entry_end = entry.start_frame + entry.timeline_object.duration

            # Entry is active if it overlaps with the range
            if entry.start_frame < end_frame and entry_end > start_frame:
                active.append(entry)

            # If entry starts after end_frame, no more entries can be active
            if entry.start_frame >= end_frame:
                break

        return active

    def get_next_entry_index(self, from_frame):
        """Get index of the next entry to show on frame (does not consider items that are already visible on the current frame)"""
        dummy = TimelineEntry(from_frame, 0, None)
        return bisect.bisect_left(self.timeline, dummy)

    def serialise_timeline(self):
        """Get serialised representation of timeline and all timeline objects"""

        objects = []
        for entry in self.timeline:
            objects.append({'start_frame': entry.start_frame,
                            'channel': entry.channel,
                            'object': entry.timeline_object.serialise_object()})  # << object serialisation will contain its type

        return {'timeline': {},
                'objects': objects}

    def create_timeline_object_from_serialised(self, object_serialised) -> TimelineObject | None:
        """Create a timeline object from its serialised format.
        Returns none if the object cannot be constructed, or returns the object"""
        assert object_serialised is not None
        timeline_object = TIMELINE_OBJECT_TYPE_REGISTRY.get(object_serialised['object_type'])  # Objects must store their type
        if timeline_object is None:
            return None  # The object type was not registered

        timeline_object = timeline_object(self.application_state, serial_representation=object_serialised)  # Create an instance of the object and allow it to deserialise
        return timeline_object

    def deserialise_timeline(self, serialised_data):
        """Reconstruct timeline entries and settings from serialised data"""
        self.timeline = []
        for timeline_entry in serialised_data.get('objects', []):
            timeline_object = self.create_timeline_object_from_serialised(timeline_entry.get('object')) if 'object' in timeline_entry else None
            if timeline_object is None:
                timeline_object = ErrorTimelineObject(self.application_state, timeline_entry.get('object'))
            self.add_entry(start_frame=timeline_entry.get('start_frame', 0),
                           channel=timeline_entry.get('channel', 0),
                           timeline_object=timeline_object)
        self.application_state.signal_timeline_content_update.emit()

    def get_start(self):
        """Return the first frame something is visible at"""
        return self.timeline[0].start_frame if self.timeline else 0

    def get_duration(self):
        """Get the last frame where an object is visible"""
        max_duration = 0
        for timeline_object in self.timeline:
            max_duration = max(max_duration, timeline_object.start_frame + timeline_object.timeline_object.duration)

        return max_duration

    def check_collision(self, proposed_start: int, proposed_stop: int, proposed_channel: int, ignore_entries: list[TimelineEntry]=None) -> bool:
        """Check if proposed entry collides with any existing entry on the same channel.

        Args:
            proposed_start: Start frame of proposed entry
            proposed_stop: Stop frame of proposed entry
            proposed_channel: Channel number of proposed entry
            ignore_entries: List of entries to ignore within self.timeline. Must be exact references

        Returns:
            True if collision detected, False otherwise
        """
        ignore_entries = [] if ignore_entries is None else ignore_entries

        for entry in self.timeline:
            if entry in ignore_entries:
                continue

            # Early exit: since sorted by start_frame, if this entry starts
            # after our proposed interval ends, no further entries can collide
            if entry.start_frame >= proposed_stop:
                break

            # Skip entries on different channels
            if entry.channel != proposed_channel:
                continue

            # Check interval overlap
            entry_end = entry.start_frame + entry.timeline_object.duration

            # Overlap occurs if: proposed_start < entry_end AND entry_start < proposed_end
            if proposed_start < entry_end:
                return True

        return False

    def move_entry(self, entry: TimelineEntry, new_start_frame: int, new_channel: int):
        """Move an entry maintaining sorted order"""
        assert entry in self.timeline
        self.timeline.remove(entry)
        entry.start_frame = new_start_frame
        entry.channel = new_channel
        bisect.insort(self.timeline, entry)
        self.application_state.signal_timeline_content_update.emit()

    def set_application_state(self, application_state: ApplicationState):
        self.application_state = application_state
        for entry in self.timeline:
            entry.timeline_object.set_application_state(application_state)

    def render_frame(self, frame_number: int, override_visible_entries: list[int]|None = None, frame_buffer: QImage = None) -> QImage:
        """
        Render a target frame. Frame buffer can be passed in. 
        :param frame_number: Frame to render
        :param override_visible_entries: If the visible entries are known ahead of time, pass in a list of indexes to the entries
        :param frame_buffer: QImage of appropriate dimension to be used as frame buffer. Will edit buffer in place if provided
        :return: Frame buffer
        """

        if frame_buffer is None:
            # Create blank frame buffer
            frame_buffer = QImage(self.application_state.rendered_frame.visual_frame)
        frame_buffer.fill(self.application_state.rendered_frame.background_color)

        # First pass: collect visible entries with their channels and relative frames
        if override_visible_entries is None:
            visible_entries = []
            for entry in self.timeline:
                # Early exit optimisation: entries are sorted by start_frame
                if entry.start_frame > frame_number:
                    break

                if entry.timeline_object.can_play_video:
                    relative_frame = frame_number - entry.start_frame
                    if 0 <= relative_frame < entry.timeline_object.duration:
                        visible_entries.append((entry.channel, relative_frame, entry))
        else:
            # Convert list of indexes into visible entry list
            visible_entries = [(self.timeline[entry].channel, frame_number - self.timeline[entry].start_frame, self.timeline[entry]) for entry in override_visible_entries
                               if 0 <= frame_number - self.timeline[entry].start_frame < self.timeline[entry].timeline_object.duration]

        # Sort by channel in ascending order
        visible_entries.sort(key=lambda x: x[0])
        self.application_state.rendered_entries = []

        # Second pass: render entries in channel order
        for channel, relative_frame, entry in visible_entries:
            entry.timeline_object.render_on_frame_buffer(relative_frame, frame_buffer)
            self.application_state.rendered_entries.append(entry)

        return frame_buffer
