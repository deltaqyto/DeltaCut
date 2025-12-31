import json
from bisect import bisect_right

from core.resources.resources import BaseResource, BaseReadHead


class TranscriptResource(BaseResource):
    """Resource for transcripts.
    Transcript stored as time and text lists, both sorted by time. Time is represented as frames from the start of the resource
    Text is pairs of speaker, text.
    """

    def __init__(self, path=None, skip_loading_resource=False, resource_id=None, serialised_data=None):
        self.transcripts: list[tuple[str, str]] = []
        self.timestamps: list[int] = []
        super().__init__(path, skip_loading_resource, resource_id, serialised_data)
        if self.path is not None:
            self._load()

    def _load(self, override_data=None):
        """Load transcript from json"""

        if override_data is not None:
            data = override_data
        else:
            with open(self.path, 'r') as f:
                data = json.loads(f.read())

        assert 'transcripts' in data, "Missing 'transcripts' key in JSON data"
        assert 'timestamps' in data, "Missing 'timestamps' key in JSON data"

        assert isinstance(data['transcripts'], list), "transcripts must be a list"
        assert all(isinstance(t, (list, tuple)) and len(t) == 2 for t in data['transcripts']), "All transcripts must be pairs"
        assert all(isinstance(t[0], str) and isinstance(t[1], str) for t in data['transcripts']), "All transcript pairs must be (str, str)"

        assert isinstance(data['timestamps'], list), "timestamps must be a list"
        assert all(isinstance(t, int) for t in data['timestamps']), "All timestamps must be integers"

        self.transcripts = [tuple(t) for t in data['transcripts']]
        self.timestamps = data['timestamps']

        assert len(self.transcripts) == len(self.timestamps), f"Transcript Resource: transcripts ({len(self.transcripts)}) != timestamps ({len(self.timestamps)})"

    def export_resource_file(self) -> (str, bytes):
        """Exports the transcript as a .json"""

        data = {
            'transcripts': self.transcripts,
            'timestamps': self.timestamps
        }

        json_str = json.dumps(data)
        json_bytes = json_str.encode('utf-8')

        return '.json', json_bytes

    def import_resource_file(self, resource_file: bytes):
        data = json.loads(resource_file.decode('utf-8'))
        self._load(data)

    def __del__(self):
        """Release data from memory."""
        self.transcripts: list[str] = []
        self.timestamps: list[int] = []

    def get_read_head(self):
        """Instance and return a read head."""
        return TranscriptReadHead(self)

    def serialise_resource(self):
        """Serialise to dict"""
        serialised_data = super().serialise_resource()
        serialised_data.update({
            'resource_type': 'TranscriptResource'
        })
        return serialised_data

    def deserialise_resource(self, serialised_data):
        """Restore from dict"""
        assert serialised_data['resource_type'] == 'TranscriptResource'
        super().deserialise_resource(serialised_data)


class TranscriptReadHead(BaseReadHead):
    """Transcript read head provides access to the transcript data."""

    def __init__(self, resource: TranscriptResource):
        super().__init__(resource)

    def read(self, position=None, count=None):
        """Returns transcript entry visible at provided frame

        Args:
            position: Frame position
            count: Ignored

        Returns:
            None if nothing is visible, or (frames: when the entry was first visible, text for that entry)
        """
        if not self.resource.transcripts:
            return None

        idx = bisect_right(self.resource.timestamps, position) - 1

        if idx < 0:
            return None

        return self.resource.timestamps[idx], self.resource.transcripts[idx]
