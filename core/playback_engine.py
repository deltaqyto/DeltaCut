import numpy as np
from PyQt6.QtCore import QIODevice, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

from core.application_state import ApplicationState
from core.timeline import Timeline, TimelineEntry


class AudioIODevice(QIODevice):
    """Custom QIODevice that provides audio data to QAudioSink"""

    def __init__(self, playback_engine, parent=None):
        super().__init__(parent)
        self.playback_engine = playback_engine
        self.current_sample_position = 0

    def readData(self, maxlen):
        """Called by Qt audio thread to request audio data"""
        bytes_per_sample = self.playback_engine.bytes_per_sample
        requested_samples = maxlen // bytes_per_sample

        if requested_samples == 0:
            return bytes()

        audio_data = self.playback_engine._get_mixed_audio(self.current_sample_position, requested_samples)
        audio_data = audio_data.T
        self.current_sample_position += requested_samples

        if not self.playback_engine._can_continue():
            self.playback_engine.stop_requested.emit()
        return audio_data.tobytes()

    def bytesAvailable(self):
        """Report infinite data available for streaming"""
        return super().bytesAvailable() + 2 ** 31 - 1  # Max value to indicate continuous stream

    def isSequential(self):
        """This is a sequential streaming device"""
        return True

    def writeData(self, data):
        """Not used for audio output"""
        return 0

    def reset_position(self, sample_position):
        """Reset to a specific sample position"""
        self.current_sample_position = sample_position


class PlaybackEngine(QObject):
    """Manages real-time audio and video playback"""

    stop_requested = pyqtSignal()

    def __init__(self, application_state: ApplicationState, timeline: Timeline):
        super().__init__()
        self.application_state: ApplicationState = application_state
        self.timeline: Timeline = timeline

        self.audio_sink: QAudioSink|None = None
        self.audio_io_device = None

        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self._update_video)

        self.active_entries: list[tuple[int, TimelineEntry]] = []  # (index, entry) pairs. Indexes into the timeline array
        self.is_playing = False
        self.start_frame = 0
        self.next_entry_index = 0

        self.sample_rate = None
        self.bit_depth = None
        self.audio_channels = None
        self.buffer_size = None
        self.frame_rate = None
        self.bytes_per_sample = None
        self.video_frame_interval = None

        self.stop_requested.connect(self._handle_stop_requested)

    def play(self, start_frame=0):
        """Start playback from the specified frame"""
        if self.is_playing:
            return

        self.start_frame = start_frame

        # Lock the timeline
        self.application_state.is_timeline_locked = True
        self.application_state.signal_timeline_lock_update.emit()
        self.is_playing = True

        self.sample_rate = self.application_state.project_settings.playback_codec.sample_rate.get_value()
        self.bit_depth = self.application_state.project_settings.playback_codec.bit_depth.get_value()
        self.audio_channels = self.application_state.project_settings.playback_codec.channels.get_value()
        self.buffer_size = self.application_state.settings.audio_buffer_size.get_value()
        self.frame_rate = self.application_state.project_settings.playback_codec.frame_rate.get_value()

        self.bytes_per_sample = self.audio_channels * (self.bit_depth // 8)
        self.video_frame_interval = int(1000 / self.frame_rate)

        audio_format = QAudioFormat()
        audio_format.setSampleRate(self.sample_rate)
        audio_format.setChannelCount(self.audio_channels)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        default_device = QMediaDevices.defaultAudioOutput()
        self.audio_sink = QAudioSink(default_device, audio_format)

        self.audio_io_device = AudioIODevice(self)
        self.audio_io_device.open(QIODevice.OpenModeFlag.ReadOnly)

        start_sample = self._frame_to_sample(start_frame)
        self.audio_io_device.reset_position(start_sample)

        # Work out what entries are visible before starting
        self.active_entries = []
        self.next_entry_index = 0
        current_frame = start_frame

        for i, entry in enumerate(self.timeline.timeline):
            entry_end_frame = entry.start_frame + entry.timeline_object.duration

            if entry.start_frame <= current_frame < entry_end_frame:
                if entry not in self.active_entries:
                    self.active_entries.append((i, entry))

            if entry.start_frame > current_frame:
                self.next_entry_index = i
                break

        self.audio_sink.start(self.audio_io_device)
        self.video_timer.start(self.video_frame_interval)

    def stop(self):
        """Stop playback and return to beginning"""
        if not self.is_playing and (self.audio_sink is None or
                                    self.audio_sink.state() == self.audio_sink.state().StoppedState):
            return None

        self.audio_sink.stop()
        self.video_timer.stop()

        # Unlock timeline
        self.application_state.is_timeline_locked = False
        self.application_state.signal_timeline_lock_update.emit()

        self.active_entries = []
        self.is_playing = False

        return self._sample_to_frame(self.audio_io_device.current_sample_position)

    def _handle_stop_requested(self):
        """Handle stop request from audio thread"""
        self.stop()

    def _get_mixed_audio(self, start_sample, sample_count):
        """Mix audio from all active entries"""
        current_frame = self._sample_to_frame(start_sample)
        end_frame = self._sample_to_frame(start_sample + sample_count)

        self._update_active_entries(current_frame, end_frame)

        audio_buffers = []

        for index, entry in self.active_entries:
            if not entry.timeline_object.can_play_audio:
                continue

            entry_start_sample = self._frame_to_sample(entry.start_frame)
            entry_duration_samples = self._frame_to_sample(entry.timeline_object.duration)
            entry_end_sample = entry_start_sample + entry_duration_samples

            overlap_start = max(start_sample, entry_start_sample)
            overlap_end = min(start_sample + sample_count, entry_end_sample)

            if overlap_start >= overlap_end:
                continue
            # Calculate relative position within clip and overlap length
            relative_start_sample = overlap_start - entry_start_sample
            overlap_sample_count = overlap_end - overlap_start

            assert relative_start_sample >= 0, "Relative sample position must be non-negative"

            # Get audio samples for the overlapping portion only
            clip_audio = entry.timeline_object.get_audio_samples(relative_start_sample, overlap_sample_count)

            # Handle mono to stereo conversion
            if clip_audio.shape[0] == 1 and self.audio_channels == 2:
                clip_audio = np.repeat(clip_audio, 2, axis=0)

            assert clip_audio.shape[0] == self.audio_channels, "Audio channel count mismatch"

            # Create padded buffer with zeros
            padded_audio = np.zeros((self.audio_channels, sample_count), dtype=clip_audio.dtype)

            # Place clip audio at correct position in buffer
            buffer_offset = overlap_start - start_sample
            padded_audio[:, buffer_offset:buffer_offset + overlap_sample_count] = clip_audio

            audio_buffers.append(padded_audio)

        if self.is_playing and current_frame - self.application_state.current_playback_frame > 1:
            self.application_state.current_playback_frame = current_frame
            self.application_state.signal_frame_number_update.emit()

        if len(audio_buffers) == 0:
            return np.zeros((self.audio_channels, sample_count), dtype=np.int16)

        mixed = np.zeros((self.audio_channels, sample_count), dtype=np.float32)
        for buffer in audio_buffers:
            actual_samples = min(buffer.shape[1], sample_count)
            mixed[:, :actual_samples] += buffer[:, :actual_samples].astype(np.float32)

        # Scale from [-1.0, 1.0] to [-32768, 32767]
        mixed = mixed * 32767
        mixed = np.clip(mixed, -32768, 32767)
        return mixed.astype(np.int16)

    def _update_active_entries(self, current_frame, end_frame):
        """Update active entries list based on current frame position"""
        # Deactivate entries that have ended
        self.active_entries = [ (index, entry) for index, entry in self.active_entries
            if current_frame < entry.start_frame + entry.timeline_object.duration
        ]

        # Activate new entries
        while self.next_entry_index < len(self.timeline.timeline):
            entry = self.timeline.timeline[self.next_entry_index]

            if entry.start_frame >= end_frame:
                break

            entry_end_frame = entry.start_frame + entry.timeline_object.duration

            if entry.start_frame < end_frame and entry_end_frame > current_frame:
                self.active_entries.append((self.next_entry_index, entry))

            self.next_entry_index += 1

    def _update_video(self):
        """Update video frames (called by timer on main thread)"""
        if not self.is_playing:
            return

        # Create blank frame buffer
        frame_buffer = QImage(self.application_state.rendered_frame.visual_frame)
        current_frame = self._sample_to_frame(self.audio_io_device.current_sample_position)

        frame_buffer = self.timeline.render_frame(current_frame, frame_buffer=frame_buffer,
                                   override_visible_entries=[i for i, entry in self.active_entries if entry.timeline_object.can_play_video])
                
        self.application_state.rendered_frame.visual_frame = frame_buffer  # Swap frame buffer
        self.application_state.signal_frame_buffer_update.emit()

    def _can_continue(self):
        """Check if playback should continue"""
        if len(self.active_entries) > 0:
            return True

        if self.next_entry_index < len(self.timeline.timeline):
            return True

        return False

    def _frame_to_sample(self, frame):
        """Convert timeline frame to audio sample position"""
        return int(frame * self.sample_rate / self.frame_rate)

    def _sample_to_frame(self, sample):
        """Convert audio sample position to timeline frame"""
        return int(sample * self.frame_rate / self.sample_rate)

    def set_application_state(self, application_state: ApplicationState):
        self.application_state = application_state
