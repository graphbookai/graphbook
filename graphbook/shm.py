from multiprocessing import shared_memory, Lock, Event
import json
import uuid
from io import BytesIO


class SharedMemoryManager:
    """
    Creates a shared memory region for storing images.

    Args:
        size (int): Size of the shared memory region in MB. Default is 1024MB (1GB)
        metadata_size (int): Size of the metadata in MB. Default is 1MB
    """

    def __init__(self, size=1024, metadata_size=1, name=None, lock=None, event=None):
        mb = 1024 * 1024
        self.size = size * mb
        self.metadata_size = metadata_size * mb  # 1MB for metadata
        self.shm = (
            shared_memory.SharedMemory(name=name)
            if name
            else shared_memory.SharedMemory(create=True, size=self.size)
        )
        self.lock = lock if lock else Lock()
        self.metadata_is_updated = event if event else Event()
        self.metadata = {"images": {}, "offset": self.metadata_size}
        self.is_full = False
        self.update_metadata()

    def get_shared_args(self):
        return {
            "name": self.shm.name,
            "lock": self.lock,
            "event": self.metadata_is_updated,
        }

    def update_metadata(self):
        metadata_json = json.dumps(self.metadata).encode()
        if len(metadata_json) > self.metadata_size:
            raise ValueError("Metadata too large")
        with self.lock:
            self.shm.buf[: len(metadata_json)] = metadata_json
            self.shm.buf[len(metadata_json) : self.metadata_size] = b"\0" * (
                self.metadata_size - len(metadata_json)
            )
            self.metadata_is_updated.set()

    def load_metadata(self):
        with self.lock:
            metadata_json = (
                self.shm.buf[: self.metadata_size].tobytes().split(b"\0", 1)[0]
            )
        self.metadata = json.loads(metadata_json)

    def add_image(self, pil_image):
        if self.is_full:
            return None

        # Convert PIL Image to bytes
        img_buffer = BytesIO()
        try:
            if pil_image.format == "CMYK":
                pil_image = pil_image.convert("RGB")
            pil_image.save(img_buffer, format=pil_image.format or "PNG")
        except Exception as e:
            print(f"Error saving image: {e}\n{pil_image}")
            return None

        img_bytes = img_buffer.getvalue()
        img_size = len(img_bytes)

        # Find space for the new image
        offset = self.metadata["offset"]

        if offset + img_size > self.size:
            self.is_full = True
            print(
                "Shared memory is full. Will no longer store images for rendering. Consider increasing the size with --img_shm_size"
            )
            return None

        # Store the image
        with self.lock:
            self.shm.buf[offset : offset + img_size] = img_bytes

        # Update metadata
        image_id = str(uuid.uuid4())
        self.metadata["images"][image_id] = (offset, img_size)
        self.metadata["offset"] += img_size
        self.update_metadata()
        return image_id

    def get_image(self, image_id):
        if self.metadata_is_updated.is_set():
            self.load_metadata()
            self.metadata_is_updated.clear()
        if image_id not in self.metadata["images"]:
            return None
        offset, size = self.metadata["images"][image_id]
        with self.lock:
            img_bytes = self.shm.buf[offset : offset + size].tobytes()
        return BytesIO(img_bytes).getvalue()

    def close(self):
        self.shm.close()
        self.shm.unlink()
