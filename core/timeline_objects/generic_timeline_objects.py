from core.application_state import ApplicationState
from core.timeline_objects.timeline_object import TimelineObject


class ErrorTimelineObject(TimelineObject):
    """Non-functional object that indicates an error in loading
    """

    def __init__(self, application_state: ApplicationState, serial_representation=None, object_resource=None):
        super().__init__(application_state, serial_representation, object_resource=object_resource)

        self.can_play_video = False  # Will this object be queued for video processing
        self.can_play_audio = False  # Will this object be queued for audio processing

    def serialise_object(self):
        """Generate a dictionary serialisation of the object.
        The serialised format is guaranteed to store the type of the object itself, and is guaranteed to match an entry in the type registry"""
        serialised_data = super().serialise_object()
        serialised_data.update({'object_type': 'ErrorTimelineObject'})
        return serialised_data

    def deserialise_object(self, serial_representation):
        """Reverse a dictionary serialisation into the object.
        If the object requires a resource, the resource manager must already be set up in the app state"""
        super().deserialise_object(serial_representation)
