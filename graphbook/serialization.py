from typing import List, Tuple, Dict, Any
import graphbook.steps as steps
import graphbook.resources as resources
import importlib.util
from copy import deepcopy
import re
import json
import os
import os.path as osp
import traceback


class GraphNodeWrapper:
    def __init__(self, node: type, id: str):
        self.id = id
        self.params: Dict[str, Any] = {}
        self.node = node

    def get(self):
        return self.node

    def param(self, key: str, arg: Any):
        self.params[key] = arg

    def serialize(self):
        params = deepcopy(getattr(self.node, "Parameters", {}))
        for key, value in self.params.items():
            if isinstance(value, GraphNodeWrapper):
                params[key]["value"] = value.id
            else:
                params[key]["value"] = value
        return {
            "name": self.node.__name__,
            "parameters": params,
            "category": getattr(self.node, "Category", ""),
            "doc": getattr(self.node, "__doc__", ""),
            "module": self.node.__module__,
        }


class GraphStepWrapper(GraphNodeWrapper):
    def __init__(self, node: steps.Step, id: str):
        self.node = node
        self.deps: List[Tuple[str, GraphStepWrapper]] = []
        super().__init__(node, id)

    def bind(self, key: str, tgt: "GraphStepWrapper"):
        self.deps.append((key, tgt))

    def serialize(self):
        step_deps = self.deps
        return {
            "type": "step",
            **super().serialize(),
            "inputs": [{"node": dep[1].id, "pin": dep[0]} for dep in step_deps],
            "outputs": getattr(self.node, "Outputs", ["out"]),
        }


class GraphResourceWrapper(GraphNodeWrapper):
    def __init__(self, node: resources.Resource, id: str):
        self.node = node
        super().__init__(node, id)

    def serialize(self):
        return {
            "type": "resource",
            **super().serialize(),
        }


class Graph:
    def __init__(self):
        self.id = 0
        self.nodes: List[GraphNodeWrapper] = []

    def step(self, n: steps.Step) -> GraphStepWrapper:
        n = GraphStepWrapper(n, id=str(self.id))
        self.nodes.append(n)
        self.id += 1
        return n

    def resource(self, n: resources.Resource) -> GraphResourceWrapper:
        n = GraphResourceWrapper(n, id=str(self.id))
        self.nodes.append(n)
        self.id += 1
        return n

    def serialize(self) -> dict:
        G = {}
        for node in self.nodes:
            try:
                G[node.id] = node.serialize()
            except:
                print(f"Failed to serialize node {node.id}")
                traceback.print_exc()
        return G

    def get_resources(self):
        return [n for n in self.nodes if isinstance(n, GraphResourceWrapper)]

    def get_steps(self):
        return [n for n in self.nodes if isinstance(n, GraphStepWrapper)]

    def run(self):
        pass

    def __call__(self, *args, **kwargs):
        def decorator(serialized_func):
            serialized_func()
            module = serialized_func.__globals__
            module["_GRAPHBOOK_WORKFLOW_"] = self

        return decorator


class NoGraphFound(Exception):
    pass


def get_py_as_workflow(filepath: str) -> dict:
    return get_py_as_graph(filepath).serialize()


def get_py_as_graph(filepath: str) -> Graph:
    module_spec = importlib.util.spec_from_file_location("transient_module", filepath)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    try:
        workflow = module.__dict__["_GRAPHBOOK_WORKFLOW_"]
        return workflow
    except KeyError:
        raise NoGraphFound(filepath)


def serialize_workflow_as_py(
    nodes: List[dict],
    edges: List[dict],
    filepath: str,
    unresolved_modules="custom_nodes",
):
    def check_node(node):
        if node.get("type") not in ["step", "resource"]:
            raise ValueError(
                f"Node type must be either 'step' or 'resource'. Got {node.get('type')} instead. Groupings and subflows are not yet supported in Python serialization."
            )

    def transform_id(id: str):
        return re.sub(r"\W", "_", id)

    def get_required_modules():
        modules: Dict[str, set] = {}
        for node in nodes:
            data = node.get("data", None)
            if not data:
                continue
            node_name = data.get("name", None)
            module = data.get("module", unresolved_modules)
            if module not in modules:
                modules[module] = set()
            modules[module].add(node_name)

        return modules

    def get_py_literal(value):
        if isinstance(value, str):
            if "\n" in value:
                return f'"""{value}"""'
            return f'"{value}"'
        return value

    for node in nodes:
        check_node(node)

    nodes = [{**node, "id": transform_id(node["id"])} for node in nodes]
    edges = [
        {
            **edge,
            "source": transform_id(edge["source"]),
            "target": transform_id(edge["target"]),
        }
        for edge in edges
    ]
    node_lookup = {node["id"]: node for node in nodes}
    for edge in edges:
        src = node_lookup[edge["source"]]
        tgt = node_lookup[edge["target"]]
        if tgt.get("inputs") is None:
            tgt["inputs"] = []

        if edge["targetHandle"] == "in":
            tgt["inputs"].append({"node": src["id"], "pin": edge["sourceHandle"]})
        else:
            params = tgt.get("data").get("parameters", None)
            if params is not None:
                params[edge["targetHandle"]]["value"] = src["id"]

    with open(filepath, "w") as f:
        f.write(f"from {__name__} import Graph\n")
        modules = get_required_modules()
        for module, nodes in modules.items():
            f.write(f"from {module} import {', '.join(nodes)}\n")
        f.write("\n")
        f.write("g = Graph()\n\n")
        f.write("@g()\ndef _():\n")
        t = " " * 4

        if len(node_lookup) == 0:
            return

        f.write(f"{t}# Create nodes\n")
        vars = {}
        for node_id, node in node_lookup.items():
            node_name = node["data"]["name"]
            if node["type"] == "step":
                f.write(f"{t}step_{node_id} = g.step({node_name})")
                vars[node_id] = f"step_{node_id}"
            elif node["type"] == "resource":
                f.write(f"{t}resource_{node_id} = g.resource({node_name})")
                vars[node_id] = f"resource_{node_id}"
            f.write("\n")
        f.write("\n")

        f.write(f"{t}# Setup parameters\n")
        for node_id, node in node_lookup.items():
            params = node.get("data").get("parameters", None)
            if params is None:
                continue
            for key, p in params.items():
                if p.get("value") is None:
                    continue
                if p["type"] == "resource":
                    f.write(f"{t}{vars[node_id]}.param('{key}', {vars[p['value']]})")
                else:
                    literal = get_py_literal(p["value"])
                    f.write(f"{t}{vars[node_id]}.param('{key}', {literal})")
                f.write("\n")
        f.write("\n")

        f.write(f"{t}# Bind steps\n")
        for node_id, node in node_lookup.items():
            if node["type"] == "step":
                inputs = node.get("inputs", [])
                for input in inputs:
                    f.write(
                        f"{t}step_{node_id}.bind('{input['pin']}', {vars[input['node']]})"
                    )
                    f.write("\n")


def convert_json_workflows_to_py(input_dir: str, output_dir: str):
    if not osp.exists(output_dir):
        os.mkdir(output_dir)
    for file in os.listdir(input_dir):
        if file.endswith(".json"):
            with open(osp.join(input_dir, file), "r") as f:
                try:
                    data = json.load(f)
                except json.decoder.JSONDecodeError:
                    print(f"Failed to parse {file}. Skipping...")
                    continue
                nodes = data.get("nodes")
                edges = data.get("edges")
                if nodes is not None and edges is not None:
                    filename = file.split(".")[0]
                    try:
                        serialize_workflow_as_py(
                            nodes, edges, osp.join(output_dir, f"{filename}.py")
                        )
                    except ValueError as e:
                        print(
                            f"Failed to convert {file} to Python file: {type(e).__name__}, {e}"
                        )
                    except Exception as e:
                        traceback.print_exc()
