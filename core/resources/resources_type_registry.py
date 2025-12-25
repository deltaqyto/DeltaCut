from core.resources.audio_resource import AudioResource
from core.resources.image_resource import ImageResource
from core.resources.resources import BaseResource

RESOURCES_TYPE_REGISTRY = {'BaseResource': BaseResource,
                           'AudioResource': AudioResource,
                           'ImageResource': ImageResource}

# Guaranteed to contain no duplicate file types
RESOURCES_FILE_TYPE_REGISTRY = {
    'AudioResource': ['*.wav', '*.mp3', '*.flac', '*.ogg', '*.aac', '*.m4a', '*.wma', '*.opus'],
    'ImageResource': ['*.png', '*.jpg', '*.jpeg', '*.webp', '*.bmp', '*.tiff'],
    'VideoResource': ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.webm', '*.flv', '*.wmv', '*.m4v', '*.mpeg', '*.mpg']

}

def get_resource_type_from_file_type(file_type):
    """Get resource type name given file type. Performs search through file type registry"""
    for resource_type, extensions in RESOURCES_FILE_TYPE_REGISTRY.items():
        if file_type in extensions:
            return resource_type
    return None
