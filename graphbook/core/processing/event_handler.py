"""
Event handling abstractions for processors.

This module contains event handler classes that abstract away the details
of sending events to clients. The different implementations support
different backends (file-based or in-memory).
"""

from typing import Dict, Optional, Any, TYPE_CHECKING
import multiprocessing as mp
from abc import ABC, abstractmethod
from ..utils import transform_json_log
from ..viewer import MultiGraphViewManagerInterface
from ..logs import LogManager

if TYPE_CHECKING:
    from ..serialization import Graph


class EventHandler(ABC):
    """
    Base abstract class for event handlers.

    Event handlers provide a consistent API for processors to send
    events to clients, abstracting away the underlying implementation
    details (file-based or in-memory).
    """

    def __init__(self, graph_name: str, view_manager_queue: mp.Queue):
        """
        Initialize the event handler.

        Args:
            graph_name: The name of the graph
            view_manager_queue: Queue for communicating with the view manager
        """
        self.graph_name = graph_name
        self.view_manager_queue = view_manager_queue
        self.view_manager = MultiGraphViewManagerInterface(self.view_manager_queue)
        self.viewer = None

    def initialize_viewer(self):
        """Initialize the viewer interface for this event handler."""
        self.viewer = self.view_manager.new(self.graph_name)
        self.viewer.set_state("run_state", "running")
        return self.viewer

    @abstractmethod
    def write_log(self, node_id: str, message: str, log_type: str = "info"):
        """
        Write a log message for a node.

        Args:
            node_id: ID of the node
            message: Log message
            log_type: Type of log (info, warning, error)
        """
        pass

    @abstractmethod
    def write_output(self, node_id: str, pin_id: str, output: Any):
        """
        Write an output for a node.

        Args:
            node_id: ID of the node
            pin_id: ID of the output pin
            output: Output data
        """
        pass

    @abstractmethod
    def update_metadata(self, metadata: Dict[str, Any]):
        """
        Update metadata for the graph.

        Args:
            metadata: Metadata to update
        """
        pass

    def handle_start(self, node_id: str):
        """Signal the start of node execution."""
        if self.viewer:
            self.viewer.handle_start(node_id)

    def handle_end(self):
        """Signal the end of graph execution."""
        if self.viewer:
            self.viewer.handle_end()
            self.viewer.set_state("run_state", "finished")

    def handle_clear(self, node_id: Optional[str] = None):
        """Clear outputs for a node or the entire graph."""
        if self.viewer:
            self.viewer.handle_clear(node_id)

    def handle_time(self, node_id: str, execution_time: float):
        """
        Record execution time for a node.

        Args:
            node_id: ID of the node
            execution_time: Execution time in seconds
        """
        if self.viewer:
            self.viewer.handle_time(node_id, execution_time)

    def handle_output(self, node_id: str, pin_id: str, output: Any):
        """
        Handle an output for a node.

        Args:
            node_id: ID of the node
            pin_id: ID of the output pin
            output: Output data
        """
        if self.viewer:
            self.viewer.handle_output(node_id, pin_id, transform_json_log(output))

    def handle_queue_size(self, node_id: str, size: Dict[str, int]):
        """
        Handle queue size updates for a node.

        Args:
            node_id: ID of the node
            size: Queue sizes by pin ID
        """
        if self.viewer:
            self.viewer.handle_queue_size(node_id, size)

    def handle_prompt(self, node_id: str, prompt: Dict[str, Any]):
        """
        Handle a prompt for a node.

        Args:
            node_id: ID of the node
            prompt: Prompt data
        """
        if self.viewer:
            self.viewer.handle_prompt(node_id, prompt)

    def cleanup(self):
        """Cleanup resources used by the event handler."""
        pass


class FileEventHandler(EventHandler):
    """
    Event handler that persists events to files.

    This handler is used by GraphProcessor to persist events to log files
    for later retrieval.
    """

    def __init__(
        self,
        graph_name: str,
        view_manager_queue: mp.Queue,
        log_dir: str = "logs",
    ):
        """
        Initialize the file-based event handler.

        Args:
            graph_name: The name of the graph
            view_manager_queue: Queue for communicating with the view manager
            log_dir: Directory to store log files
        """
        super().__init__(graph_name, view_manager_queue)
        self.log_manager = LogManager(log_dir)
        self.log_watcher = None
        self.log_writer = self.log_manager.get_writer(self.graph_name)

    def initialize_viewer(self):
        """Initialize the viewer and log writer/watcher."""
        super().initialize_viewer()

        # Create and start the log watcher to stream logs to the viewer
        self.log_watcher = self.log_manager.create_watcher(self.graph_name, self.viewer)

        return self.viewer

    def write_log(self, node_id: str, message: str, log_type: str = "info"):
        """Write a log message to the log file."""
        if self.log_writer:
            self.log_writer.write_log(node_id, message, log_type)

    def write_output(self, node_id: str, pin_id: str, output: Any):
        """Write an output to the log file."""
        if self.log_writer:
            self.log_writer.write_output(node_id, pin_id, output)

    def update_metadata(self, metadata: Dict[str, Any]):
        """Update metadata in the log file."""
        if self.log_writer:
            self.log_writer.update_metadata(metadata)

    def get_output(self, node_id: str, pin_id: str, index: int) -> Optional[Any]:
        """
        Get a specific output from the log file.

        Args:
            node_id: ID of the node
            pin_id: ID of the output pin
            index: Index of the output

        Returns:
            The output data or None if not found
        """
        if self.log_manager:
            log_reader = self.log_manager.get_watcher(self.graph_name)
            if log_reader:
                output = log_reader.get_output(node_id, pin_id, index)
                output = {
                    "step_id": node_id,
                    "pin_id": pin_id,
                    "index": index,
                    "data": transform_json_log(output),
                }
                return output
        return None

    def cleanup(self):
        """Clean up log watchers and writers."""
        # Stop the log watcher if it's running
        if hasattr(self, "log_watcher") and self.log_watcher:
            self.log_manager.stop_watcher(self.graph_name)

        # Close output log files
        if hasattr(self, "log_manager") and self.log_manager:
            self.log_manager.close()


class MemoryEventHandler(EventHandler):
    """
    Event handler that keeps events in memory.

    This handler is used by WebInstanceProcessor for quick access to events
    during interactive sessions.
    """

    def __init__(self, graph_name: str, view_manager_queue: mp.Queue):
        """
        Initialize the memory-based event handler.

        Args:
            graph_name: The name of the graph
            view_manager_queue: Queue for communicating with the view manager
        """
        super().__init__(graph_name, view_manager_queue)
        self.queue_sizes = {}

    def write_log(self, node_id: str, message: str, log_type: str = "info"):
        """Write a log message to the viewer directly."""
        if self.viewer:
            self.viewer.handle_log(node_id, message, log_type)

    def write_output(self, node_id: str, pin_id: str, output: Any):
        """
        Handle output for a node (no persistent storage).

        The outputs are not persisted but directly sent to the viewer.
        For WebInstanceProcessor, the actual outputs are stored in its
        graph_state instance.
        """
        self.handle_output(node_id, pin_id, output)
        self.queue_sizes.setdefault(node_id, {}).setdefault(pin_id, 0)
        self.queue_sizes[node_id][pin_id] += 1
        self.handle_queue_size(node_id, self.queue_sizes[node_id])

    def update_metadata(self, metadata: Dict[str, Any]):
        """Update metadata in memory."""
        if self.viewer and "graph" in metadata:
            self.viewer.set_state("graph_state", metadata["graph"])

    def get_output(self, node_id: str, pin_id: str, index: int) -> Optional[Any]:
        """Unsupported for memory event handler."""
        error_msg = """
            I am currently not storing any outputs in memory.
            If you would like to see historical outputs, please use the file-based event handler.
            (i.e. set log_dir to a valid directory in the processor's constructor)
            """.strip().replace(
            "\n", " "
        )

        return {
            "step_id": node_id,
            "pin_id": pin_id,
            "index": index,
            "data": {"message": error_msg},
        }
