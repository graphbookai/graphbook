from typing import Dict, List, Any, Optional, Union, Tuple, BinaryIO
import os
import msgpack
import cloudpickle
import time
import threading
import tempfile
from pathlib import Path
import atexit
import uuid
from enum import Enum, auto
from graphbook.core.viewer import ViewManagerInterface


class LogEntryType(Enum):
    """Type of log entry for the output log file."""
    META = auto()
    OUTPUT = auto()
    LOG = auto()


class OutputLogWriter:
    """
    Writer for the output log file format.
    
    This class serializes step outputs and logs using msgpack and cloudpickle,
    writing them to a log file for later retrieval.
    """
    
    def __init__(self, log_file_path: Union[str, Path], max_buffer_size: int = 50):
        """
        Initialize the output log writer.
        
        Args:
            log_file_path: Path to the log file
            max_buffer_size: Maximum number of entries to buffer before writing to disk
        """
        self.log_file_path = Path(log_file_path)
        self.max_buffer_size = max_buffer_size
        self.buffer = []
        self.lock = threading.Lock()
        self.index = {}  # Maps (step_id, pin_id, index) to file position
        self.log_index = {}  # Maps (step_id, log_index) to file position
        self.pin_index = {}  # Maps (step_id, pin_id) to list of output indices
        
        # Create the directory if it doesn't exist
        os.makedirs(self.log_file_path.parent, exist_ok=True)
        
        # Open the file and write the header
        if self.log_file_path.exists():
            print(f"Warning: Log file already exists: {self.log_file_path}. Overwriting contents.")
            self.file.truncate(0)
            
        self.file = open(self.log_file_path, 'wb')
        self._write_header()
        
        # Register cleanup
        atexit.register(self.close)
    
    def _write_header(self):
        """Write the log file header."""
        header = {
            'format': 'graphbook-output-log',
            'version': '0',
        }
        self._write_entry(LogEntryType.META, header)
    
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
            'type': entry_type.value,
            'timestamp': time.time(),
            'data': serialized_data
        }
        
        # Let MessagePack handle all the length encoding
        self.file.write(msgpack.packb(entry, use_bin_type=True))
        self.file.flush()
        
        position = self.file.tell()
        
        return position
    
    def write_output(self, step_id: str, pin_id: str, output: Any):
        """
        Write a step output to the log file.
        
        Args:
            step_id: ID of the step
            pin_id: ID of the output pin
            output: Output data
        """
        with self.lock:
            pin_index = self.pin_index.get((step_id, pin_id), 0)
            entry_data = {
                'step_id': step_id,
                'pin_id': pin_id,
                'index': pin_index,
                'output': output,
            }
            position = self._write_entry(LogEntryType.OUTPUT, entry_data)
            self.index[(step_id, pin_id, pin_index)] = position
            self.pin_index[(step_id, pin_id)] = pin_index + 1

    def write_log(self, step_id: str, message: str, log_type: str = "info"):
        """
        Write a log entry to the log file.
        
        Args:
            step_id: ID of the step
            message: Log message
            log_type: Type of log (info, warning, error)
        """
        with self.lock:
            log_index = len(self.log_index.get(step_id, []))
            entry_data = {
                'step_id': step_id,
                'message': message,
                'type': log_type,
                'index': log_index,
            }
            position = self._write_entry(LogEntryType.LOG, entry_data)
            
            if step_id not in self.log_index:
                self.log_index[step_id] = []
            self.log_index[step_id].append(position)
    
    def get_index(self) -> Dict:
        """Get the index mapping."""
        return {
            'outputs': self.index,
            'logs': self.log_index,
        }
    
    def flush(self):
        """Flush the buffer to disk."""
        with self.lock:
            self.file.flush()
    
    def close(self):
        """Close the log file."""
        if hasattr(self, 'file') and not self.file.closed:
            self.flush()
            self.file.close()
            # Unregister atexit handler
            atexit.unregister(self.close)


class LogWatcher:
    """
    Watches an output log file and streams data to the viewer.
    
    This class monitors an output log file in real-time and sends updates
    to the viewer for displaying logs, outputs, and queue sizes.
    """
    
    def __init__(self, graph_id: str, log_file_path: Union[str, Path], viewer_interface: ViewManagerInterface):
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
        self.latest_outputs: Dict[Tuple[str, str], Any] = {}  # Maps (step_id, pin_id) to the latest output
        self.all_outputs: Dict[Tuple[str, str], List[Any]] = {}  # Maps (step_id, pin_id) to a list of outputs
        self.outputs_updated = False  # Flag to indicate if outputs were updated during iteration
        self.watch_thread = None
        self.last_position = 0
        self.pin_output_counts = {}  # Maps (step_id, pin_id) to count
        
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
        with open(self.log_file_path, 'rb') as file:
            # Main monitoring loop
            while not self.stop_event.is_set():
                # Check if there's new data
                current_size = self.log_file_path.stat().st_size
                if current_size > self.last_position:
                    # Reset the outputs updated flag
                    self.outputs_updated = False
                    
                    # Move to the last position we read
                    file.seek(self.last_position)
                    
                    # Read new entries
                    self._process_new_entries(file)
                    
                    # Update last position
                    self.last_position = file.tell()
                    
                    # Update the viewer with the latest outputs (only once per iteration)
                    if self.outputs_updated:
                        for (step_id, pin_id), output in self.latest_outputs.items():
                            self.viewer.handle_output(step_id, pin_id, output)
                        # Clear latest outputs after sending to viewer
                        self.latest_outputs = {}
                
                # Sleep briefly before checking again
                time.sleep(0.1)

    
    def _process_new_entries(self, file: BinaryIO):
        """Process new entries in the log file."""
        # Create an unpacker that reads directly from the file
        unpacker = msgpack.Unpacker(file, raw=False)
        
        for entry in unpacker:    
            # Process the entry based on its type
            if entry['type'] == LogEntryType.OUTPUT.value:
                self._handle_output_entry(entry['data'])
            elif entry['type'] == LogEntryType.LOG.value:
                self._handle_log_entry(entry['data'])
            elif entry['type'] == LogEntryType.META.value:
                pass
            else:
                print(f"Unknown entry type: {entry['type']}")

    def _handle_output_entry(self, data):
        """Handle an output entry from the log file."""
        data = cloudpickle.loads(data)
        step_id = data['step_id']
        pin_id = data['pin_id']
        output = data['output']
        
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
        step_id = data['step_id']
        message = data['message']
        log_type = data['type']
        
        # Update the viewer with the log
        self.viewer.handle_log(step_id, message, log_type)
        
    def get_output(self, step_id: str, pin_id: str, index: int) -> Optional[Any]:
        """Get the latest output for a step and pin."""
        key = (step_id, pin_id)
        if key in self.all_outputs and index < len(self.all_outputs[key]):
            print(f"Getting output for {key} at index {index}")
            return self.all_outputs[key][index]
        
        print(f"Output not found for {key} at index {index}")
        print([k for k in self.all_outputs.keys()])
        return None

class OutputLogManager:
    """
    Manager for output logs.
    
    This class maintains a mapping of graph IDs to log files and watchers.
    """
    
    def __init__(self, log_dir: Optional[Union[str, Path]] = None):
        """
        Initialize the output log manager.
        
        Args:
            log_dir: Directory to store log files, defaults to a temporary directory
        """
        if log_dir is None:
            log_dir = os.path.join(tempfile.gettempdir(), f"graphbook_logs_{uuid.uuid4().hex}")
        
        self.log_dir = Path(log_dir)
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.writers: Dict[str, OutputLogWriter] = {}  # graph_id -> OutputLogWriter
        self.watchers: Dict[str, LogWatcher] = {}  # graph_id -> LogWatcher
        self.lock = threading.Lock()
        
        # Register cleanup
        atexit.register(self.close)
    
    def get_writer(self, graph_id: str) -> OutputLogWriter:
        """
        Get or create a writer for a graph.
        
        Args:
            graph_id: ID of the graph
            
        Returns:
            The output log writer
        """
        with self.lock:
            if graph_id not in self.writers:
                log_file_path = self.log_dir / f"{graph_id}.graphlog"
                self.writers[graph_id] = OutputLogWriter(log_file_path)
            
            return self.writers[graph_id]
    
    def get_watcher(self, graph_id: str) -> Optional[LogWatcher]:
        """
        Get a reader for a graph.
        
        Args:
            graph_id: ID of the graph
            
        Returns:
            The output log reader or None if no log exists
        """
        return self.watchers.get(graph_id)
        
    def create_watcher(self, graph_id: str, viewer_interface: ViewManagerInterface) -> LogWatcher:
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
            
            log_file_path = self.log_dir / f"{graph_id}.graphlog"
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
        print("STopping watcher")
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
            
            # Close all writers and readers
            for writer in self.writers.values():
                writer.close()
            
            # Unregister atexit handler
            atexit.unregister(self.close)
