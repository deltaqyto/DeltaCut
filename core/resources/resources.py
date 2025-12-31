import uuid
import weakref

class BaseResource:
    """Base class for shareable media resources.

    Resources are path-indexed and automatically shared between multiple timeline objects.
    Creating a Resource with an existing path returns the cached instance instead of loading
    the file again, saving memory.

    Each Resource subclass maintains its own separate registry, allowing the same path to
    represent different resource types (e.g., VideoResource and AudioResource for the same file).

    Resources are ready immediately upon instantiation. Cleanup occurs automatically when
    the last reference is released.

    Args:
        path: File path or unique identifier for the resource
        skip_loading_resource: If True, skip loading from disk, allows for software defined files

    Example:
        # Normal usage - loads from file
        video = VideoResource("clip.mp4")

        # Multiple references return same instance
        video2 = VideoResource("clip.mp4")  # Returns same object as video

        # Empty resource for custom data
        audio = AudioResource("notarealfile", skip_loading_resource=True)
        audio.data = somedata
    """

    def __new__(cls, path=None, skip_loading_resource=False, serialised_data=None, **kwargs):
        """Create or retrieve cached resource instance.

        Checks the subclass-specific registry for an existing resource at this path.
        Returns cached instance if available, otherwise creates new instance with
        weakref tracking for automatic cleanup.
        """
        # Extract path from serialised_data if deserialising
        if serialised_data is not None:
            assert 'path' in serialised_data, f'Serialised resource data must contain a resource path, got {serialised_data}'
            path = serialised_data['path']

        if not hasattr(cls, '_registry'):
            cls._registry = {}

        if path in cls._registry:
            existing = cls._registry[path]()
            if existing is not None:
                return existing

        instance = super().__new__(cls)
        cls._registry[path] = weakref.ref(
            instance,
            lambda ref: cls._registry.pop(path, None)
        )
        return instance

    def __init__(self, path=None, skip_loading_resource=False, resource_id=None, serialised_data=None, **kwargs):
        """Initialise resource.

        Only runs once per instance, even if retrieved from registry multiple times.
        Calls _load() unless skip_loading_resource=True.
        """
        if hasattr(self, '_initialised'):
            return  # Already initialised from registry return

        self._initialised = True

        self.path = path
        self.skip_loading = skip_loading_resource
        self.resource_id = resource_id or str(uuid.uuid4())

        if serialised_data is not None:
            self.deserialise_resource(serialised_data)

        if not self.skip_loading:
            assert self.path is not None, f'Resource cannot have a None path'
            self._load()

    def _load(self):
        """Load resource data from path.

        Subclasses must implement specific loading behaviour.
        Called during __init__ unless skip_loading_resource=True.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement _load()")

    def __del__(self):
        """Cleanup when resource destroyed.

        Subclasses should implement cleanup of loaded data (close files, free memory, etc).
        Called automatically when last reference is released.
        """
        pass

    def get_read_head(self):
        """Instance and return a read head.

        A read head provides an interface to read the resource.
        It can prefetch or cache data as desired.

        Subclasses must implement this to return their specific read head type.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement get_read_head()")


    def get_audio_read_head(self):
        """Instance and return an AUDIO read head."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support reading audio")

    def get_video_read_head(self):
        """Instance and return an VIDEO read head."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support reading video")

    def serialise_resource(self):
        return {'path': self.path,
                'skip_loading': self.skip_loading,
                'resource_id': self.resource_id,
                'resource_type': 'BaseResource'}  # All resources must include a resource type, and must register it in the type registry

    def deserialise_resource(self, serialised_data):
        self.path = serialised_data['path']
        self.skip_loading = serialised_data.get('skip_loading', False)
        self.resource_id = serialised_data.get('resource_id', str(uuid.uuid4()))

    def uses_external_resource_file(self):
        return not self.skip_loading

    def export_resource_file(self) -> (str, bytes):
        """Exports the resource file, returning the file type extension, and the file data.
        Eg: ('.txt', b'abc')"""
        raise NotImplementedError(f"{self.__class__.__name__} did not implement resource file exports")

    def import_resource_file(self, resource_file: bytes):
        raise NotImplementedError(f"{self.__class__.__name__} did not implement resource file imports")



class BaseReadHead:
    """Base class for resource read heads.

    Read heads provide position-based access to resource data.
    Multiple read heads can operate on the same resource simultaneously,
    each maintaining independent position and buffer state.

    Args:
        resource: The resource instance to read from
    """

    def __init__(self, resource: BaseResource):
        self.resource = resource

    def read(self, position, count=1):
        """Read items from the resource at the specified position.

        Args:
            position: Starting position (frame number, sample number, index, etc.)
            count: Number of items to read from position

        Returns:
            Resource-specific data at the requested position
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement read()")
