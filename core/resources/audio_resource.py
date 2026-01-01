import librosa
from core.resources.resources import BaseResource, BaseReadHead
from core.resources.transcript_resource import TranscriptResource


class AudioResource(BaseResource):
    """Resource for audio file content.

    Loads entire audio file into memory using librosa.
    Preserves original sample rate and channel configuration.

    Attributes:
        data: Numpy array of audio samples. Shape is (n_channels, n_samples)
        sample_rate: Sample rate in Hz
        duration: Duration in seconds
        n_channels: Number of audio channels (1 for mono, 2 for stereo, etc)
        n_samples: Total number of samples per channel

    Example:
        # Load from file
        audio = AudioResource("soundtrack.wav")
        print(f"Duration: {audio.duration}s at {audio.sample_rate}Hz")

        # Skip loading resource for manual population
        extracted = AudioResource("video.mp4.audio", skip_loading_resource=True)
        extracted.data = audio_array
        extracted.sample_rate = 48000
    """

    def __init__(self, path=None, skip_loading_resource=False, resource_id=None, serialised_data=None, sample_rate=None, force_mono=False):
        self.data = None
        self.sample_rate = sample_rate
        self.force_mono = force_mono
        self.duration = None
        self.n_channels = None
        self.n_samples = None
        self.transcript_resource: TranscriptResource | None = None  # Reference to actual bound transcript
        self.transcript_id: str | None = None  # Resource ID for bound transcript
        super().__init__(path, skip_loading_resource, resource_id, serialised_data)
        if self.data is None:  # If the resource manager is reloaded mid execution, it does not clear the cache. Manually check to ensure the data exists
            self._load()

    def _load(self):
        """Load audio file using librosa.
        """
        # Load with original sample rate and preserve channels
        self.data, self.sample_rate = librosa.load(
            self.path,
            sr=self.sample_rate,
            mono=self.force_mono,
        )

        # Handle channel dimension
        if self.data.ndim == 1:
            self.data = self.data.reshape(1, -1)
            self.n_channels = 1
        else:
            self.n_channels = self.data.shape[0]

        self.n_samples = self.data.shape[1]
        self.duration = self.n_samples / self.sample_rate

    def __del__(self):
        """Release audio data from memory."""
        self.data = None

    def get_read_head(self):
        """Instance and return a read head."""
        return AudioReadHead(self)

    def get_audio_read_head(self):
        """Instance and return an AUDIO read head."""
        return AudioReadHead(self)

    def serialise_resource(self):
        serialised_data = super().serialise_resource()
        serialised_data.update({
            'sample_rate': self.sample_rate,
            'force_mono': self.force_mono,
            'transcript_id': self.transcript_resource.resource_id if self.transcript_resource is not None else None,
            'resource_type': 'AudioResource'
        })
        return serialised_data

    def deserialise_resource(self, serialised_data):
        assert serialised_data['resource_type'] == 'AudioResource'
        super().deserialise_resource(serialised_data)
        self.force_mono = serialised_data.get('force_mono', False)
        self.sample_rate = serialised_data.get('sample_rate')
        self.transcript_id = serialised_data.get('transcript_id')

    def resolve_references(self, resource_manager):
        """Find and bind transcript resource if previously set"""
        if self.transcript_id:
            self.transcript_resource = resource_manager.get_resource_by_resource_id(self.transcript_id)
            self.transcript_id = None


class AudioReadHead(BaseReadHead):
    """Audio read head provides sample-based access to audio data.

    Reads directly from in-memory audio array.

    Args:
        resource: The AudioResource instance to read from
    """

    def __init__(self, resource: AudioResource):
        super().__init__(resource)

    def read(self, position=0, count=0):
        """Read audio samples from the specified position.

        Args:
            position: Starting sample number (integer index)
            count: Number of samples to read. count=0 returns all remaining samples

        Returns:
            Numpy array of audio samples.
            Shape is (n_channels, count) for multi-channel.

        Raises:
            IndexError: If position is negative or beyond audio length
            IndexError: If count would read past end of audio (unless count=0)
        """
        if position < 0:
            raise IndexError(f"Position cannot be negative: {position}")

        if position >= self.resource.n_samples:
            raise IndexError(
                f"Position {position} beyond audio length {self.resource.n_samples}"
            )

        # Handle count=0 as "read to end"
        if count == 0:
            return self.resource.data[:, position:]

        # Validate count doesn't exceed remaining samples
        end_position = position + count
        if end_position > self.resource.n_samples:
            raise IndexError(
                f"Requested range [{position}:{end_position}] exceeds audio length {self.resource.n_samples}"
            )

        # (n_channels, n_samples) -> (n_channels, count)
        return self.resource.data[:, position:end_position]
