import json
from bisect import bisect_right
from uuid import UUID, uuid4

from core.resources.resources import BaseResource, BaseReadHead


class TranscriptResource(BaseResource):
    """Resource for transcripts.
    Transcript stored as time and text lists, both sorted by time. Time is represented as frames from the start of the resource
    Text is pairs of speaker, text.
    """

    def __init__(self, path=None, skip_loading_resource=False, resource_id=None, serialised_data=None):
        self.transcript_entries: dict[UUID, tuple[str, str]] = {}
        self.transcript_order: list[UUID] = []
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

        self.load_from_data(data['transcripts'], data['timestamps'])

    def load_from_data(self, transcripts, timestamps):
        """Load from directly provided transcript and timestamp"""

        assert isinstance(transcripts, list), "transcripts must be a list"
        assert all(isinstance(t, (list, tuple)) and len(t) == 2 for t in transcripts), "All transcripts must be pairs"
        assert all(isinstance(t[0], str) and isinstance(t[1], str) for t in transcripts), "All transcript pairs must be (str, str)"

        assert isinstance(timestamps, list), "timestamps must be a list"
        assert all(isinstance(t, int) for t in timestamps), "All timestamps must be integers"


        self.transcript_entries = {}
        self.transcript_order = []
        for entry in transcripts:
            entry_id = str(uuid4())
            self.transcript_order.append(entry_id)
            self.transcript_entries[entry_id] = tuple(entry)
        self.timestamps = timestamps

        assert len(self.transcript_order) == len(self.timestamps), f"Transcript Resource: transcripts ({len(self.transcript_order)}) != timestamps ({len(self.timestamps)})"

    def export_resource_file(self) -> (str, bytes):
        """Exports the transcript as a .json"""

        data = {
            'transcripts': [self.transcript_entries[entry_id] for entry_id in self.transcript_order],
            'timestamps': self.timestamps
        }

        json_str = json.dumps(data)
        json_bytes = json_str.encode('utf-8')

        return '.json', json_bytes

    def import_resource_file(self, resource_file: bytes):
        data = json.loads(resource_file.decode('utf-8'))
        self._load(data)

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
        """Returns transcript timestamp, uuid and entry visible at provided frame

        Args:
            position: Frame position
            count: Ignored

        Returns:
            None if nothing is visible, or (frames when the entry was first visible, entry uuid as a string and tuple of (speaker, text))
        """
        if not self.resource.timestamps:
            return None

        idx = bisect_right(self.resource.timestamps, position) - 1

        if idx < 0:
            return None

        entry_id = self.resource.transcript_order[idx]
        return self.resource.timestamps[idx], entry_id, self.resource.transcript_entries[entry_id]
