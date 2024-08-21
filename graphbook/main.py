#!/usr/bin/env python
import argparse
from graphbook.web import start_web
from graphbook.serve import start_serve

DESCRIPTION = """
Graphbook | ML Workflow Framework
"""


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
    parser.add_argument("--graph_port", type=int, default=8005)
    parser.add_argument("--media_port", type=int, default=8006)
    parser.add_argument("--web_port", type=int, default=8007)
    parser.add_argument("--workflow_dir", type=str, default="./workflow")
    parser.add_argument("--nodes_dir", type=str, default="./workflow/custom_nodes")

    return parser.parse_args()


def main():
    args = get_args()

    if args.command == "web":
        start_web(args)


if __name__ == "__main__":
    main()
