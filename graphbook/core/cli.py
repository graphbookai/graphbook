#!/usr/bin/env python
import argparse
import sys
from pathlib import Path
from graphbook.core import config
from graphbook.core.web import start_app
from graphbook.core.logs.web import start_view


DESCRIPTION = """
Graphbook | Visual AI Development Framework
"""

workflow_dir = "workflow"
nodes_dir = "custom_nodes"
docs_dir = "docs"


def add_common_args(parser):
    """Add arguments that are common to all subcommands."""
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host to bind the server to"
    )
    parser.add_argument(
        "--port", type=int, default=8005, help="Port to bind the server to"
    )
    parser.add_argument(
        "--config", type=str, help="Path to a config file for supplementary settings"
    )


def add_app_args(parser):
    """Add arguments specific to the app subcommand."""
    parser.add_argument("--num_workers", type=int, default=1)
    parser.add_argument("--continue_on_failure", action="store_true")
    parser.add_argument("--copy_outputs", action="store_true")
    parser.add_argument("--media_dir", type=str, default="/")
    parser.add_argument("--web_dir", type=str)
    parser.add_argument("--start_media_server", action="store_true")
    parser.add_argument("--media_port", type=int, default=8006)
    parser.add_argument(
        "--root_dir",
        type=str,
        help="If setting this directory, workflow_dir, nodes_dir, and docs_dir will be ignored",
    )
    parser.add_argument(
        "--workflow_dir",
        type=str,
        default=workflow_dir,
        help="Path to the workflow directory",
    )
    parser.add_argument(
        "--nodes_dir",
        type=str,
        default=str(Path(workflow_dir).joinpath(nodes_dir)),
        help="Path to the custom nodes directory",
    )
    parser.add_argument(
        "--docs_dir",
        type=str,
        default=str(Path(workflow_dir).joinpath(docs_dir)),
        help="Path to the docs directory",
    )
    parser.add_argument(
        "--no_sample",
        action="store_true",
        help="Do not create a sample workflow if the workflow directory does not exist",
    )
    parser.add_argument(
        "--spawn",
        action="store_true",
        help="Use the spawn start method for multiprocessing",
    )
    parser.add_argument(
        "--isolate_users",
        action="store_true",
        help="Isolate each user in their own execution environment. Does NOT prevent users from accessing each other's files.",
    )


def add_view_args(parser):
    """Add arguments specific to the view subcommand."""
    parser.add_argument(
        "log_path",
        type=str,
        nargs="?",
        help="Path to log file or directory containing log files to view. Defaults to 'logs/'.",
    )
    parser.add_argument("--web_dir", type=str, help="Directory containing web assets")


def resolve_paths(args):
    """Resolve paths based on root_dir if specified."""
    if hasattr(args, "root_dir") and args.root_dir:
        args.workflow_dir = args.root_dir
        args.nodes_dir = str(Path(args.root_dir).joinpath(nodes_dir))
        args.docs_dir = str(Path(args.root_dir).joinpath(docs_dir))
    return args


def get_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter
    )

    # Add subparsers for app and view modes
    subparsers = parser.add_subparsers(dest="mode", help="Mode to run")

    # App mode subcommand (default)
    app_parser = subparsers.add_parser("app", help="Run the full Graphbook application")
    add_common_args(app_parser)
    add_app_args(app_parser)

    # View mode subcommand
    view_parser = subparsers.add_parser(
        "view", help="View logs only mode. Starts a simple server to view logs."
    )
    add_common_args(view_parser)
    add_view_args(view_parser)

    # Also add app arguments to the main parser for backward compatibility
    add_common_args(parser)
    add_app_args(parser)

    return parser.parse_args()


def main():
    args = get_args()

    # Handle config file if specified
    if args.config:
        config.setup(args.config)

    try:
        # Determine which mode to run
        if args.mode == "view":
            start_view(args)
        else:
            # Default to app mode
            args = resolve_paths(args)
            start_app(args)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
