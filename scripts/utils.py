#!/usr/bin/env python

import argparse
from graphbook.core.serialization import convert_json_workflows_to_py


def main():
    parser = argparse.ArgumentParser(prog="utils")
    subparsers = parser.add_subparsers(dest="command")

    convert_json_to_py = subparsers.add_parser(
        "convert_json_to_py", help="Convert older JSON-serialized workflows to the new Python-serialized format."
    )
    convert_json_to_py.set_defaults(func=convert_json_to_py_command)
    convert_json_to_py.add_argument(
        "--input",
        help="Directory of JSON files that correspond with graphbook workflows.",
        default="./workflow",
    
    )
    convert_json_to_py.add_argument(
        "--output",
        help="Directory to save the converted python files.",
        default="./workflow/new_workflow",
    )

    # Add more subcommands as needed

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


def convert_json_to_py_command(args):
    input_dir = args.input
    output_dir = args.output
    convert_json_workflows_to_py(input_dir, output_dir)

if __name__ == "__main__":
    main()
