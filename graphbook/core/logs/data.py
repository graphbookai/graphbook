"""
Unified logging implementation for Graphbook.

This module provides a simplified, unified logging system that:
1. Uses msgpack and cloudpickle for serialization
2. Stores graph metadata and images in a single log file
"""

from typing import Dict, List, Any, Optional, Union, Tuple, BinaryIO, Callable
from pathlib import Path
import os
import os.path as osp
import msgpack
import cloudpickle
import time
import threading
import atexit
import io
import struct
from enum import Enum, auto
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from PIL import Image

from graphbook.core.viewer import MultiGraphViewManagerInterface, ViewManagerInterface
from graphbook.core.utils import transform_json_log, TaskLoop
from graphbook.core.shm import MultiThreadedMemoryManager
from multiprocessing import Lock, Queue
from multiprocessing.synchronize import Event as MPEvent

MARKER = b"GRAPHBOOK"
VERSION = 1


class InvalidFileFormatError(Exception):
    pass


class StreamUnreadyError(Exception):
    pass


def is_s3_url(path_str: str) -> bool:
    """Check if a string is an S3 URL.

    Args:
        path_str: String to check

    Returns:
        True if the string is an S3 URL, False otherwise
    """
    if isinstance(path_str, str):
        if path_str.startswith("s3://"):
            return True
        if path_str.startswith("https://") and ".s3." in path_str:
            return True
    return False


def parse_s3_url(url: str) -> tuple:
    """Parse an S3 URL into bucket and key.

    Args:
        url: S3 URL to parse

    Returns:
        Tuple of (bucket, key)
    """
    if url.startswith("s3://"):
        parts = url[5:].split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        return bucket, key

    # Handle https URLs
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if ".s3." in parsed.netloc:
        bucket = parsed.netloc.split(".s3.")[0]
        key = parsed.path.lstrip("/")
        return bucket, key

    raise ValueError(f"Invalid S3 URL: {url}")


def _check_file(f: io.BufferedReader):
    """Check if the file is in the correct format."""
    marker = f.read(len(MARKER))
    if marker != MARKER:
        raise InvalidFileFormatError("Invalid file format. Not a Graphbook log file.")

    version = struct.unpack(">B", f.read(1))[0]
    if version != VERSION:
        if version < VERSION:
            raise InvalidFileFormatError(
                f"Graphbook does not support version {version} log files anymore. If you want to keep using this log file, please use an older version of Graphbook."
            )
        raise InvalidFileFormatError(
            f"Invalid file version. Expected version {VERSION}. Instead, got {version}."
        )

    new_loc = f.tell()
    f.seek(0)
    return new_loc


class S3Writer:
    """
    Writer for S3 destinations.
    """

    def __init__(self, s3_url: str):
        """
        Initialize the S3 writer.

        Args:
            s3_url: S3 URL to write to
        """
        # Check if boto3 is available
        try:
            import s3fs
        except ImportError:
            raise ImportError(
                "s3fs is required for S3 support. Install with 'pip install s3fs'"
            )

        self.s3_url = s3_url
        self.bucket_name, self.key = parse_s3_url(s3_url)
        self.s3_client = s3fs.S3FileSystem(anon=False)
        self.buffer = io.BytesIO()
        self.closed = False

    def write(self, data: bytes):
        """Write data to the buffer."""
        self.buffer.write(data)

    def flush(self):
        """Flush the buffer to S3."""
        if self.closed:
            return

        # Reset buffer position to start
        self.buffer.seek(0)

        # Upload to S3
        try:
            with self.s3_client.open(self.s3_url, "wb") as f:
                f.write(self.buffer.read())
            print(f"Uploaded to S3: {self.s3_url}")
        except Exception as e:
            print(f"Error uploading to S3: {str(e)}")

    def tell(self):
        """Get the current position in the buffer."""
        if self.buffer.closed:
            self._renew_buffer()
            
        return self.buffer.tell()

    def close(self):
        """Flush and close the buffer."""
        print("!!!!!!Closing S3Writer!!!!!!")
        if not self.closed:
            self.flush()
            self.buffer.close()
            self.closed = True
            
    def _renew_buffer(self):
        old_buffer = self.buffer
        self.buffer = io.BytesIO()
        old_buffer.seek(0)
        self.buffer.write(old_buffer.read())


class LogEntryType(Enum):
    """Type of log entry for log file."""

    META = auto()  # Graph structure metadata
    IMAGE = auto()  # Image data entry
    LOG = auto()  # Text log entry
    OUTPUT = auto()  # General output data


class LogWriter:
    """
    Writer for the log file format.

    This class serializes graph metadata, images, and logs using msgpack and cloudpickle,
    writing them to a log file for later retrieval.
    """

    def __init__(self, log_file_path: str):
        """
        Initialize the log writer.

        Args:
            log_file_path: Path to the log file (can be a local path or an S3 URL)
        """
        print("logwriter", log_file_path)
        self.is_s3 = is_s3_url(log_file_path)
        self.log_file_path = log_file_path

        # Check if it's an S3 URL
        if self.is_s3:
            self.file = S3Writer(self.log_file_path)
        else:
            pth = Path(self.log_file_path)
            # Create the directory if it doesn't exist
            os.makedirs(pth.parent, exist_ok=True)

            # Open the file and write the header
            if pth.exists():
                print(
                    f"Warning: Log file already exists: {self.log_file_path}. Overwriting contents."
                )

            self.file = open(self.log_file_path, "wb")

        self.lock = threading.Lock()
        self.metadata = {}  # Graph structure metadata

        self._write_header()

        # Register cleanup
        atexit.register(self.close)

    def _write_header(self):
        """Write the log file header."""
        self.file.write(struct.pack(f">{len(MARKER)}s", MARKER))
        self.file.write(struct.pack(">B", VERSION))

    def _write_entry(self, entry_type: LogEntryType, data: Any):
        """
        Write an entry to the log file.

        Args:
            entry_type: Type of log entry
            data: Data to write

        Returns:
            Position in the file where the entry was written
        """
        # Get current position for indexing
        position = self.file.tell()

        # Serialize the data
        serialized_data = cloudpickle.dumps(data)

        # Create and serialize the entry directly
        entry = {
            "type": entry_type.value,
            "timestamp": time.time(),
            "data": serialized_data,
        }

        # Let MessagePack handle all the length encoding
        self.file.write(msgpack.packb(entry, use_bin_type=True))
        self.file.flush()

        return position

    def update_metadata(self, metadata: Dict[str, Any]):
        """
        Update the graph structure metadata.

        Args:
            metadata: Dict containing graph structure information
        """
        with self.lock:
            self.metadata.update(metadata)
            self._write_entry(LogEntryType.META, self.metadata)

    def write_image(self, node_id: str, image: Image.Image):
        """
        Write an image to the log file.

        Args:
            node_id: ID of the node that generated the image
            image: PIL Image to log
        """
        if not isinstance(image, Image.Image):
            raise TypeError("Input should be a PIL Image.")

        with self.lock:
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            entry_data = {"node_id": node_id, "image": buffer.getvalue()}
            self._write_entry(LogEntryType.IMAGE, entry_data)

    def write_output(self, step_id: str, pin_id: str, output: Any):
        """
        Write a step output to the log file.

        Args:
            step_id: ID of the step
            pin_id: ID of the output pin
            output: Output data
        """
        with self.lock:
            entry_data = {
                "step_id": step_id,
                "pin_id": pin_id,
                "output": output,
            }
            self._write_entry(LogEntryType.OUTPUT, entry_data)

    def write_log(self, step_id: str, message: str, log_type: str = "info"):
        """
        Write a log entry to the log file.

        Args:
            step_id: ID of the step
            message: Log message
            log_type: Type of log (info, warning, error)
        """
        with self.lock:
            entry_data = {
                "step_id": step_id,
                "message": message,
                "type": log_type,
            }
            self._write_entry(LogEntryType.LOG, entry_data)

    def flush(self):
        """Flush the buffer to disk."""
        with self.lock:
            self.file.flush()

    def close(self):
        """Close the log file."""
        if hasattr(self, "file"):
            if self.is_s3:
                if not getattr(self.file, "closed", False):
                    self.flush()
                    self.file.close()
            elif not self.file.closed:
                self.flush()
                self.file.close()
            # Unregister atexit handler
            atexit.unregister(self.close)


class LogFileHandler(FileSystemEventHandler):
    """Handle file system events for log files."""

    def __init__(self, handler: Callable, on_delete: Callable):
        super().__init__()
        self.handler = handler
        self.on_delete = on_delete

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self.handler(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        self.on_delete(event.src_path)

    def on_modified(self, event):
        return

    def on_moved(self, event):
        return


class LogWatcher:
    """
    Watches a log file and streams data to the viewer.

    This class monitors a log file in real-time and sends updates
    to the viewer for displaying logs, outputs, and images.
    """

    def __init__(
        self,
        graph_id: str,
        log_file_path: Union[str, Path],
        viewer_interface: ViewManagerInterface,
    ):
        """
        Initialize the log watcher.

        Args:
            graph_id: ID of the graph
            log_file_path: Path to the log file
            viewer_interface: Interface to the viewer
        """
        self.graph_id = graph_id
        self.log_file_path = Path(log_file_path)
        self.viewer = viewer_interface
        self.stop_event = threading.Event()
        # (step_id, pin_id) -> latest output
        self.latest_outputs: Dict[Tuple[str, str], Any] = {}
        # (step_id, pin_id) -> list of all outputs
        self.all_outputs: Dict[Tuple[str, str], List[Any]] = {}
        self.outputs_updated = False
        self.latest_metadata = {}  # Latest graph metadata
        self.watch_thread = None
        self.last_position = 0
        self.pin_output_counts = {}  # Maps (step_id, pin_id) to count
        self.file_initialized = False

    def start(self):
        """Start watching the log file."""
        if self.watch_thread is not None and self.watch_thread.is_alive():
            return

        self.stop_event.clear()
        self.watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watch_thread.start()

    def stop(self):
        """Stop watching the log file."""
        if self.watch_thread is not None:
            self.stop_event.set()
            self.watch_thread.join(timeout=1.0)
            self.watch_thread = None

    def _watch_loop(self):
        """Main watch loop that monitors the log file for changes."""
        # Wait for the log file to be created if it doesn't exist yet
        while not self.log_file_path.exists() and not self.stop_event.is_set():
            time.sleep(0.1)

        # Open the file for reading
        with open(self.log_file_path, "rb") as file:
            # Main monitoring loop
            while not self.stop_event.is_set():
                # Check if there's new data
                current_size = self.log_file_path.stat().st_size
                if current_size > self.last_position:
                    if self.file_initialized:
                        # Reset the outputs updated flag
                        self.outputs_updated = False

                        # Move to the last position we read
                        file.seek(self.last_position)

                        # Read new entries
                        self._process_new_entries(file)

                        # Update last position
                        self.last_position = file.tell()

                        # Update the viewer with the latest metadata if available
                        if self.latest_metadata and "graph" in self.latest_metadata:
                            self.viewer.set_state(
                                "graph_state", self.latest_metadata["graph"]
                            )

                        # Update the viewer with the latest outputs
                        if self.outputs_updated:
                            for (
                                step_id,
                                pin_id,
                            ), output in self.latest_outputs.items():
                                self.viewer.handle_output(step_id, pin_id, output)
                            # Clear latest outputs after sending to viewer
                            self.latest_outputs = {}
                    else:
                        try:
                            self.last_position = _check_file(file)
                            self.file_initialized = True
                        except InvalidFileFormatError as e:
                            print(f"{self.log_file_path}: {str(e)}")
                            self.stop_event.set()

                # Sleep briefly before checking again
                time.sleep(0.1)

    def _process_new_entries(self, file: BinaryIO):
        """Process new entries in the log file."""
        # Create an unpacker that reads directly from the file
        unpacker = msgpack.Unpacker(file, raw=False)

        for entry in unpacker:
            # Process the entry based on its type
            if entry["type"] == LogEntryType.META.value:
                self._handle_meta_entry(entry["data"])
            elif entry["type"] == LogEntryType.IMAGE.value:
                self._handle_image_entry(entry["data"])
            elif entry["type"] == LogEntryType.OUTPUT.value:
                self._handle_output_entry(entry["data"])
            elif entry["type"] == LogEntryType.LOG.value:
                self._handle_log_entry(entry["data"])
            else:
                print(f"Unknown entry type: {entry['type']}")

    def _handle_meta_entry(self, data):
        """Handle a metadata entry from the log file."""
        data = cloudpickle.loads(data)
        if data and isinstance(data, dict):
            self.latest_metadata = data
            if "graph" in data:
                # Set the graph state for viewing
                self.viewer.set_state("run_state", "finished")
                self.viewer.set_state("graph_state", data["graph"])

    def _handle_image_entry(self, data):
        """Handle an image entry from the log file."""
        data = cloudpickle.loads(data)
        node_id = data["node_id"]
        image_bytes = data["image"]

        try:
            image_pil = Image.open(io.BytesIO(image_bytes))
            image_id = MultiThreadedMemoryManager.add_image(image_pil)

            # Create the output with an image reference
            output = {"image": {"type": "image", "shm_id": image_id}}

            # Store as an output with pin_id "out" for compatibility with viewer
            key = (node_id, "out")
            self.latest_outputs[key] = output
            self.outputs_updated = True

            # Track all outputs
            if key not in self.all_outputs:
                self.all_outputs[key] = []
            self.all_outputs[key].append(output)

            # Update output count
            count = self.pin_output_counts.get(key, 0) + 1
            self.pin_output_counts[key] = count

            # Update queue size for the viewer
            self.viewer.handle_queue_size(node_id, {"out": count})
        except Exception as e:
            print(f"Error processing image: {str(e)}")

    def _handle_output_entry(self, data):
        """Handle an output entry from the log file."""
        data = cloudpickle.loads(data)
        step_id = data["step_id"]
        pin_id = data["pin_id"]
        output = data["output"]

        # Store the latest output value for this pin
        key = (step_id, pin_id)
        self.latest_outputs[key] = output
        self.outputs_updated = True

        # Store all outputs for this pin
        if key not in self.all_outputs:
            self.all_outputs[key] = []
        self.all_outputs[key].append(output)

        # Update pin output counts
        count = self.pin_output_counts.get(key, 0) + 1
        self.pin_output_counts[key] = count

        # Update the queue size
        sizes = {}
        for (s_id, p_id), count in self.pin_output_counts.items():
            if s_id == step_id:
                sizes[p_id] = count

        if sizes:
            self.viewer.handle_queue_size(step_id, sizes)

    def _handle_log_entry(self, data):
        """Handle a log entry from the log file."""
        data = cloudpickle.loads(data)
        step_id = data["step_id"]
        message = data["message"]
        log_type = data["type"]

        # Update the viewer with the log
        self.viewer.handle_log(step_id, message, log_type)

    def get_output(self, step_id: str, pin_id: str, index: int) -> Optional[Any]:
        """Get the output for a step and pin at a specific index."""
        key = (step_id, pin_id)
        if key in self.all_outputs and index < len(self.all_outputs[key]):
            return transform_json_log(self.all_outputs[key][index])
        return None


class LogDirectoryReader(TaskLoop):
    """Watches a directory for log files and manages their watchers."""

    def __init__(
        self,
        log_dir: str,
        queue: Queue,
        poll_interval: float = 0.1,
        close_event: Optional[MPEvent] = None,
    ):
        """
        Initialize the log directory reader.

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
        self.event_handler = LogFileHandler(
            self.handle_new_file, self.handle_deleted_file
        )
        self.observer = Observer()
        self.watchers: Dict[str, LogWatcher] = {}
        self.viewers: Dict[str, ViewManagerInterface] = {}

    def handle_new_file(self, filepath: str):
        """Handle a new log file being created."""
        filepath: Path = Path(filepath)
        if filepath.suffix != ".log":
            return

        filename = filepath.name
        viewer = self.viewer_manager.new(filename)
        viewer.set_state("run_state", "finished")

        watcher = LogWatcher(filename, filepath, viewer)
        self.viewers[filename] = viewer
        self.watchers[filename] = watcher
        watcher.start()

        print(f"Tracking new log file: {filename}")

    def handle_deleted_file(self, filepath: str):
        """Handle a log file being deleted."""
        filename = Path(filepath).stem
        if filename in self.watchers:
            self.watchers[filename].stop()
            del self.watchers[filename]
            del self.viewers[filename]
            print(f"Stopped tracking log file: {filename}")

    def initialize_files(self):
        """Initialize tracking for all log files in the directory."""
        if not self.log_dir.exists():
            os.mkdir(self.log_dir)
        elif not self.log_dir.is_dir():
            raise ValueError(
                "Directory chosen is not a directory. Will fail to read logs."
            )

        for root, _, files in os.walk(self.log_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix == ".log":
                    self.handle_new_file(str(file_path))

    async def loop(self):
        """Check for updates in watched log files."""
        # Nothing to do here, watchers handle their own updates
        pass

    def start(self):
        """Start watching the log directory."""
        self.initialize_files()
        self.observer.schedule(self.event_handler, self.log_dir, recursive=True)
        self.observer.start()
        super().start()

    def stop(self):
        """Stop watching the log directory and all log files."""
        # Stop all watchers
        for watcher in self.watchers.values():
            watcher.stop()

        # Stop the file system observer
        self.observer.stop()
        self.observer.join()

        # Stop the task loop
        super().stop()

    def get_output(
        self, graph_id: str, step_id: str, pin_id: str, index: int
    ) -> Optional[Any]:
        """Get an output from a specific log file."""
        if graph_id in self.watchers:
            output = self.watchers[graph_id].get_output(step_id, pin_id, index)
            return {
                "step_id": step_id,
                "pin_id": pin_id,
                "index": index,
                "data": transform_json_log(output),
            }
        return None


class LogManager:
    """
    Manager for log files.

    This class maintains a mapping of graph IDs to log files and watchers.
    """

    def __init__(self, log_dir: str = "logs"):
        """
        Initialize the log manager.

        Args:
            log_dir: Directory to store log files (can be a local path or an S3 URL)
        """
        self.is_s3 = is_s3_url(log_dir)
        self.log_dir = log_dir
        
        if not self.is_s3:
            os.makedirs(self.log_dir, exist_ok=True)

        self.writers: Dict[str, LogWriter] = {}
        self.watchers: Dict[str, LogWatcher] = {}
        self.lock = threading.Lock()

        # Register cleanup
        atexit.register(self.close)

    def get_writer(self, graph_id: str) -> LogWriter:
        """
        Get or create a writer for a graph.

        Args:
            graph_id: ID of the graph

        Returns:
            The log writer
        """
        with self.lock:
            if graph_id not in self.writers:
                log_file_path = osp.join(self.log_dir, f"{graph_id}.log")
                self.writers[graph_id] = LogWriter(log_file_path)

            return self.writers[graph_id]

    def get_watcher(self, graph_id: str) -> Optional[LogWatcher]:
        """
        Get a watcher for a graph.

        Args:
            graph_id: ID of the graph

        Returns:
            The log watcher or None if no log exists
        """
        return self.watchers.get(graph_id)

    def create_watcher(
        self, graph_id: str, viewer_interface: ViewManagerInterface
    ) -> LogWatcher:
        """
        Create a log watcher for a graph.

        Args:
            graph_id: ID of the graph
            viewer_interface: Interface to the viewer

        Returns:
            The log watcher
        """
        with self.lock:
            # Stop existing watcher if any
            if graph_id in self.watchers:
                self.watchers[graph_id].stop()

            log_file_path = Path(self.log_dir) / f"{graph_id}.log"

            watcher = LogWatcher(graph_id, log_file_path, viewer_interface)
            self.watchers[graph_id] = watcher
            watcher.start()

            return watcher

    def stop_watcher(self, graph_id: str):
        """
        Stop a log watcher for a graph.

        Args:
            graph_id: ID of the graph
        """
        with self.lock:
            if graph_id in self.watchers:
                self.watchers[graph_id].stop()
                del self.watchers[graph_id]

    def close(self):
        """Close all log files and stop all watchers."""
        with self.lock:
            # Stop all watchers
            for watcher in self.watchers.values():
                watcher.stop()
            self.watchers.clear()

            # Close all writers
            for writer in self.writers.values():
                writer.close()

            # Unregister atexit handler
            atexit.unregister(self.close)


class DAGNodeRef:
    """
    Reference to a DAG node capable of logging images.
    You should not create this directly, but instead use the :meth:`graphbook.logging.DAGLogger.node` to create one.

    Args:
        id: Unique identifier for the node
        logger: Owner DAGLogger instance
    """

    def __init__(
        self,
        id: str,
        logger: "DAGLogger",
    ):
        self.id = id
        self.logger = logger

    def log_image(self, image: Image.Image):
        """
        Logs an image to the DAG.

        Args:
            pil_or_tensor: PIL Image
        """
        self.logger.log_image(self.id, image)

    def log_output(self, output: Any, pin_id: str = "out"):
        """
        Logs an output to the DAG.

        Args:
            output: Output data
            pin_id: ID of the output pin
        """
        self.logger.log_output(self.id, output, pin_id)

    def log_message(self, message: str, log_type: str = "info"):
        """
        Logs a message to the DAG.

        Args:
            message: Log message
            log_type: Type of log (info, warning, error)
        """
        self.logger.log_message(self.id, message, log_type)


class DAGLogger:
    """
    Logger for both code execution and image logging.

    This class provides a single interface for logging both general outputs
    and images in a directed acyclic graph (DAG).
    """

    def __init__(self, name: Optional[str] = None, log_dir: Optional[str] = "logs"):
        """
        Initialize the logger.

        Args:
            name: Name of the log file (without extension)
            log_dir: Directory to store log files
        """
        if name is None:
            name = str(uuid.uuid4())

        self.name = name
        self.log_dir = Path(log_dir)
        self.filepath = self.log_dir / f"{name}.log"
        self.lock = Lock()
        self.writer = LogWriter(self.filepath)
        self.nodes: Dict[str, Dict] = {}
        self.id_idx = 0

    def update_graph(self, graph: Dict[str, Any]):
        """
        Update the graph structure metadata.

        Args:
            graph: Dict containing the graph structure
        """
        self.writer.update_metadata({"graph": graph})

    def node(self, id: str, name: str, doc: str = "", back_refs: List[str] = None):
        """
        Register a node in the graph.

        Args:
            id: ID of the node
            name: Name of the node
            doc: Documentation for the node
            back_refs: List of IDs of nodes that this node depends on

        Returns:
            The ID of the node for future reference
        """
        if back_refs is None:
            back_refs = []

        node_data = {"id": id, "name": name, "doc": doc, "back_refs": back_refs}

        self.nodes[id] = node_data

        # Update the graph metadata
        graph = self._build_graph_from_nodes()
        self.writer.update_metadata({"graph": graph})

        return DAGNodeRef(id, self)

    def log_image(self, node_id: str, image: Image.Image):
        """
        Log an image for a specific node.

        Args:
            node_id: ID of the node
            image: PIL Image to log
        """
        self.writer.write_image(node_id, image)

    def log_output(self, node_id: str, output: Any, pin_id: str = "out"):
        """
        Log an output for a specific node.

        Args:
            node_id: ID of the node
            output: Any output data to log
            pin_id: ID of the output pin (defaults to "out")
        """
        self.writer.write_output(node_id, pin_id, output)

    def log_message(self, node_id: str, message: str, log_type: str = "info"):
        """
        Log a message for a specific node.

        Args:
            node_id: ID of the node
            message: Message to log
            log_type: Type of log (info, warning, error)
        """
        self.writer.write_log(node_id, message, log_type)

    def _build_graph_from_nodes(self) -> Dict[str, Any]:
        """Build a graph structure dictionary from the registered nodes."""
        graph = {}

        for node_id, node_data in self.nodes.items():
            graph[node_id] = {
                "type": "step",
                "name": node_data["name"],
                "parameters": {},
                "inputs": [
                    {"node": str(ref), "pin": "out"}
                    for ref in node_data.get("back_refs", [])
                ],
                "outputs": ["out"],
                "category": "",
                "doc": node_data.get("doc", ""),
                "default_tab": "Images",
            }

        return graph

    def close(self):
        """Close the log file."""
        self.writer.close()


class CallableNode(Callable):
    def __init__(self, ref: DAGNodeRef, log_every: int = 1):
        self.ref = ref
        self.log_every = log_every
        self.counter = 0

    def __call__(self, input):
        if self.counter % self.log_every == 0:
            self.ref.log_image(input)
        self.counter += 1
        return input
