import numpy as np
from PIL import Image
from core.resources.resources import BaseResource, BaseReadHead


class ImageResource(BaseResource):
    """Resource for image file content.

    Loads entire image into memory using PIL and converts to RGBA format.
    All images are standardised to 4-channel RGBA regardless of original format.

    Attributes:
        data: Numpy array of image data. Shape is (height, width, 4) for RGBA
        width: Image width in pixels
        height: Image height in pixels
        original_mode: Original PIL image mode before RGBA conversion

    Example:
        # Load from file
        image = ImageResource("photo.jpg")
        print(f"Size: {image.width}x{image.height}")

        # Skip loading resource for manual population
        generated = ImageResource("render.png", skip_loading_resource=True)
        generated.data = rgba_array
        generated.width = 1920
        generated.height = 1080
    """

    def __init__(self, path=None, skip_loading_resource=False, resource_id=None, serialised_data=None):
        self.data = None
        self.width = None
        self.height = None
        self.original_mode = None
        super().__init__(path, skip_loading_resource, resource_id, serialised_data)
        if self.data is None:
            self._load()

    def _load(self):
        """Load image file using PIL and convert to RGBA."""
        img = Image.open(self.path)
        self.original_mode = img.mode

        assert len(img.getbands()) <= 4, f"Image has {len(img.getbands())} channels, maximum supported is 4"

        # Convert to RGBA
        img_rgba = img.convert('RGBA')

        # Convert to numpy array (height, width, 4)
        self.data = np.array(img_rgba)
        self.height, self.width = self.data.shape[:2]

    def __del__(self):
        """Release image data from memory."""
        self.data = None

    def get_read_head(self):
        """Instance and return a read head."""
        return ImageReadHead(self)

    def get_video_read_head(self):
        """Instance and return a VIDEO read head."""
        return ImageReadHead(self)

    def serialise_resource(self):
        serialised_data = super().serialise_resource()
        serialised_data.update({
            'original_mode': self.original_mode,
            'resource_type': 'ImageResource'
        })
        return serialised_data

    def deserialise_resource(self, serialised_data):
        assert serialised_data['resource_type'] == 'ImageResource'
        super().deserialise_resource(serialised_data)
        self.original_mode = serialised_data.get('original_mode')


class ImageReadHead(BaseReadHead):
    """Image read head provides access to RGBA image data.

    Can return single frames or treat the image as an infinite video
    where every frame is identical.

    Args:
        resource: The ImageResource instance to read from
    """

    def __init__(self, resource: ImageResource):
        super().__init__(resource)

    def read(self, position=None, count=None):
        """Read image data as frames.

        Args:
            position: Frame position (ignored, all frames are identical)
            count: Number of frames to return. If None or 0 or 1, returns single frame.

        Returns:
            Numpy array of RGBA image data.
            Shape is (height, width, 4) for count = None.
            Shape is (count, height, width, 4) for count >= 1.

        Raises:
            ValueError: If count is invalid (not None or >= 1)
        """
        if count is None:
            return self.resource.data

        if count < 1:
            raise ValueError(f"Count must be None or > 0: {count}")

        # Return multiple identical frames (count, height, width, 4)
        return np.repeat(self.resource.data[np.newaxis, :, :, :], count, axis=0)
