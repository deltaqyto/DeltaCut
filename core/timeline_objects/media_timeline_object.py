from math import ceil, floor
import numpy as np

from core.GUI.themes import ACTIVE_THEME
from core.application_state import ApplicationState
from core.resources.audio_resource import AudioResource, AudioReadHead
from core.timeline_objects.timeline_object import TimelineObject


class AudioMediaTimelineObject(TimelineObject):
    """Timeline object for audio media playback.

    Manages audio resources with sub-frame positioning via sample_offset.
    Safely handles None resources by returning silence.

    Args:
        object_resource: AudioResource instance or None
        sample_offset: Sub-frame sample offset in range [0, samples_per_frame)
    """

    def __init__(self, application_state: ApplicationState, name="Unnamed Audio", serial_representation=None, object_resource=None, sample_offset=0, duration=None):
        super().__init__(application_state, name, serial_representation, object_resource=object_resource)
        self.can_play_audio = True
        self.can_play_video = False

        self.ui_color=ACTIVE_THEME.object_audio_ui
        #self.ui_text_color = ???

        self.read_head: AudioReadHead|None = None
        self.object_resource: AudioResource|None = object_resource

        if serial_representation is None:
            self.sample_offset = sample_offset
            self.n_channels = 1
        else:
            self.deserialise_object(serial_representation)

        assert self.sample_offset >= 0, f"sample_offset must be non-negative, got {self.sample_offset}"
        assert self.n_channels >= 1, f"n_channels must be non-negative, got {self.n_channels}"

        if self.object_resource is not None:
            self.set_audio_resource(self.object_resource)

        if duration is None:
            self.attempt_change_object_duration(desired_duration=self.true_duration)
        else:
            self.attempt_change_object_duration(desired_duration=duration if duration >= 1 else self.true_duration)

    def set_audio_resource(self, object_resource: AudioResource|None):
        """Change or clear the audio resource.

        Args:
            object_resource: AudioResource instance or None
        """
        if object_resource is None:
            self.read_head = None
            self.true_duration = None  # Do not limit the size of the audio object if no resource is set
            self.n_channels = 1
            self.object_resource = None
        else:
            self.object_resource = object_resource
            self.read_head = object_resource.get_audio_read_head()
            self.n_channels = object_resource.n_channels

            # Calculate duration from audio length
            assert self.project_frame_rate is not None and self.project_sample_rate is not None

            samples_per_frame = self.project_sample_rate / self.project_frame_rate
            self.true_duration = ceil(object_resource.n_samples / samples_per_frame)
            self.attempt_change_object_duration(self.start_offset, self.duration) # Reconcile offset and duration in case true duration changed

    def _generate_silence(self, sample_count):
        """Generate silence array matching resource channel configuration.

        Args:
            sample_count: Number of samples to generate

        Returns:
            Numpy array of zeros with shape (n_channels, sample_count)
        """
        return np.zeros((self.n_channels, sample_count), dtype=np.float32)

    def get_audio_samples(self, start_sample, sample_count):
        """Retrieve audio samples for the specified range.

        Args:
            start_sample: Starting sample position (0-based)
            sample_count: Number of samples to retrieve

        Returns:
            Numpy array of audio samples with shape (n_channels, sample_count)
        """
        if self.read_head is None:
            return self._generate_silence(sample_count)

        adjusted_start = start_sample + self.sample_offset + floor(self.start_offset / self.project_frame_rate * self.project_sample_rate)

        if adjusted_start >= self.object_resource.n_samples:
            return self._generate_silence(sample_count)

        available_samples = self.object_resource.n_samples - adjusted_start
        if sample_count > available_samples:
            audio_data = self.read_head.read(adjusted_start, available_samples)
            padding = self._generate_silence(sample_count - available_samples)
            return np.concatenate([audio_data, padding], axis=1)

        return self.read_head.read(adjusted_start, sample_count)

    def serialise_object(self):
        serial = {
            'object_type': 'AudioMediaTimelineObject',
            'sample_offset': self.sample_offset,
            'channels': self.n_channels
        }
        if self.object_resource is not None:
            serial['resource_id'] = self.object_resource.resource_id
        serialised_data = super().serialise_object()
        serialised_data.update(serial)
        return serialised_data


    def deserialise_object(self, serial_representation):
        super().deserialise_object(serial_representation)
        self.sample_offset = serial_representation.get('sample_offset', 0)
        self.n_channels = serial_representation.get('channels', 1)
        self.object_resource = self.application_state.resource_manager.get_resource_by_resource_id(serial_representation.get('resource_id')) if 'resource_id' in serial_representation else None
