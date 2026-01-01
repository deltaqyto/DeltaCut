import os
import subprocess
from pathlib import Path
import tempfile

import numpy as np
from PyQt6.QtCore import QObject, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QImage

from core.application_state import ApplicationState
from core.timeline import Timeline, TimelineEntry


class ExportWorker(QObject):
    """Worker object that runs export in separate thread"""

    finished = pyqtSignal()

    def __init__(self, application_state: ApplicationState, timeline: Timeline):
        super().__init__()
        self.application_state: ApplicationState = application_state
        self.timeline: Timeline = timeline

        self.start_frame = 0
        self.end_frame = 0
        self.should_stop = False

        self.sample_rate = None
        self.bit_depth = None
        self.audio_channels = None
        self.frame_rate = None
        self.bytes_per_sample = None

        self.active_entries: list[tuple[int, TimelineEntry]] = []  # (index, entry) pairs. Indexes into the timeline array
        self.next_entry_index = 0

        self.ffmpeg_video_process = None
        self.ffmpeg_audio_process = None

        self.temp_audio_file = None

        self.latest_frame = None
        self.latest_frame_id: int = 0

    def run(self):
        """Main export loop running in worker thread"""
        try:
            project = self.application_state.project_settings
            export_video = project.export_container.export_video.get_value()
            export_audio = project.export_container.export_audio.get_value()
            video_format = project.export_container.video_format.get_value()

            self._setup_export()

            # Stage 1: Export audio to temporary file if video will embed it
            if (export_video and video_format == "Video" and export_audio and
                    not project.export_container.audio_in_separate_file.get_value()):

                # Create temporary audio file
                temp_fd, self.temp_audio_file = tempfile.mkstemp(suffix='.wav')
                os.close(temp_fd)

                # Export audio to temp file
                self.ffmpeg_audio_process = self._create_audio_process(output_file=self.temp_audio_file)
                self._process_frames(export_video=False, export_audio=True)
                self._cleanup_processes()

                # Stage 2: Export video with audio file
                frame_width, frame_height = project.export_codec.frame_dimensions.get_value()
                self.ffmpeg_video_process = self._create_video_with_audio_file_process(
                    frame_width, frame_height, self.temp_audio_file
                )
                self.active_entries = []
                self.next_entry_index = 0
                self._process_frames(export_video=True, export_audio=False)
            else:
                # Single stage: export video and/or audio
                self._process_frames(export_video=export_video, export_audio=export_audio)

        finally:
            self._cleanup_processes()

            # Clean up temporary audio file
            if self.temp_audio_file:
                try:
                    Path(self.temp_audio_file).unlink(missing_ok=True)
                except Exception as e:
                    print(f"Export: Failed to delete temporary audio file: {e}")

            self.finished.emit()

    def stop(self):
        """Request immediate stop of export"""
        self.should_stop = True

    def _setup_export(self):
        """Initialise export parameters and FFmpeg processes"""
        project = self.application_state.project_settings

        self.sample_rate = project.export_codec.sample_rate.get_value()
        self.bit_depth = project.export_codec.bit_depth.get_value()
        self.audio_channels = project.export_codec.channels.get_value()
        self.frame_rate = project.export_codec.frame_rate.get_value()
        self.bytes_per_sample = self.audio_channels * (self.bit_depth // 8)

        frame_width, frame_height = project.export_codec.frame_dimensions.get_value()

        export_video = project.export_container.export_video.get_value()
        export_audio = project.export_container.export_audio.get_value()
        video_format = project.export_container.video_format.get_value()

        # Create parent directory for output files
        output_path = Path(project.export_container.file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup FFmpeg processes based on export configuration
        if export_video and video_format == "Video":
            if export_audio and not project.export_container.audio_in_separate_file.get_value():
                # Video with embedded audio - will be handled in two stages
                pass
            else:
                # Video only
                self.ffmpeg_video_process = self._create_video_process(frame_width, frame_height)

                if export_audio:
                    # Separate audio file
                    self.ffmpeg_audio_process = self._create_audio_process()

        elif export_video and video_format == "Image Sequence":
            # Create output folder for image sequence
            output_path = Path(project.export_container.file_path)
            output_path.mkdir(parents=True, exist_ok=True)

            if export_audio:
                # Audio in folder
                self.ffmpeg_audio_process = self._create_audio_process()

        elif export_audio and not export_video:
            # Audio only
            self.ffmpeg_audio_process = self._create_audio_process()

        # Initialise active entries tracking
        self.active_entries = []
        self.next_entry_index = 0

    def _create_video_process(self, width, height):
        """Create FFmpeg process for video only"""
        project = self.application_state.project_settings

        video_codec = project.export_codec.video_codec.get_value()
        video_quality = project.export_codec.video_quality.get_value()
        container = project.export_container.video_container.get_value()
        output_file = project.export_container.file_path + f".{container}"

        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgra',
            '-s', f'{width}x{height}',
            '-r', str(self.frame_rate),
            '-i', '-',
            '-c:v', video_codec,
            '-crf', str(video_quality),
            '-pix_fmt', 'yuv420p',
            output_file
        ]

        return subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def _create_audio_process(self, output_file=None):
        """Create FFmpeg process for audio only"""
        project = self.application_state.project_settings

        audio_codec = project.export_codec.audio_codec.get_value()
        audio_bitrate = project.export_codec.audio_bitrate.get_value()

        # Determine output filename
        if output_file is None:
            if project.export_container.export_video and project.export_container.video_format.get_value() == "Image Sequence":
                # Audio in image sequence folder
                output_file = str(Path(project.export_container.file_path) / f"audio.{self._get_audio_extension(audio_codec)}")
            else:
                # Standalone audio or separate from video
                output_file = project.export_container.file_path + f".{self._get_audio_extension(audio_codec)}"

        cmd = [
            'ffmpeg',
            '-y',
            '-f', 's16le',
            '-ar', str(self.sample_rate),
            '-ac', str(self.audio_channels),
            '-i', '-',
            '-c:a', audio_codec,
        ]

        # Add bitrate for compressed formats
        if audio_codec in ['aac', 'mp3']:
            cmd.extend(['-b:a', f'{audio_bitrate}k'])

        cmd.append(output_file)

        return subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def _create_video_with_audio_file_process(self, width, height, audio_file):
        """Create FFmpeg process for video with embedded audio from file"""
        export_codec = self.application_state.project_settings.export_codec
        video_codec = export_codec.video_codec.get_value()
        video_quality = export_codec.video_quality.get_value()
        audio_codec = export_codec.audio_codec.get_value()
        audio_bitrate = export_codec.audio_bitrate.get_value()

        export_container = self.application_state.project_settings.export_container
        container = export_container.video_container.get_value()
        output_file = export_container.file_path + f".{container}"

        cmd = [
            'ffmpeg',
            '-y',
            # Video input from stdin
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgra',
            '-s', f'{width}x{height}',
            '-r', str(self.frame_rate),
            '-i', '-',
            # Audio input from file
            '-i', audio_file,
            # Video encoding
            '-c:v', video_codec,
            '-crf', str(video_quality),
            '-pix_fmt', 'yuv420p',
            # Audio encoding
            '-c:a', audio_codec,
        ]

        if audio_codec in ['aac', 'mp3']:
            cmd.extend(['-b:a', f'{audio_bitrate}k'])

        cmd.append(output_file)

        return subprocess.Popen(cmd, stdin=subprocess.PIPE)

    @staticmethod
    def _get_audio_extension(codec):
        """Get file extension for audio codec"""
        extensions = {
            'aac': 'm4a',
            'mp3': 'mp3',
            'flac': 'flac',
            'pcm': 'wav'
        }
        return extensions.get(codec, 'wav')

    def _process_frames(self, export_video: bool, export_audio: bool):
        """Process all frames from start to end.
        Stops after completing current frame if stop is called"""
        project = self.application_state.project_settings
        frame_width, frame_height = project.export_codec.frame_dimensions.get_value()
        video_format = project.export_container.video_format.get_value()

        total_frames = self.end_frame - self.start_frame
        padding_width = len(str(total_frames))

        for current_frame in range(self.start_frame, self.end_frame):
            if self.should_stop:
                break

            # Update active entries
            self._update_active_entries(current_frame, current_frame + 1)

            # Render video frame if needed
            if export_video:
                frame_buffer = QImage(frame_width, frame_height, QImage.Format.Format_ARGB32)
                frame_buffer = self.timeline.render_frame(current_frame, frame_buffer=frame_buffer,
                                                          override_visible_entries=[i for i, entry in self.active_entries if entry.timeline_object.can_play_video])

                # Update shared frame
                self.latest_frame = frame_buffer
                frame_data = frame_buffer.bits().asarray(frame_buffer.sizeInBytes())

                # Write frame to appropriate output
                if video_format == "Video":
                    self.ffmpeg_video_process.stdin.write(frame_data)
                else:
                    # Save as individual image
                    frame_filename = f"{current_frame:0{padding_width}d}.{project.export_container.image_format.get_value()}"
                    frame_path = Path(project.export_container.file_path) / frame_filename
                    frame_buffer.save(str(frame_path))

            # Process audio for this frame
            if export_audio:
                start_sample = self._frame_to_sample(current_frame)
                end_sample = self._frame_to_sample(current_frame + 1)
                sample_count = end_sample - start_sample

                audio_data = self._get_mixed_audio(start_sample, sample_count)
                audio_data = audio_data.T
                audio_bytes = audio_data.tobytes()

                self.ffmpeg_audio_process.stdin.write(audio_bytes)

            self.latest_frame_id = current_frame

    def _cleanup_processes(self):
        """Close FFmpeg processes and wait for completion"""
        for process in [self.ffmpeg_video_process, self.ffmpeg_audio_process]:
            if process:
                try:
                    if process.stdin:
                        process.stdin.close()
                    process.wait(timeout=5)
                except Exception as e:
                    print(f"Export: Error on closing ffmpeg. Killing process: {e}")
                    process.kill()

        self.ffmpeg_video_process = None
        self.ffmpeg_audio_process = None

    def _update_active_entries(self, current_frame, end_frame):
        """Update active entries list based on current frame position"""
        # Deactivate entries that have ended
        self.active_entries = [(index, entry) for index, entry in self.active_entries
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

    def _get_mixed_audio(self, start_sample, sample_count):
        """Mix audio from all active entries.
        Timeline entries must be activated before calling"""
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

        if len(audio_buffers) == 0:
            return np.zeros((self.audio_channels, sample_count), dtype=np.int16)

        mixed = np.zeros((self.audio_channels, sample_count), dtype=np.float32)
        for buffer in audio_buffers:
            actual_samples = min(buffer.shape[1], sample_count)
            mixed[:, :actual_samples] += buffer[:, :actual_samples].astype(np.float32)

        # Scale and clip
        mixed = mixed * 32767
        mixed = np.clip(mixed, -32768, 32767)
        return mixed.astype(np.int16)

    def _frame_to_sample(self, frame):
        """Convert timeline frame to audio sample position"""
        return int(frame * self.sample_rate / self.frame_rate)

    def _sample_to_frame(self, sample):
        """Convert audio sample position to timeline frame"""
        return int(sample * self.frame_rate / self.sample_rate)


class ExportEngine(QObject):
    """Manages video and audio export to files"""

    def __init__(self, application_state: ApplicationState, timeline: Timeline):
        super().__init__()
        self.application_state = application_state
        self.timeline = timeline

        self.viewport_update_rate = 4  # Viewport update rate hz
        self.playhead_update_rate = 30  # Playhead update rate hz
        self.frame_at_start = 0  # Frame that was active before export began

        self.worker: ExportWorker | None = None
        self.worker_thread = None
        self.viewport_update_timer = QTimer()
        self.viewport_update_timer.timeout.connect(self._update_display)
        self.playhead_update_timer = QTimer()
        self.playhead_update_timer.timeout.connect(self._update_playhead)

        self.is_exporting = False

    def start(self, start_frame=0, end_frame=None):
        """Start export from start_frame to end_frame"""
        if self.is_exporting:
            return

        # Determine end frame
        if end_frame is None:
            end_frame = self.timeline.get_duration()

        # Validation asserts
        assert start_frame >= 0, "Start frame must be non-negative"
        assert end_frame > start_frame, "End frame must be greater than start frame"

        project = self.application_state.project_settings

        # Validate export configuration
        assert project.export_container.export_video or project.export_container.export_audio, \
            "Must export at least video or audio"

        if project.export_container.video_format.get_value() == "Image Sequence":
            if project.export_container.export_audio and project.export_container.export_video:
                assert project.export_container.audio_in_separate_file.get_value(), \
                    "audio_in_separate_file must be true for image sequences with both audio and video"

        # Validate codec settings
        sample_rate = project.export_codec.sample_rate.get_value()
        assert sample_rate > 0, "Sample rate must be positive"

        frame_rate = project.export_codec.frame_rate.get_value()
        assert frame_rate > 0, "Frame rate must be positive"

        self.frame_at_start = self.application_state.current_playback_frame

        # Create worker and thread
        self.worker = ExportWorker(self.application_state, self.timeline)
        self.worker.start_frame = start_frame
        self.worker.end_frame = end_frame

        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        # Connect signals
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_export_finished)

        # Start export
        self.is_exporting = True
        self.worker_thread.start()
        self.viewport_update_timer.start(1000 // self.viewport_update_rate)
        self.playhead_update_timer.start(1000 // self.playhead_update_rate)

    def stop(self):
        """Stop export process"""
        if not self.is_exporting:
            return

        self.viewport_update_timer.stop()
        self.playhead_update_timer.stop()

        if self.worker:
            self.worker.stop()

        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()

        self.application_state.rendered_frame.visual_frame = self.timeline.render_frame(self.frame_at_start)
        self.application_state.current_playback_frame = self.frame_at_start
        self.application_state.signal_frame_number_update.emit()
        self.application_state.signal_frame_buffer_update.emit()

        self.is_exporting = False

    def _on_export_finished(self):
        """Handle export completion"""
        self.stop()

    def _update_display(self):
        """Update display with latest rendered frame"""
        if not self.worker:
            return

        # Pull latest frame from worker
        latest_frame = self.worker.latest_frame
        if latest_frame is None:
            return

        # Update application state frame buffer
        self.application_state.rendered_frame.visual_frame = latest_frame.copy()
        self.application_state.signal_frame_buffer_update.emit()

    def _update_playhead(self):
        """Update display with latest rendered frame"""
        if not self.worker:
            return

        latest_frame_id = self.worker.latest_frame_id

        self.application_state.current_playback_frame = latest_frame_id
        self.application_state.signal_frame_number_update.emit()


    def set_application_state(self, application_state: ApplicationState):
        self.application_state = application_state
