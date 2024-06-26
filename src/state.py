from __future__ import annotations
from aiohttp.web import WebSocketResponse
from typing import Dict, Tuple, List, Iterator, Set
from graphbook.steps.base import Step, DataRecord
from graphbook.resources.base import Resource
from viewer import Logger, ViewManagerInterface
import multiprocessing as mp
import importlib, importlib.util, inspect
import exports
import sys, os
import hashlib
from enum import Enum

Outputs = Dict[str, List[DataRecord]]


class UIState:
    def __init__(self, websocket: WebSocketResponse):
        self.ws = websocket
        self.nodes = {}
        self.edges = {}

    def cmd(self, req: dict):
        if req["cmd"] == "add_node":
            self.add_node(req["node"])
        elif req["cmd"] == "put_node":
            self.put_node(req["node"])
        elif req["cmd"] == "delete_node":
            self.delete_node(req["id"])

    def add_node(self, node: dict):
        self.nodes[node["id"]] = node

    def put_node(self, node: dict):
        self.nodes[node["id"]] = node

    def delete_node(self, id: str):
        del self.nodes[id]


class NodeCatalog:
    def __init__(self, custom_nodes_path: str):
        sys.path.append(custom_nodes_path)
        self.custom_nodes_path = custom_nodes_path
        self.nodes = {"steps": {}, "resources": {}}
        self.nodes["steps"] |= exports.default_exported_steps
        self.nodes["resources"] |= exports.default_exported_resources
        self.hashes = {}

    def _hash(self, data: str) -> str:
        return hashlib.md5(data.encode()).hexdigest()

    def _get_file_hash(self, file_path: str) -> str:
        with open(file_path, "r") as f:
            src = f.read()
            return self._hash(src)

    def _get_module(self, module_path):
        spec = importlib.util.spec_from_file_location("transient_module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _should_update_module(self, module_path):
        if module_path not in self.hashes:
            self.hashes[module_path] = self._get_file_hash(module_path)
            return True
        curr_src_hash = self._get_file_hash(module_path)
        if self.hashes[module_path] != curr_src_hash:
            self.hashes[module_path] = curr_src_hash
            return True
        return False

    def _update_custom_nodes(self) -> dict:
        """
        Updates the nodes dictionary with the latest custom nodes and returns which ones have been updated
        """
        updated_nodes = {
            "steps": {k: False for k in self.nodes["steps"]},
            "resources": {k: False for k in self.nodes["resources"]},
        }
        for root, dirs, files in os.walk(self.custom_nodes_path):
            for file in files:
                if not file.endswith(".py"):
                    continue
                if not self._should_update_module(os.path.join(root, file)):
                    continue
                module_name = file[: file.index(".py")]
                # trim beginning periods
                while module_name.startswith("."):
                    module_name = module_name[1:]
                # import
                if module_name in sys.modules:
                    mod = sys.modules[module_name]
                    mod = importlib.reload(mod)
                else:
                    mod = importlib.import_module(module_name)
                # get node classes
                for name, obj in inspect.getmembers(mod):
                    if inspect.isclass(obj):
                        if issubclass(obj, Step):
                            self.nodes["steps"][name] = obj
                            updated_nodes["steps"][name] = True
                        if issubclass(obj, Resource):
                            self.nodes["resources"][name] = obj
                            updated_nodes["resources"][name] = True
        return updated_nodes

    def get_nodes(self) -> Tuple[dict, dict]:
        updated_nodes = self._update_custom_nodes()
        return self.nodes, updated_nodes


StepState = Enum("StepState", ["EXECUTED", "EXECUTED_THIS_RUN"])


class GraphState:
    def __init__(self, custom_nodes_path: str, view_manager_queue: mp.Queue):
        sys.path.append(custom_nodes_path)
        self.custom_nodes_path = custom_nodes_path
        self.view_manager_queue = view_manager_queue
        self.view_manager = ViewManagerInterface(view_manager_queue)
        self._dict_graph = {}
        self._dict_resources = {}
        self._steps: Dict[str, Step] = {}
        self._resources: Dict[str, Resource] = {}
        self._queues: Dict[str, MultiConsumerStateDictionaryQueue] = {}
        self._resource_values: dict = {}
        self._parent_iterators: Dict[str, Iterator] = {}
        self._node_catalog = NodeCatalog(custom_nodes_path)
        self._updated_nodes: Dict[str, Dict[str, bool]] = {}
        self._step_states: Dict[str, Set[StepState]] = {}

    def update_state(self, graph: dict, graph_resources: dict):
        nodes, is_updated = self._node_catalog.get_nodes()
        self._updated_nodes = is_updated
        step_hub = nodes["steps"]
        resource_hub = nodes["resources"]
        is_updated_step = is_updated["steps"]
        is_updated_resource = is_updated["resources"]

        # First, create resources that the steps depend on
        param_values = {}
        resources = {}
        for resource_id, resource_data in graph_resources.items():
            curr_resource = self._dict_resources.get(resource_id)
            resource_name = resource_data["name"]
            resources[resource_id] = resource_hub[resource_name](
                **resource_data["parameters"]
            )
            if (
                curr_resource is not None
                and curr_resource == resource_data
                and not is_updated_resource.get(resource_name, False)
            ):
                param_values[resource_id] = self._resource_values[resource_id]
            else:
                param_values[resource_id] = resources[resource_id].value()

        # Next, create all steps
        steps = {}
        queues = {}
        step_states = {}
        for step_id, step_data in graph.items():
            step_name = step_data["name"]
            step_input = {}
            for param_name, lookup in step_data["parameters"].items():
                if isinstance(lookup, dict):
                    step_input[param_name] = param_values[lookup["node"]]
                else:
                    step_input[param_name] = lookup
            curr_step = self._dict_graph.get(step_id)
            if (
                curr_step is not None
                and curr_step == step_data
                and not is_updated_step.get(step_name, False)
            ):
                steps[step_id] = self._steps[step_id]
                queues[step_id] = self._queues[step_id]
                step_states[step_id] = self._step_states[step_id]
                step_states[step_id].discard(StepState.EXECUTED_THIS_RUN)
            else:
                logger = Logger(self.view_manager_queue, step_id, step_name)
                step = step_hub[step_name](**step_input, id=step_id, logger=logger)
                steps[step_id] = step
                queues[step_id] = MultiConsumerStateDictionaryQueue()
                step_states[step_id] = set()
                
                previous_obj = self._steps.get(step_id)
                if previous_obj is not None:
                    print("Updating consumer")
                    for parent in previous_obj.parents:
                        if parent.id in self._queues:
                            self._queues[parent.id].update_consumer(
                                id(previous_obj), id(step)
                            )

        # Next, connect the steps
        for step_id, step_data in graph.items():
            child_node = steps[step_id]
            for input in step_data["inputs"]:
                node = input["node"]
                slot = input["slot"]
                parent_node = steps[node]
                if parent_node not in child_node.parents:
                    parent_node.set_child(child_node, slot)
                # Note: Two objects with non-overlapping lifetimes may have the same id() value.
                # But in this case, the below child_node object is not overlapping because at
                # this point, any previous nodes in the graph are still in self._steps
                queues[parent_node.id].add_consumer(id(child_node), slot)
        for step_id in steps:
            parent_node = steps[step_id]
            children_ids = [
                id(child)
                for label_steps in parent_node.children.values()
                for child in label_steps
            ]
            queues[step_id].remove_except(children_ids)

        def get_parent_iterator(step_id):
            step = steps[step_id]
            p_index = 0
            while True:
                yield step.parents[p_index]
                p_index = (p_index + 1) % len(step.parents)

        self._parent_iterators = {
            step_id: get_parent_iterator(step_id) for step_id in steps
        }

        # Update current graph and resource state
        self._dict_graph = graph
        self._dict_resources = resources
        self._steps = steps
        self._resources = resources
        self._queues = queues
        self._resource_values = param_values
        self._step_states = step_states

    def create_parent_subgraph(self, step_id: str):
        new_steps = {}
        q = []
        q.append(step_id)
        while q:
            step_id = q.pop(0)
            if step_id in new_steps:
                continue

            new_steps[step_id] = self._steps[step_id]
            step = self._steps[step_id]
            for input in step.parents:
                q.append(input.id)
        return new_steps

    def get_processing_steps(self, step_id: str = None):
        steps = self._steps
        if step_id is not None:
            steps = self.create_parent_subgraph(step_id)
        # Topologically sort the steps
        # Note: Optional, due to the way the graph is processed
        ordered_steps = []
        visited = set()

        def dfs(step_id):
            if step_id in visited or step_id not in steps:
                return
            visited.add(step_id)
            step = steps[step_id]
            for child in step.children.values():
                for c in child:
                    dfs(c.id)
            ordered_steps.append(step)

        for step_id in steps:
            dfs(step_id)
        return ordered_steps[::-1]

    def handle_outputs(self, step_id: str, outputs: Outputs):
        for label, records in outputs.items():
            self._queues[step_id].enqueue(label, records)
        self._step_states[step_id].add(StepState.EXECUTED)
        self._step_states[step_id].add(StepState.EXECUTED_THIS_RUN)
        self.view_manager.handle_queue_size(step_id, self._queues[step_id].size())

    def clear_outputs(self, step_id: str = None):
        if step_id is None:
            for q in self._queues.values():
                q.clear()
            for step_id in self._step_states:
                self.view_manager.handle_queue_size(step_id, 0)
                self._step_states[step_id] = set()
        else:
            self._queues[step_id].clear()
            step = self._steps[step_id]
            for p in step.parents:
                self._queues[p.id].reset_consumer_idx(id(step))
            self._step_states[step_id] = set()
        self.view_manager.handle_queue_size(step_id, 0)

    def get_input(self, step: Step) -> DataRecord:
        num_parents = len(step.parents)
        i = 0
        while i < num_parents:
            next_parent = next(self._parent_iterators[step.id])
            try:
                next_input = self._queues[next_parent.id].dequeue(id(step))
                return next_input
            except StopIteration:
                i += 1
        raise StopIteration

    def get_state(self, step: Step | str, state: StepState) -> bool:
        step_id = step.id if isinstance(step, Step) else step
        return state in self._step_states[step_id]


class MultiConsumerStateDictionaryQueue:
    def __init__(self):
        self._dict: Dict[str, list] = {}
        self._order: List[Tuple[str, int]] = []
        self._consumer_idx: Dict[int, int] = {}
        self._consumer_subs: Dict[int, set] = {}

    def add_consumer(self, consumer_id: int, key: str):
        if consumer_id not in self._consumer_idx:
            self._consumer_idx[consumer_id] = 0
            self._consumer_subs[consumer_id] = set()
        self._consumer_subs[consumer_id].add(key)

    def update_consumer(self, old_id: int, new_id: int):
        self._consumer_idx[new_id] = self._consumer_idx[old_id]
        self._consumer_subs[new_id] = self._consumer_subs[old_id]
        del self._consumer_idx[old_id]
        del self._consumer_subs[old_id]

    def remove_consumer(self, consumer_id: int):
        del self._consumer_idx[consumer_id]
        del self._consumer_subs[consumer_id]

    def remove_except(self, consumer_ids: List[int]):
        self._consumer_idx = {
            k: v for k, v in self._consumer_idx.items() if k in consumer_ids
        }
        self._consumer_subs = {
            k: v for k, v in self._consumer_subs.items() if k in consumer_ids
        }

    def enqueue(self, key: str, records: List[DataRecord]):
        if not key in self._dict:
            self._dict[key] = []
        idx = len(self._dict[key])
        self._dict[key].extend(records)
        for i in range(len(records)):
            self._order.append((key, idx + i))

    def dequeue(self, consumer_id: int):
        idx = self._consumer_idx[consumer_id]
        key = None
        while key not in self._consumer_subs[consumer_id]:
            if idx >= len(self._order):
                raise StopIteration
            key, order_idx = self._order[idx]
            idx += 1
        records = self._dict[key]
        if order_idx >= len(records):
            raise StopIteration
        value = records[order_idx]
        self._consumer_idx[consumer_id] = idx
        return value
    
    def size(self):
        return len(self._order)

    def clear(self):
        self._dict.clear()
        self._order.clear()
        for consumer_id in self._consumer_subs:
            self._consumer_idx[consumer_id] = 0
            self._consumer_subs[consumer_id] = set()
            
    def reset_consumer_idx(self, consumer_id: int):
        self._consumer_idx[consumer_id] = 0
