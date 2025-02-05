from typing import List, Tuple, Iterator, Union, Optional, Dict, Any
from io import BufferedReader, BytesIO
from PIL import Image
from torch import Tensor
from torchvision.transforms.functional import to_pil_image
from pathlib import Path
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from graphbook.viewer import MultiGraphViewManagerInterface, ViewManagerInterface
from graphbook.utils import TaskLoop, transform_json_log
from graphbook.shm import MultiThreadedMemoryManager
from graphbook.steps import StepOutput as Outputs
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
MARKER = b"GRAPHBOOK"
VERSION = 0


"""
Log files are stored in a custom format that can be read by Graphbook.
They combine information about the DAG in the first section (metadata) and the logs in the second section (Arrow IPC stream).

Log file format:
- Marker: GRAPHBOOK
- First byte: Version
- Next 8 bytes: Metadata length
- Next N bytes: Metadata (JSON)
- Next M bytes: Arrow IPC stream

"""


def _check_file(f: BufferedReader):
    """Check if the file is in the correct format."""
    marker = f.read(len(MARKER))
    if marker != MARKER:
        raise ValueError("Invalid file format. Not a Graphbook log file.")

    version = struct.unpack(">B", f.read(1))[0]
    if version != VERSION:
        raise ValueError(
            f"Invalid file version. Expected version {VERSION}. Instead, got {version}."
        )

    new_loc = f.tell()
    f.seek(0)
    return new_loc


class ImageDAGRef:
    """
    Reference to an image in a directed acyclic graph (DAG).
    """

    def __init__(
        self, id: str, name: str, filepath: Path, *back_refs: List["ImageDAGRef"]
    ):
        self.id = id
        self.name = name
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
        data = [{"id": self.id, "image": buf.getvalue()}]
        table = pa.Table.from_pylist(data, schema=schema)

        # Open file in append binary mode
        with pa.OSFile(str(self.filepath), "ab") as f:
            # Write new batch
            writer = pa.ipc.RecordBatchStreamWriter(f, schema)
            for batch in table.to_batches():
                writer.write_batch(batch)
            writer.close()


class DAGLogger:
    """
    Logs images in a directed acyclic graph (DAG) to a pyarrow format which can be read by Graphbook.
    """

    def __init__(self, name: str, log_dir: Optional[str] = "logs"):
        self.name = name
        self.log_dir = Path(log_dir)
        self.filepath = self.log_dir / Path(name + ".log")
        self.nodes: List[ImageDAGRef] = []
        self.id_idx = 0
        self._initialize_file()

    def _initialize_file(self):
        """Initialize the file with initial metadata length (0) if it doesn't exist."""
        if not self.log_dir.exists():
            os.mkdir(self.log_dir)
        elif not self.log_dir.is_dir():
            raise ValueError(
                "Directory chosen is not a directory. Will fail to write logs."
            )

        if not self.filepath.exists():
            with pa.OSFile(str(self.filepath), "wb") as f:
                f.write(struct.pack(f">{len(MARKER)}s", MARKER))
                f.write(struct.pack(">B", VERSION))
                f.write(struct.pack(">Q", 0))  # Metadata length
                # Initialize Arrow IPC stream
                writer = pa.ipc.RecordBatchStreamWriter(f, LOG_SCHEMA)
                writer.close()

    def _write_node(self, id: str, **node):
        """
        Write metadata to the first section of the file.
        Previous metadata is preserved and new metadata is appended.

        Args:
            metadata: Dictionary containing the metadata
        """
        # Read existing metadata
        current_metadata = {}
        with open(self.filepath, "rb") as f:
            length_loc = _check_file(f)

            f.seek(length_loc)
            metadata_length = struct.unpack(">Q", f.read(METADATA_LENGTH_BYTES))[0]
            if metadata_length > 0:
                metadata_bytes = f.read(metadata_length)
                current_metadata = json.loads(metadata_bytes)

        # Append new metadata
        if not isinstance(current_metadata, dict):
            current_metadata = {}
        current_metadata.update({id: node})

        # Read existing log data
        log_data = b""
        if self.filepath.exists():
            with open(self.filepath, "rb") as f:
                f.seek(length_loc + METADATA_LENGTH_BYTES + metadata_length)
                log_data = f.read()

        # Write everything back
        with open(self.filepath, "wb") as f:
            f.write(struct.pack(f">{len(MARKER)}s", MARKER))
            f.write(struct.pack(">B", VERSION))
            metadata_bytes = json.dumps(current_metadata).encode("utf-8")
            f.write(struct.pack(">Q", len(metadata_bytes)))
            f.write(metadata_bytes)
            f.write(log_data)

    def node(self, name: str, *back_refs: List[ImageDAGRef]) -> ImageDAGRef:
        """
        Creates a node in the DAG ready for logging
        """
        node = ImageDAGRef(str(self.id_idx), name, self.filepath, *back_refs)
        self._write_node(
            str(self.id_idx), name=name, back_refs=[ref.id for ref in back_refs]
        )
        self.nodes.append(node)
        self.id_idx += 1
        return node


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


class LogStates:
    def __init__(self, viewer: ViewManagerInterface):
        self.steps_outputs: Dict[str, list] = {}
        self.viewer = viewer

    def update_nodes_from_graph(self, graph: Dict[str, Any]):
        for step_id in graph:
            if step_id not in self.steps_outputs:
                self.steps_outputs[step_id] = []
                self.viewer.handle_queue_size(step_id, {"out": 0})

    def handle_outputs(self, step_id: str, outputs: Outputs):
        assert step_id in self.steps_outputs, f"Step {step_id} not initialized"
        assert self.viewer is not None, "Viewer not initialized"

        # Converts multi-output into single output nodes with label "out"
        self.steps_outputs[step_id].extend(outputs["out"])

        self.viewer.handle_queue_size(
            step_id, {"out": len(self.steps_outputs[step_id])}
        )
        outputs = transform_json_log(outputs)
        self.viewer.handle_outputs(step_id, outputs)


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
            queue: Queue to send data to the viewer
            poll_interval: Time in seconds to wait between checking for new data
            close_event: Event to signal when to stop the task loop
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
        self.states: Dict[str, LogStates] = {}

    def handle_new_file(self, filepath: Path):
        if not filepath.suffix == ".log":
            return
        filename = filepath.name
        viewer = self.viewer_manager.new(filename)
        viewer.set_state("run_state", "initializing")
        reader = DAGStreamReader(filepath)
        self.viewers[filename] = viewer
        self.readers[filename] = reader
        self.states[filename] = LogStates(viewer)
        print(f"Tracking new log file: {filename}")

    def initialize_files(self):
        if not self.log_dir.exists():
            os.mkdir(self.log_dir)
        elif not self.log_dir.is_dir():
            raise ValueError(
                "Directory chosen is not a directory. Will fail to read logs."
            )

        for root, _, files in os.walk(self.log_dir):
            for file in files:
                self.handle_new_file(Path(root).joinpath(file))

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
                "default_tab": "Images",
            }
        return graph

    async def loop(self):
        for graph_id, reader in self.readers.items():
            metadata, is_changed = reader.get_metadata()
            if is_changed:
                G = self.metadata_to_graph(metadata)
                self.viewers[graph_id].set_state("run_state", "finished")
                self.viewers[graph_id].set_state("graph_state", G)
                self.states[graph_id].update_nodes_from_graph(G)
            for batch in reader.get_logs():
                id = str(batch[0][0])
                image_bytes = batch[1][0].as_py()
                image_pil = Image.open(BytesIO(image_bytes))
                image_id = MultiThreadedMemoryManager.add_image(image_pil)
                output = {"image": {"type": "image", "shm_id": image_id}}
                self.states[graph_id].handle_outputs(id, {"out": [output]})

    def start(self):
        self.initialize_files()
        self.observer.schedule(self.event_handler, self.log_dir, recursive=True)
        self.observer.start()
        super().start()

    def stop(self):
        self.observer.stop()
        self.observer.join()
        super().stop()
        
    def get_output_note(self, graph_id, step_id, pin_id, index):
        return {
            "step_id": step_id,
            "pin_id": pin_id,
            "index": index,
            "data": transform_json_log(
                self.states[graph_id].steps_outputs[step_id][index]
            ),
        }

class DAGStreamReader:
    def __init__(self, filepath: str):
        """
        Initialize a reader for the custom format file.

        Args:
            filepath: Path to the log file
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
            len_loc = _check_file(f)
            f.seek(len_loc)
            metadata_length = struct.unpack(">Q", f.read(METADATA_LENGTH_BYTES))[0]
            self.log_position = len_loc + METADATA_LENGTH_BYTES + metadata_length

    def get_metadata(self) -> Tuple[Dict[str, Any], bool]:
        """
        Gets metadata section from file.

        Returns:
            Tuple of Dictionary containing metadata and changed/unchanged flag
        """
        try:
            with open(self.filepath, "rb") as f:
                len_loc = _check_file(f)
                f.seek(len_loc)
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

                if self.log_position < file_size:
                    f.seek(self.log_position)

                    while self.log_position < file_size:
                        reader = pa.ipc.RecordBatchStreamReader(f)
                        for batch in reader:
                            yield batch
                        self.log_position = f.tell()
        except Exception as e:
            raise RuntimeError(f"Error reading log stream: {str(e)}")
