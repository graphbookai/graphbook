from graphbook.core.viewer import MultiGraphViewManager
from graphbook.core.shm import MultiThreadedMemoryManager
from graphbook.core.clients import SimpleClientPool
from graphbook.core.web import Server
from pathlib import Path
from typing import Optional, Tuple
import sys
import asyncio
import multiprocessing as mp
import time
import threading
from urllib.parse import urlparse
from graphbook.logging import LogManager, LogDirectoryReader


# Optional s3fs import for S3 support
try:
    import s3fs
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False


def is_s3_url(path_str: str) -> bool:
    """Check if a string is an S3 URL.

    Args:
        path_str: String to check

    Returns:
        True if the string is an S3 URL, False otherwise
    """
    # Check if it starts with s3:// or https://s3
    if path_str.startswith("s3://"):
        return True
    if path_str.startswith("https://") and ".s3." in path_str:
        return True
    return False


def parse_s3_url(url: str) -> Tuple[str, str]:
    """Parse an S3 URL into bucket and path.

    Args:
        url: S3 URL to parse

    Returns:
        Tuple of (bucket, path)
    """
    if url.startswith("s3://"):
        bucket = url.split("s3://")[1].split("/")[0]
        pth = url.split(bucket)[1]
        if pth.startswith("/"):
            pth = pth[1:]
        return bucket, pth
    
    # Handle https URLs
    parsed = urlparse(url)
    if ".s3." in parsed.netloc:
        bucket = parsed.netloc.split(".s3.")[0]
        pth = parsed.path
        return bucket, pth
    
    raise ValueError(f"Invalid S3 URL: {url}")


def is_valid_log_file(path: Path) -> bool:
    """Check if a file is a valid graphbook log file.

    Args:
        path: Path to the log file

    Returns:
        True if the file is a valid graphbook log file, False otherwise
    """
    if not path.exists():
        return False

    if path.is_dir():
        return True

    if path.suffix != ".log":
        return False

    return True


class S3LogReader(LogDirectoryReader):
    """Watches an S3 bucket for log files and manages their watchers using s3fs for streaming access."""

    def __init__(
        self,
        s3_url: str,
        queue: mp.Queue,
        poll_interval: float = 5.0,  # Default to 5 seconds for S3 to avoid excessive API calls
        close_event: Optional[mp.Event] = None,
    ):
        """
        Initialize the S3 log reader.

        Args:
            s3_url: S3 URL to the log directory or file
            queue: Queue to send data to the viewer
            poll_interval: Time in seconds to wait between checking for new data
            close_event: Event to signal when to stop the task loop
        """
        # We need to create a temporary directory to store downloaded files
        import tempfile
        self.temp_dir = tempfile.mkdtemp(prefix="graphbook_s3_logs_")
        super().__init__(self.temp_dir, queue, poll_interval, close_event)
        
        # Parse the S3 URL
        if s3_url.endswith("/"):
            s3_url = s3_url[:-1]
        self.bucket_name, self.name = parse_s3_url(s3_url)
        print("Parsed S3 URL:", self.bucket_name, self.name)
        self.s3_url = s3_url
        
        # Create S3 filesystem
        if not S3_AVAILABLE:
            raise ImportError(
                "s3fs is required for S3 support. Install with 'pip install s3fs'"
            )
        
        self.s3_fs = s3fs.S3FileSystem(anon=False)
        
        # Initialize tracking of S3 object states
        self.s3_objects = {}  # Maps object key to last modified time
        self.is_file = self.name.endswith(".log")
        
        # Create thread for syncing S3 objects
        self.sync_thread = None
        self.sync_stop_event = threading.Event()

    def _stream_s3_object(self, s3_path: str):
        """Stream an S3 object to the temp directory using s3fs."""
        try:
            local_path = Path(self.temp_dir) / Path(s3_path).name
            
            # Stream the file from S3 to local filesystem
            with self.s3_fs.open(s3_path, "rb") as s3_file:
                with open(local_path, "wb") as local_file:
                    local_file.write(s3_file.read())
                    
            print(f"Wrote S3 object {s3_path} to {local_path}")
            return str(local_path)
        except Exception as e:
            print(f"Error streaming S3 object {s3_path}: {type(e)} {str(e)}")
            return None

    def _sync_s3_objects(self):
        """Sync S3 objects to the local filesystem using s3fs streaming."""
        while not self.sync_stop_event.is_set():
            try:
                if self.is_file:
                    # If monitoring a specific file
                    if self.s3_fs.exists(self.s3_url):
                        info = self.s3_fs.info(self.s3_url)
                        last_modified = info.get('LastModified')
                        
                        # If the file has been modified or doesn't exist locally, stream it
                        if self.name not in self.s3_objects or self.s3_objects[self.name] != last_modified:
                            local_path = self._stream_s3_object(self.name)
                            if local_path:
                                self.s3_objects[self.name] = last_modified
                                # Notify about the file if it's new
                                if self.name not in self.s3_objects:
                                    self.handle_new_file(local_path)
                    else:
                        print(f"S3 object {self.name} not found")
                else:
                    # If monitoring a prefix (directory)
                    # s3fs glob to list all log files under the prefix
                    log_files = self.s3_fs.glob(f"{self.s3_url}/*.log")
                    
                    for s3_file in log_files:
                        # Extract key from full s3 path
                        key = s3_file.replace(f"s3://{self.bucket_name}/", "")
                        
                        # Get file info
                        info = self.s3_fs.info(s3_file)
                        last_modified = info.get('LastModified')
                        
                        # If the object has been modified or doesn't exist locally, stream it
                        if key not in self.s3_objects or self.s3_objects[key] != last_modified:
                            local_path = self._stream_s3_object(key)
                            if local_path:
                                self.s3_objects[key] = last_modified
                                # Notify about the file if it's new
                                if key not in self.s3_objects:
                                    self.handle_new_file(local_path)
            except Exception as e:
                print(f"Error syncing S3 objects: {str(e)}")
            
            # Sleep for the poll interval
            time.sleep(self.poll_interval)

    def start(self):
        """Start watching the S3 bucket."""
        # Start the sync thread
        self.sync_stop_event.clear()
        self.sync_thread = threading.Thread(target=self._sync_s3_objects, daemon=True)
        self.sync_thread.start()
        
        # Start the directory reader
        super().start()
        
        print(f"Watching S3 {'file' if self.is_file else 'prefix'}: {self.s3_url}")

    def stop(self):
        """Stop watching the S3 bucket and clean up resources."""
        # Stop the sync thread
        if self.sync_thread is not None:
            self.sync_stop_event.set()
            self.sync_thread.join(timeout=1.0)
            self.sync_thread = None
        
        # Stop the directory reader
        super().stop()
        
        # Clean up the temp directory
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Error cleaning up temp directory: {str(e)}")


def start_view(args):
    """Run the view mode with a simplified server setup."""
    log_path = args.log_path
    is_s3_path = False
    
    if log_path:
        # Check if it's an S3 URL
        if isinstance(log_path, str) and is_s3_url(log_path):
            is_s3_path = True
        else:
            log_path = Path(log_path)
            if not is_valid_log_file(log_path):
                print(f"Error: Invalid log file or directory: {log_path}")
                sys.exit(1)
    else:
        log_path = Path("logs")  # Default to the logs directory
        # Create it if it doesn't exist
        log_path.mkdir(exist_ok=True)
        
    # Check if S3 is available when needed
    if is_s3_path and not S3_AVAILABLE:
        print("Error: S3 dependencies are not available.")
        print("Install with 'pip install s3fs'")
        sys.exit(1)

    # Set up the server components
    close_event = mp.Event()
    view_queue = mp.Queue()
    log_reader = None

    try:
        if is_s3_path:
            # Set up the S3 log reader
            log_reader = S3LogReader(
                log_path, view_queue, poll_interval=5.0, close_event=close_event
            )
            log_reader.start()
        else:
            # Set up the regular log directory reader
            log_dir = log_path if log_path.is_dir() else log_path.parent
            log_reader = LogDirectoryReader(
                str(log_dir), view_queue, poll_interval=0.1, close_event=close_event
            )
            log_reader.start()

            # If a specific file is provided, announce it
            if not log_path.is_dir():
                print(f"Watching log file: {log_path}")
            else:
                print(f"Watching log directory: {log_path}")

        # Create a simple client pool with no processor
        client_pool = SimpleClientPool(
            close_event=close_event, view_queue=view_queue, processor=None
        )

        # Start the server
        server = Server(
            close_event=close_event,
            client_pool=client_pool,
            img_mem=MultiThreadedMemoryManager,
            web_dir=args.web_dir,
            host=args.host,
            port=args.port,
        )

        print(f"Started view server at {args.host}:{args.port}")
        print("Press Ctrl+C to stop the server")

        # Run the server
        loop = asyncio.get_event_loop()
        loop.run_until_complete(server.start(block=True))

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        # Clean up resources
        close_event.set()

        if log_reader:
            log_reader.stop()
