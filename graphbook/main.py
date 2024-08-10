#!/usr/bin/env python
import argparse
from graphbook.web import start_web
from graphbook.serve import start_serve

DESCRIPTION = \
"""
Graphbook | ML Workflow Framework

graphbook web: The web interface and processing server
graphbook serve: A remote processing server
"""


def get_args():
    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--num_workers", type=int, default=1)
    parser.add_argument("--continue_on_failure", action="store_true")
    parser.add_argument("--copy_outputs", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Web subcommand
    web_parser = subparsers.add_parser("web")
    web_parser.add_argument("--media_dir", type=str, default="/")
    web_parser.add_argument("--web_dir", type=str)
    web_parser.add_argument("--host", type=str, default="0.0.0.0")
    web_parser.add_argument("--graph_port", type=int, default=8005)
    web_parser.add_argument("--media_port", type=int, default=8006)
    web_parser.add_argument("--web_port", type=int, default=8007)
    web_parser.add_argument("--workflow_dir", type=str, default="./workflow")
    web_parser.add_argument("--nodes_dir", type=str, default="./workflow/custom_nodes")

    # Serve subcommand
    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", type=str, default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8008)
    serve_parser.add_argument("--nodes_dir", type=str, default="./workflow/custom_nodes")

    return parser.parse_args()


def main():
    args = get_args()

    if args.command == "web":
        start_web(args)
    elif args.command == "serve":
        start_serve(args)


if __name__ == "__main__":
    main()
