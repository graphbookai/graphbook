from typing import Dict, List, Any, Optional, Union, Tuple, BinaryIO
import os
import msgpack
import cloudpickle
import time
import io
import threading
import tempfile
from pathlib import Path
import atexit
import shutil
import uuid
import json
from enum import Enum, auto


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
        
        # Create the directory if it doesn't exist
        os.makedirs(self.log_file_path.parent, exist_ok=True)
        
        # Open the file and write the header
        self.file = open(self.log_file_path, 'wb')
        self._write_header()
        
        # Register cleanup
        atexit.register(self.close)
    
    def _write_header(self):
        """Write the log file header."""
        header = {
            'format': 'graphbook-output-log',
            'version': '1.0',
            'created_at': time.time(),
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
        
        # Create the entry
        entry = {
            'type': entry_type.value,
            'timestamp': time.time(),
            'size': len(serialized_data),
            'data': serialized_data,
        }
        
        # Write the entry
        packed_entry = msgpack.packb(entry, use_bin_type=True)
        entry_length = len(packed_entry)
        
        # Write the length and then the entry
        self.file.write(msgpack.packb(entry_length, use_bin_type=True))
        self.file.write(packed_entry)
        self.file.flush()
        
        return position
    
    def write_output(self, step_id: str, pin_id: str, index: int, output: Any):
        """
        Write a step output to the log file.
        
        Args:
            step_id: ID of the step
            pin_id: ID of the output pin
            index: Index of the output
            output: Output data
        """
        with self.lock:
            entry_data = {
                'step_id': step_id,
                'pin_id': pin_id,
                'index': index,
                'output': output,
            }
            position = self._write_entry(LogEntryType.OUTPUT, entry_data)
            self.index[(step_id, pin_id, index)] = position
    
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


class OutputLogReader:
    """
    Reader for the output log file format.
    
    This class deserializes step outputs and logs from the log file.
    """
    
    def __init__(self, log_file_path: Union[str, Path]):
        """
        Initialize the output log reader.
        
        Args:
            log_file_path: Path to the log file
        """
        self.log_file_path = Path(log_file_path)
        self.file = None
        self.index = None
        self.header = None
        self.lock = threading.Lock()
    
    def _open_file(self):
        """Open the log file and initialize if needed."""
        if self.file is None or self.file.closed:
            self.file = open(self.log_file_path, 'rb')
            self._read_header()
            self._build_index()
    
    def _read_header(self):
        """Read the log file header."""
        with self.lock:
            self._open_file()
            self.file.seek(0)
            
            # Read the length of the header entry
            length_bytes = self.file.read(5)  # msgpack for small integers uses 5 bytes
            length = msgpack.unpackb(length_bytes, raw=False)
            
            # Read the header entry
            entry_bytes = self.file.read(length)
            entry = msgpack.unpackb(entry_bytes, raw=False)
            
            if entry['type'] != LogEntryType.META.value:
                raise ValueError("Invalid log file format")
            
            self.header = cloudpickle.loads(entry['data'])
    
    def _read_entry_at(self, position: int) -> Any:
        """
        Read an entry at a specific position in the file.
        
        Args:
            position: Position in the file to read from
            
        Returns:
            The deserialized entry data
        """
        with self.lock:
            self._open_file()
            self.file.seek(position)
            
            # Read the length of the entry
            length_bytes = self.file.read(5)  # msgpack for small integers uses 5 bytes
            length = msgpack.unpackb(length_bytes, raw=False)
            
            # Read the entry
            entry_bytes = self.file.read(length)
            entry = msgpack.unpackb(entry_bytes, raw=False)
            
            # Deserialize the data
            return cloudpickle.loads(entry['data'])
    
    def _build_index(self):
        """Build the index from the log file."""
        with self.lock:
            self._open_file()
            
            # Start after the header
            self.file.seek(0)
            
            # Skip the header
            length_bytes = self.file.read(5)
            length = msgpack.unpackb(length_bytes, raw=False)
            self.file.seek(length, io.SEEK_CUR)
            
            self.index = {'outputs': {}, 'logs': {}}
            
            while True:
                position = self.file.tell()
                
                # Try to read the next entry length
                try:
                    length_bytes = self.file.read(5)
                    if not length_bytes:
                        # End of file
                        break
                    
                    length = msgpack.unpackb(length_bytes, raw=False)
                    
                    # Read the entry
                    entry_bytes = self.file.read(length)
                    entry = msgpack.unpackb(entry_bytes, raw=False)
                    data = cloudpickle.loads(entry['data'])
                    
                    # Index the entry
                    if entry['type'] == LogEntryType.OUTPUT.value:
                        key = (data['step_id'], data['pin_id'], data['index'])
                        self.index['outputs'][key] = position
                    elif entry['type'] == LogEntryType.LOG.value:
                        step_id = data['step_id']
                        if step_id not in self.index['logs']:
                            self.index['logs'][step_id] = []
                        self.index['logs'][step_id].append(position)
                
                except Exception as e:
                    # End of file or corrupt entry
                    break
    
    def get_output(self, step_id: str, pin_id: str, index: int) -> Optional[Any]:
        """
        Get a step output from the log file.
        
        Args:
            step_id: ID of the step
            pin_id: ID of the output pin
            index: Index of the output
            
        Returns:
            The output data or None if not found
        """
        with self.lock:
            self._open_file()
            key = (step_id, pin_id, index)
            
            if key not in self.index['outputs']:
                return None
            
            position = self.index['outputs'][key]
            entry_data = self._read_entry_at(position)
            
            return entry_data['output']
    
    def get_logs(self, step_id: str) -> List[Dict]:
        """
        Get logs for a step from the log file.
        
        Args:
            step_id: ID of the step
            
        Returns:
            List of log entries
        """
        with self.lock:
            self._open_file()
            
            if step_id not in self.index['logs']:
                return []
            
            logs = []
            for position in self.index['logs'][step_id]:
                entry_data = self._read_entry_at(position)
                logs.append({
                    'message': entry_data['message'],
                    'type': entry_data['type'],
                    'index': entry_data['index'],
                })
            
            return logs
    
    def close(self):
        """Close the log file."""
        if self.file and not self.file.closed:
            self.file.close()


class OutputLogManager:
    """
    Manager for output logs.
    
    This class maintains a mapping of graph IDs to log files.
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
        
        self.writers = {}  # graph_id -> OutputLogWriter
        self.readers = {}  # graph_id -> OutputLogReader
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
    
    def get_reader(self, graph_id: str) -> Optional[OutputLogReader]:
        """
        Get a reader for a graph.
        
        Args:
            graph_id: ID of the graph
            
        Returns:
            The output log reader or None if no log exists
        """
        with self.lock:
            log_file_path = self.log_dir / f"{graph_id}.graphlog"
            
            if not log_file_path.exists():
                return None
            
            if graph_id not in self.readers:
                self.readers[graph_id] = OutputLogReader(log_file_path)
            
            return self.readers[graph_id]
    
    def close(self):
        """Close all log files."""
        with self.lock:
            for writer in self.writers.values():
                writer.close()
            for reader in self.readers.values():
                reader.close()
            
            # Unregister atexit handler
            atexit.unregister(self.close)