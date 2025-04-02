import importlib.util
import re
import json
import os
import os.path as osp
import traceback
import inspect
from pathlib import Path
from copy import deepcopy
from typing import List, Tuple, Dict, Any, Optional
import graphbook.core.steps as steps
import graphbook.core.resources as resources
from graphbook.core.processing.graph_processor import Executor, DefaultExecutor


class GraphNodeWrapper:
    """
    Base class for step and resource nodes returned by the Graph class.
    Do not create this directly, use the `Graph.step` or `Graph.resource` methods instead.

    Args:
        node (type): The node to wrap
        id (str): The unique identifier for the node
    """

    def __init__(self, node: type, id: str):
        self.id = id
        self.params: Dict[str, Any] = {}
        self.node = node

    def get(self):
        return self.node

    def param(self, key: str, arg: Any):
        """
        Sets a parameter on the node

        Args:
            key (str): The parameter key
            arg (Any): The parameter value
        """
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
    """
    A wrapper class around a step node that allows for binding dependencies and setting parameters.
    Do not create this directly, use the `Graph.step` method instead.

    Args:
        node (Step): The step node to wrap
        id (str): The unique identifier for the node
    """

    def __init__(self, node: steps.Step, id: str):
        self.node = node
        self.deps: List[Tuple[str, GraphStepWrapper]] = []
        super().__init__(node, id)

    def bind(self, src: "GraphStepWrapper", key="out"):
        """
        Binds this step to the output of another step

        Args:
            src (GraphStepWrapper): The source step to bind to
            key (str): The output key on the source step to bind to
        """
        available_pins = src.node.Outputs
        if key not in available_pins:
            raise ValueError(
                f"Pin '{key}' not found in available pins: {available_pins} for node {src.node.__name__}"
            )

        self.deps.append((key, src))

    def serialize(self):
        step_deps = self.deps
        return {
            "type": "step",
            **super().serialize(),
            "inputs": [{"node": dep[1].id, "pin": dep[0]} for dep in step_deps],
            "outputs": getattr(self.node, "Outputs", ["out"]),
        }


class GraphResourceWrapper(GraphNodeWrapper):
    """
    A wrapper class around a resource node that allows for setting parameters.
    Do not create this directly, use the `Graph.resource` method instead.

    Args:
        node (Resource): The resource node to wrap
        id (str): The unique identifier for the node
    """

    def __init__(self, node: resources.Resource, id: str):
        self.node = node
        super().__init__(node, id)

    def serialize(self):
        return {
            "type": "resource",
            **super().serialize(),
        }


class Graph:
    """
    Creates a new graph object that can be used to define a workflow.
    Use the `step` and `resource` methods to add nodes to the graph.
    """

    def __init__(self):
        self.id = 0
        self.module_name = None
        self.doc = None
        self.nodes: List[GraphNodeWrapper] = []

    def step(self, n: steps.Step) -> GraphStepWrapper:
        """
        Creates a new step node in the graph

        Args:
            n (Step): The step to add to the graph

        Returns:
            GraphStepWrapper: A wrapper around the step node that can be used to bind step dependencies and parameters
        """
        n = GraphStepWrapper(n, id=str(self.id))
        self.nodes.append(n)
        self.id += 1
        return n

    def resource(self, n: resources.Resource) -> GraphResourceWrapper:
        """
        Creates a new resource node in the graph

        Args:
            n (Resource): The resource to add to the graph

        Returns:
            GraphResourceWrapper: A wrapper around the resource node that can have parameters set
        """
        n = GraphResourceWrapper(n, id=str(self.id))
        self.nodes.append(n)
        self.id += 1
        return n

    def md(self, text: str):
        """
        Adds markdown documentation to demonstrate usage of the workflow

        Args:
            text (str): The markdown text to add
        """
        self.doc = text

    def serialize(self) -> dict:
        """
        Serializes the graph into a dictionary for the frontend
        """
        out = dict(doc=self.doc, G={})
        for node in self.nodes:
            try:
                out["G"][node.id] = node.serialize()
            except:
                print(f"Failed to serialize node {node.id}")
                traceback.print_exc()
        return out

    def get_resources(self) -> List[GraphResourceWrapper]:
        """Returns all resources in the graph"""
        return [n for n in self.nodes if isinstance(n, GraphResourceWrapper)]

    def get_steps(self) -> List[GraphStepWrapper]:
        """Returns all steps in the graph"""
        return [n for n in self.nodes if isinstance(n, GraphStepWrapper)]

    def get_subgraph(self, step_id: str) -> "Graph":
        """
        Returns a subgraph containing only the specified step and its dependencies.

        Args:
            step_id (str): The ID of the step to include in the subgraph

        Returns:
            Graph: A new graph containing only the specified step and its dependencies
        """
        subgraph = Graph()
        subgraph.doc = self.doc
        subgraph.module_name = self.module_name + "_id=" + step_id
        node_map = {}

        def add_node(node: GraphNodeWrapper):
            if node.id not in node_map:
                new_node = None
                if isinstance(node, GraphStepWrapper):
                    new_node = subgraph.step(node.node)
                else:
                    new_node = subgraph.resource(node.node)
                new_node.id = node.id
                node_map[node.id] = new_node
                if isinstance(node, GraphStepWrapper):
                    for key, dep in node.deps:
                        add_node(dep)
                        new_node.bind(node_map[dep.id], key)
                for key, value in node.params.items():
                    if isinstance(value, GraphResourceWrapper):
                        add_node(value)
                    new_node.param(key, value)

        for node in self.nodes:
            if node.id == step_id:
                add_node(node)
                break

        return subgraph

    def run(
        self,
        executor: Optional[Executor] = None,
        step_id: Optional[str] = None,
        start_web_server: bool = True,
        host: str = "localhost",
        port: int = 8005,
    ) -> None:
        """
        Run the graph using the provided executor.

        Args:
            executor (Executor): The executor to use for running the graph
            step_id (Optional[str]): If provided, only run the specified step and its dependencies
            start_web_server (bool): If True, start a web server to monitor execution
            host (str): Host for the web server (default: "localhost")
            port (int): Port for the web server (default: 8005)
        """
        # Serialize the graph and pass it to the executor
        if executor is None:
            executor = DefaultExecutor()

        client_pool = executor.get_client_pool()
        img_storage = executor.get_img_storage()

        # Start the web server if requested
        if start_web_server and client_pool is not None and img_storage is not None:
            from graphbook.core.web import async_start

            # Start the web server
            async_start(host, port, None, img_storage, client_pool)

        graph = self
        if step_id:
            graph = self.get_subgraph(step_id)
        executor.run(graph, graph.module_name)

    def __call__(self, *args, **kwargs):
        """
        Use this decorator to decorate a function that defines the workflow.
        The function should contain calls to the `step` and `resource` methods to define the workflow.
        Use the `bind` and `param` methods on the step and resource nodes to define dependencies and parameters.
        """

        def decorator(serialized_func):
            serialized_func()
            self.module_name = Path(inspect.getfile(serialized_func)).name
            module = serialized_func.__globals__
            module["_GRAPHBOOK_WORKFLOW_"] = self

        return decorator


class NoGraphFound(Exception):
    pass


def get_py_as_workflow(filepath: str) -> dict:
    graph = get_py_as_graph(filepath)
    return graph.serialize()


def get_py_as_graph(filepath: str) -> Graph:
    module_spec = importlib.util.spec_from_file_location("transient_module", filepath)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    try:
        workflow = module.__dict__["_GRAPHBOOK_WORKFLOW_"]
        return workflow
    except KeyError:
        raise NoGraphFound(filepath)


def deserialize_json_to_graph(json_data: dict) -> Graph:
    """
    Deserializes a JSON graph representation into a Graph object.

    Args:
        json_data (dict): A dictionary containing the serialized graph data.
            Expected format: {"nodes": [...], "edges": [...]}

    Returns:
        Graph: A Graph object constructed from the JSON data

    Raises:
        ValueError: If the JSON data is not in the expected format
    """
    if "nodes" not in json_data or "edges" not in json_data:
        raise ValueError("JSON data must contain 'nodes' and 'edges' keys")

    graph = Graph()
    node_wrappers = {}

    # First pass: create all nodes
    for node in json_data["nodes"]:
        node_data = node.get("data", {})
        node_id = node["id"]
        node_type = node.get("type")

        if node_type not in ["step", "resource"]:
            continue

        try:
            # Import the node class dynamically
            module_name = node_data.get("module", "custom_nodes")
            node_name = node_data.get("name")

            module = importlib.import_module(module_name)
            node_class = getattr(module, node_name)

            # Create the appropriate wrapper
            if node_type == "step":
                wrapper = graph.step(node_class)
            else:  # resource
                wrapper = graph.resource(node_class)

            # Store the original ID mapping
            wrapper.id = node_id
            node_wrappers[node_id] = wrapper

            # Set parameters
            params = node_data.get("parameters", {})
            for key, param in params.items():
                if "value" in param and param["value"] is not None:
                    wrapper.param(key, param["value"])

        except (ImportError, AttributeError) as e:
            print(f"Failed to create node {node_id}: {e}")

    # Second pass: bind steps
    for edge in json_data["edges"]:
        source_id = edge["source"]
        target_id = edge["target"]
        source_handle = edge.get("sourceHandle", "out")
        target_handle = edge.get("targetHandle", "in")

        if source_id in node_wrappers and target_id in node_wrappers:
            source = node_wrappers[source_id]
            target = node_wrappers[target_id]

            if target_handle == "in":
                # This is a step binding
                if hasattr(target, "bind"):
                    target.bind(source, source_handle)
            else:
                # This is a parameter binding
                target.param(target_handle, source)

    return graph


def serialize_workflow_as_py(
    nodes: List[dict],
    edges: List[dict],
    filepath: str,
    unresolved_modules="custom_nodes",
):
    """
    Not in use due to instability.
    Can result in incosistencies with styling/formatting and the resolution of imported modules.
    """

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
                        f"{t}step_{node_id}.bind({vars[input['node']]}, '{input['pin']}')"
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
