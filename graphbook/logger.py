from typing import List, Tuple, Iterator, Union, Optional, Dict, Any
from io import BytesIO
from PIL import Image
from torch import Tensor
from torchvision.transforms.functional import to_pil_image
from pathlib import Path
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from graphbook.viewer import MultiGraphViewManagerInterface, ViewManagerInterface
from graphbook.utils import TaskLoop, transform_json_log
from graphbook.shm import MultiThreadedMemoryManager
import pyarrow as pa
import json
import struct
import queue
import asyncio
import os

LOG_SCHEMA = pa.schema([pa.field("id", pa.string()), pa.field("image", pa.binary())])
META_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("name", pa.string()),
        pa.field("back_refs", pa.list_(pa.string())),
    ]
)
METADATA_LENGTH_BYTES = 8  # Using 8 bytes for metadata length


class ImageDAGRef:
    """
    Reference to an image in a directed acyclic graph (DAG).
    """

    def __init__(
        self, id: str, name: str, stream, filepath, *back_refs: List["ImageDAGRef"]
    ):
        self.id = id
        self.name = name
        self.stream = stream
        self.filepath = filepath
        self.back_refs = back_refs
        self.bufs = []

    def log(self, pil_or_tensor: Union[Image.Image, Tensor]):
        """
        Logs an image to the DAG.
        """
        buf = BytesIO()
        if isinstance(pil_or_tensor, Image.Image):
            pil_or_tensor.save(buf, format="PNG")
        elif isinstance(pil_or_tensor, Tensor):
            pil = to_pil_image(pil_or_tensor)
            pil.save(buf, format="PNG")
        else:
            raise TypeError("Input should be a PIL Image or a Tensor.")

        self.bufs.append(buf)
        self.write_log(buf)

    def write_log(self, buf: BytesIO):
        """
        Write log records to the logs section.

        Args:
            data: List of dictionaries containing the log records
        """
        schema = LOG_SCHEMA
        # try:
        data = [{"id": self.id, "image": buf.getvalue()}]
        table = pa.Table.from_pylist(data, schema=schema)

        # # Open file in read binary mode
        # with pa.OSFile(str(self.filepath), 'rb') as f:
        #     # Read metadata length
        #     metadata_length = struct.unpack('>Q', f.read(self.METADATA_LENGTH_BYTES))[0]

        # Open file in append binary mode
        with pa.OSFile(str(self.filepath), "ab") as f:
            # Write new batch
            writer = pa.ipc.RecordBatchStreamWriter(f, schema)
            for batch in table.to_batches():
                writer.write_batch(batch)
            writer.close()
        # except Exception as e:
        #     raise RuntimeError(f"Error writing log batch: {str(e)}")


class DAGLogger:
    """
    Logs images in a directed acyclic graph (DAG) to a pyarrow format which can be read by Graphbook.
    """

    def __init__(self, name: str):
        self.name = name
        self.filepath = Path(name)
        self.nodes: List[ImageDAGRef] = []
        self.id_idx = 0
        self.stream = None
        self._initialize_file()

    def _initialize_file(self):
        """Initialize the file with initial metadata length (0) if it doesn't exist."""
        if not self.filepath.exists():
            with pa.OSFile(str(self.filepath), "wb") as f:
                # Write initial metadata length (0)
                f.write(struct.pack(">Q", 0))
                # Initialize Arrow IPC stream
                writer = pa.ipc.RecordBatchStreamWriter(f, LOG_SCHEMA)
                writer.close()

    def write_node(self, id: str, **node):
        """
        Write metadata to the first section of the file.
        Previous metadata is preserved and new metadata is appended.

        Args:
            metadata: Dictionary containing the metadata
        """
        # Read existing metadata
        current_metadata = {}
        try:
            with open(self.filepath, "rb") as f:
                metadata_length = struct.unpack(">Q", f.read(METADATA_LENGTH_BYTES))[0]
                if metadata_length > 0:
                    metadata_bytes = f.read(metadata_length)
                    current_metadata = json.loads(metadata_bytes)
        except FileNotFoundError:
            pass

        # Append new metadata
        if not isinstance(current_metadata, dict):
            current_metadata = {}
        current_metadata.update({id: node})

        # Read existing log data
        log_data = b""
        if self.filepath.exists():
            with open(self.filepath, "rb") as f:
                metadata_length = struct.unpack(">Q", f.read(METADATA_LENGTH_BYTES))[0]
                f.seek(METADATA_LENGTH_BYTES + metadata_length)
                log_data = f.read()

        # Write everything back
        with open(self.filepath, "wb") as f:
            # Convert metadata to bytes
            metadata_bytes = json.dumps(current_metadata).encode("utf-8")
            # Write metadata length
            f.write(struct.pack(">Q", len(metadata_bytes)))
            # Write metadata
            f.write(metadata_bytes)
            # Write back log data
            f.write(log_data)

    def close(self):
        """Close the stream if it's open."""
        if self.stream:
            self.stream.close()
            self.stream = None

    def node(self, name: str, *back_refs: List[ImageDAGRef]) -> ImageDAGRef:
        """
        Creates a node in the DAG ready for logging
        """
        node = ImageDAGRef(
            str(self.id_idx), name, self.stream, self.filepath, *back_refs
        )
        self.write_node(
            str(self.id_idx), name=name, back_refs=[ref.id for ref in back_refs]
        )
        self.nodes.append(node)
        self.id_idx += 1
        return node

    # def log(self, pil_or_tensor: Union[Image.Image, Tensor], *back_refs: List[ImageDAGRef]) -> ImageDAGRef:
    #     """
    #     Logs an image to the DAG.
    #     """
    #     buf = BytesIO()
    #     if isinstance(pil_or_tensor, Image.Image):
    #         pil_or_tensor.save(buf, format="PNG")
    #     elif isinstance(pil_or_tensor, Tensor):
    #         pil_or_tensor = pil_or_tensor.cpu().detach().numpy()
    #         pil_or_tensor = (pil_or_tensor * 255).astype("uint8")
    #         pil_or_tensor = Image.fromarray(pil_or_tensor)
    #         pil_or_tensor.save(buf, format="PNG")
    #     else:
    #         raise TypeError("Input should be a PIL Image or a Tensor.")

    #     ref = ImageDAGRef(buf, *back_refs)
    #     return ref


class LogFileHandler(FileSystemEventHandler):
    def __init__(self, handler: callable):
        super().__init__()
        self.handler = handler

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self.handler(event.src_path)

    def on_modified(self, event):
        return

    def on_deleted(self, event):
        return

    def on_moved(self, event):
        return


class LogDirectoryReader(TaskLoop):
    def __init__(
        self,
        log_dir: str,
        queue: queue.Queue,
        poll_interval: float = 0.1,
        close_event: Optional[asyncio.Event] = None,
    ):
        """
        Initialize a reader for the custom format file.

        Args:
            log_dir: Path to the log directory
            poll_interval: Time in seconds to wait between checking for new data
        """
        super().__init__(interval_seconds=poll_interval, close_event=close_event)
        self.log_dir = Path(log_dir)
        self.viewer_manager = MultiGraphViewManagerInterface(queue)
        self.poll_interval = poll_interval
        self.last_metadata_length = 0
        self.last_log_position = 0
        self.event_handler = LogFileHandler(self.handle_new_file)
        self.observer = Observer()
        self.readers: Dict[str, DAGStreamReader] = {}
        self.viewers: Dict[str, ViewManagerInterface] = {}

    def handle_new_file(self, filepath: Path):
        filename = filepath.name
        viewer = self.viewer_manager.new(filename)
        viewer.set_state("run_state", "initializing")
        reader = DAGStreamReader(filepath)
        self.viewers[filename] = viewer
        self.readers[filename] = reader
        print(f"Tracking new log file: {filename}")

    def initialize_files(self):
        for root, dirs, files in os.walk(self.log_dir):
            for file in files:
                self.handle_new_file(Path(root).joinpath(file))

    def start_observer(self):
        self.observer.schedule(self.event_handler, self.log_dir, recursive=True)
        self.observer.start()

    def stop_observer(self):
        self.observer.stop()
        self.observer.join()

    def metadata_to_graph(self, metadata: Dict[str, Any]):
        graph = {}
        for node_id, node in metadata.items():
            graph[node_id] = {
                "type": "step",
                "name": str(node.get("name", "")),
                "parameters": {},
                "inputs": [
                    {"node": str(ref), "pin": "out"}
                    for ref in node.get("back_refs", [])
                ],
                "outputs": ["out"],
                "category": "",
                "doc": "",
            }
        return graph

    async def loop(self):
        for graph_id, reader in self.readers.items():
            metadata, is_changed = reader.get_metadata()
            if is_changed:
                self.viewers[graph_id].set_state("run_state", "finished")
                self.viewers[graph_id].set_state(
                    "graph_state", self.metadata_to_graph(metadata)
                )
            for batch in reader.get_logs():
                id = str(batch[0][0])
                image_bytes = batch[1][0].as_py()
                image_pil = Image.open(BytesIO(image_bytes))
                image_id = MultiThreadedMemoryManager.add_image(image_pil)
                output = {"image": {"type": "image", "shm_id": image_id}}
                self.viewers[graph_id].handle_outputs(id, {"out": [output]})

    def start(self):
        self.start_observer()
        self.initialize_files()
        super().start()

    def stop(self):
        self.stop_observer()
        super().stop()


class DAGStreamReader:
    def __init__(self, filepath: str):
        """
        Initialize a reader for the custom format file.

        Args:
            filepath: Path to the log file
            poll_interval: Time in seconds to wait between checking for new data
        """
        self.filepath = Path(filepath)
        self.last_metadata_length = 0
        self.last_metadata = {}
        self.log_position = 0
        self._load_initial_state()

    def _load_initial_state(self):
        """Load initial state and schema from the file."""
        if not self.filepath.exists():
            raise FileNotFoundError(f"Log file not found: {self.filepath}")

        with open(self.filepath, "rb") as f:
            # Skip metadata section
            metadata_length = struct.unpack(">Q", f.read(METADATA_LENGTH_BYTES))[0]
            f.seek(METADATA_LENGTH_BYTES + metadata_length)
            # Read schema from Arrow IPC stream
            self.log_position = f.tell()

    def get_metadata(self) -> Tuple[Dict[str, Any], bool]:
        """
        Gets metadata section from file.

        Returns:
            Tuple of Dictionary containing metadata and changed or unchanged flag
        """
        try:
            with open(self.filepath, "rb") as f:
                metadata_length = struct.unpack(">Q", f.read(METADATA_LENGTH_BYTES))[0]
                if metadata_length != self.last_metadata_length:
                    metadata_bytes = f.read(metadata_length)
                    metadata = json.loads(metadata_bytes)
                    self.last_metadata = metadata
                    self.last_metadata_length = metadata_length
                    return metadata, True
                return self.last_metadata, False
        except Exception as e:
            raise RuntimeError(f"Error reading metadata stream: {str(e)}")

    def get_logs(self) -> Iterator[pa.RecordBatch]:
        """
        Stream log record batches as they are added.

        Yields:
            PyArrow RecordBatch objects containing the new logs
        """
        try:
            with pa.OSFile(str(self.filepath), "rb") as f:
                # Get current file size
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()

                if file_size > self.log_position:
                    # Seek to last read position
                    f.seek(self.log_position)
                    # Create arrow stream from this position
                    reader = pa.ipc.RecordBatchStreamReader(f)

                    for batch in reader:
                        yield batch

                    self.log_position = f.tell()
        except Exception as e:
            raise RuntimeError(f"Error reading log stream: {str(e)}")

    def on_log(self):
        pass

    def on_metadata(self):
        pass
