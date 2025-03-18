from graphbook.core.viewer import MultiGraphViewManager
from graphbook.core.shm import MultiThreadedMemoryManager
from graphbook.core.clients import SimpleClientPool
from graphbook.core.web import Server
from pathlib import Path
import sys
import asyncio
import multiprocessing as mp

# Import the logging system
try:
    from graphbook.logging import LogManager, LogDirectoryReader

    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False


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


def start_view(args):
    """Run the view mode with a simplified server setup."""
    log_path = args.log_path
    if log_path:
        log_path = Path(log_path)
        if not is_valid_log_file(log_path):
            print(f"Error: Invalid log file or directory: {log_path}")
            sys.exit(1)
    else:
        print("No log file or directory specified. Will watch for new logs.")
        log_path = Path("logs")  # Default to the logs directory
        # Create it if it doesn't exist
        log_path.mkdir(exist_ok=True)

    # Check if logging is available
    if not LOGGING_AVAILABLE:
        print("Error: Logging dependencies are not available.")
        print("Install with 'pip install msgpack cloudpickle watchdog pillow'")
        sys.exit(1)

    # Set up the server components
    close_event = mp.Event()
    view_queue = mp.Queue()
    log_reader = None

    try:
        # Set up the log directory reader
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
