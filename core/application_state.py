from dataclasses import dataclass, field

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QImage, QColor

from core.resources.resource_manager import ResourceManager
from core.setting.basic_settings import ChoiceSetting, IntRangeSetting, FloatRangeSetting, ResolutionSetting


@dataclass
class Codec:
    # Audio
    sample_rate: ChoiceSetting = ChoiceSetting(44100, [16000, 22050, 44100, 48000, 882000, 96000])
    channels: ChoiceSetting = ChoiceSetting(2, [1, 2])
    bit_depth: ChoiceSetting = ChoiceSetting(16, [2, 4, 8, 16, 32])
    audio_codec: ChoiceSetting = ChoiceSetting("aac", ["aac", "mp3", "flac", "pcm"])
    audio_bitrate: IntRangeSetting = IntRangeSetting(192, 64, 512)  # kbps, for compressed formats

    # Video
    frame_rate: FloatRangeSetting = FloatRangeSetting(30, 1, 300)
    frame_dimensions: ResolutionSetting = ResolutionSetting((1920, 1080), 16, 4096, 16, 4096)
    video_codec: ChoiceSetting = ChoiceSetting("h264", ["h264", "h265", "vp9"])
    video_quality: IntRangeSetting = IntRangeSetting(23, 0, 51)  # CRF value

    def serialise(self):
        return {
            'sample_rate': self.sample_rate.serialise(),
            'channels': self.channels.serialise(),
            'bit_depth': self.bit_depth.serialise(),
            'audio_codec': self.audio_codec.serialise(),
            'audio_bitrate': self.audio_bitrate.serialise(),
            'frame_rate': self.frame_rate.serialise(),
            'frame_dimensions': self.frame_dimensions.serialise(),
            'video_codec': self.video_codec.serialise(),
            'video_quality': self.video_quality.serialise()
        }

    def deserialise(self, serialised_data):
        self.sample_rate.deserialise(serialised_data.get('sample_rate'))
        self.channels.deserialise(serialised_data.get('channels'))
        self.bit_depth.deserialise(serialised_data.get('bit_depth'))
        self.audio_codec.deserialise(serialised_data.get('audio_codec'))
        self.audio_bitrate.deserialise(serialised_data.get('audio_bitrate'))
        self.frame_rate.deserialise(serialised_data.get('frame_rate'))
        self.frame_dimensions.deserialise(serialised_data.get('frame_dimensions'))
        self.video_codec.deserialise(serialised_data.get('video_codec'))
        self.video_quality.deserialise(serialised_data.get('video_quality'))


@dataclass
class MediaContainer:
    file_path: str = "Untitled"

    export_video: ChoiceSetting = ChoiceSetting(True, [True, False])
    export_audio: ChoiceSetting = ChoiceSetting(True, [True, False])

    # Video format (only relevant if export_video=True)
    video_format: ChoiceSetting = ChoiceSetting("Video", ["Video", "Image Sequence"])

    # Audio handling (only relevant if export_audio=True and export_video=True and video_format="Video")
    audio_in_separate_file: ChoiceSetting = ChoiceSetting(False, [True, False])  # If True, audio exports to separate file even with video

    # Container/format types
    video_container: ChoiceSetting = ChoiceSetting("mp4", ["mp4", "mkv", "mov", "avi", "webm"])  # Used when video_format="Video"
    image_format: ChoiceSetting = ChoiceSetting("png", ["png", "jpeg", "tiff"])  # Used when video_format="Image Sequence"

    def serialise(self):
        return {
            'file_path': self.file_path,
            'export_video': self.export_video.serialise(),
            'export_audio': self.export_audio.serialise(),
            'video_format': self.video_format.serialise(),
            'audio_in_separate_file': self.audio_in_separate_file.serialise(),
            'video_container': self.video_container.serialise(),
            'image_format': self.image_format.serialise()
        }

    def deserialise(self, serialised_data):
        self.file_path = serialised_data.get('file_path')
        self.export_video.deserialise(serialised_data.get('export_video'))
        self.export_audio.deserialise(serialised_data.get('export_audio'))
        self.video_format.deserialise(serialised_data.get('video_format'))
        self.audio_in_separate_file.deserialise(serialised_data.get('audio_in_separate_file'))
        self.video_container.deserialise(serialised_data.get('video_container'))
        self.image_format.deserialise(serialised_data.get('image_format'))


@dataclass
class ApplicationSettings:
    audio_buffer_size: IntRangeSetting = IntRangeSetting(1024, 32, 4096)
    default_playback_codec: Codec = field(default_factory=Codec)

    def serialise(self):
        return {
            'audio_buffer_size': self.audio_buffer_size.serialise(),
            'default_playback_codec': self.default_playback_codec.serialise()
        }

    def deserialise(self, serialised_data):
        self.audio_buffer_size.deserialise(serialised_data.get('audio_buffer_size'))
        self.default_playback_codec.deserialise(serialised_data.get('default_playback_codec'))


@dataclass
class ProjectSettings:
    playback_codec: Codec = field(default_factory=Codec)
    export_codec: Codec = field(default_factory=Codec)
    export_container: MediaContainer = field(default_factory=MediaContainer)

    def serialise(self):
        return {
            'playback_codec': self.playback_codec.serialise(),
            'export_codec': self.export_codec.serialise(),
            'export_container': self.export_container.serialise()
        }

    def deserialise(self, serialised_data):
        self.playback_codec.deserialise(serialised_data.get('playback_codec'))
        self.export_codec.deserialise(serialised_data.get('export_codec'))
        self.export_container.deserialise(serialised_data.get('export_container'))


class FrameBuffer:
    """Rendering framebuffer.
    Stores a RGB/RGBA numpy frame buffer"""
    def __init__(self, size_x, size_y, background_color: QColor):
        self.visual_frame: QImage = QImage(size_x, size_y, QImage.Format.Format_ARGB32)
        self.background_color: QColor = background_color

    def update_frame_size(self, size_x, size_y):
        """Change the size of the framebuffer. Will wipe contents"""
        self.visual_frame = QImage(size_x, size_y, QImage.Format.Format_ARGB32)


class ApplicationState(QObject):
    """Application operating data utility class.
    Should not be deleted until the application is closed"""

    signal_frame_buffer_update: pyqtSignal = pyqtSignal()  # Triggered when the frame buffer has been updated with new data.

    signal_frame_number_update: pyqtSignal = pyqtSignal()  # Triggered when the frame number has been changed.
    signal_timeline_content_update: pyqtSignal = pyqtSignal()  # Triggered when the timeline contents have been altered.
    signal_timeline_lock_update: pyqtSignal = pyqtSignal()  # Triggered when the timeline has been locked or unlocked.

    signal_entry_selection_update: pyqtSignal = pyqtSignal()  # Triggered when the selected entry has changed.

    def __init__(self):
        super().__init__(parent=None)

        self.settings: ApplicationSettings = ApplicationSettings()
        self.project_settings: ProjectSettings = ProjectSettings()
        self.resource_manager: ResourceManager = ResourceManager()

        self.rendered_frame: FrameBuffer = FrameBuffer(*self.project_settings.playback_codec.frame_dimensions.get_value(), QColor(0, 0, 0, 0))
        self.rendered_entries: list = []  # List of timeline entries that got rendered onto the frame. Sorted by order of rendering (last index rendered last)

        self.current_playback_frame: int = 0  # The frame that is currently visible on the viewport
        self.is_timeline_locked: bool = False  # The timeline is read-only when True
