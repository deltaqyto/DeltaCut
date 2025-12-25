from core.timeline_objects.generic_timeline_objects import ErrorTimelineObject
from core.timeline_objects.image_media_timeline_object import ImageMediaTimelineObject
from core.timeline_objects.media_timeline_object import AudioMediaTimelineObject

TIMELINE_OBJECT_TYPE_REGISTRY = {'BaseTimelineObject': ErrorTimelineObject, # The base should never be instanced
                                 'AudioMediaTimelineObject': AudioMediaTimelineObject,
                                 'ImageMediaTimelineObject': ImageMediaTimelineObject,
                                 'ErrorTimelineObject': ErrorTimelineObject}

# List of valid resource types for a given media object
TIMELINE_OBJECT_RESOURCE_TYPE_REGISTRY = {
    'BaseTimelineObject': [],
    'AudioMediaTimelineObject': ['AudioResource'],
    'ImageMediaTimelineObject': ['ImageResource'],
    'VideoMediaTimelineObject': ['VideoResource'],
    'ErrorTimelineObject': []
}
