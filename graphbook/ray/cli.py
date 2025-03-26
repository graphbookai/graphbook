#!/usr/bin/env python
import argparse
from pathlib import Path
from graphbook.ray.web import start_ray_server

DESCRIPTION = """
Graphbook | ML Workflow Framework
"""

workflow_dir = "workflow"
nodes_dir = "custom_nodes"
docs_dir = "docs"


def get_args():
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("--web_dir", type=str)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8005)
    parser.add_argument(
        "--config",
        type=str,
        help="Path to a config file for supplementary settings",
    )
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
        "--log_dir",
        type=str,
        default="logs",
        help="Path to the logs directory for applications that simply use the DAG Logging lib",
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

    return parser.parse_args()


def resolve_paths(args):
    if args.root_dir:
        args.workflow_dir = args.root_dir
        args.nodes_dir = str(Path(args.root_dir).joinpath(nodes_dir))
        args.docs_dir = str(Path(args.root_dir).joinpath(docs_dir))
    return args


def main():
    args = get_args()
    args = resolve_paths(args)

    start_ray_server(args)


if __name__ == "__main__":
    main()
