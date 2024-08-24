#!/usr/bin/env python
import argparse
from graphbook.web import start_web
import os.path as osp

DESCRIPTION = """
Graphbook | ML Workflow Framework
"""

workflow_dir = "./workflow"
nodes_dir = "custom_nodes"
docs_dir = "docs"


def get_args():
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--num_workers", type=int, default=1)
    parser.add_argument("--continue_on_failure", action="store_true")
    parser.add_argument("--copy_outputs", action="store_true")

    # Web subcommand
    parser.add_argument("--media_dir", type=str, default="/")
    parser.add_argument("--web_dir", type=str)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8005)
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
        default=osp.join(workflow_dir, nodes_dir),
        help="Path to the custom nodes directory",
    )
    parser.add_argument(
        "--docs_dir",
        type=str,
        default=osp.join(workflow_dir, docs_dir),
        help="Path to the docs directory",
    )

    return parser.parse_args()


def resolve_paths(args):
    if args.root_dir:
        args.workflow_dir = args.root_dir
        args.nodes_dir = osp.join(args.root_dir, nodes_dir)
        args.docs_dir = osp.join(args.root_dir, docs_dir)
    return args


def main():
    args = get_args()
    args = resolve_paths(args)

    start_web(args)


if __name__ == "__main__":
    main()
