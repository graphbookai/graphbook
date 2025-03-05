import ray
from graphbook.core.shm import ImageStorageInterface
from io import BytesIO

class RayMemoryManager(ImageStorageInterface):
    """
    For retrieving images from a Ray actor.
    """
    _processor = None

    @classmethod
    def add_image(cls, pil_image):
        raise NotImplementedError(
            "RayMemoryManager doesn't support add_image. Images are stored in _graphbook_RayStepHandler Actor"
        )

    @classmethod
    def get_image(cls, image_id: str):
        if cls._processor is None:
            cls._processor = ray.get_actor("_graphbook_RayStepHandler")
        img_buffer = BytesIO()
        image = ray.get(cls._processor.get_image.remote(image_id))
        image.save(img_buffer, format=image.format or "PNG")
        return img_buffer.getvalue()
