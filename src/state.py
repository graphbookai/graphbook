from __future__ import annotations
from aiohttp.web import WebSocketResponse
from typing import Dict, Tuple, List, Iterator, Set
from graphbook.steps.base import Step, DataRecord
from graphbook.resources.base import Resource
from viewer import Logger
import multiprocessing as mp
import importlib, inspect
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
        if req['cmd'] == 'add_node':
            self.add_node(req['node'])
        elif req['cmd'] == 'put_node':
            self.put_node(req['node'])
        elif req['cmd'] == 'delete_node':
            self.delete_node(req['id'])

    def add_node(self, node: dict):
        self.nodes[node['id']] = node

    def put_node(self, node: dict):
        self.nodes[node['id']] = node

    def delete_node(self, id: str):
        del self.nodes[id]

class NodeCatalog:
    def __init__(self, custom_nodes_path: str):
        sys.path.append(custom_nodes_path)
        self.custom_nodes_path = custom_nodes_path
        self.nodes = {"steps": {}, "resources": {}}
        self.nodes["steps"] |= exports.default_exported_steps
        self.nodes["resources"] |= exports.default_exported_resources
        self.hashes = {"steps": {}, "resources": {}}

    def _clean_hashes(self):
        for node_type in self.hashes:
            self.hashes[node_type] = { k: v for k, v in self.hashes[node_type].items() if k in self.nodes[node_type] }

    def _clean_nodes(self, is_updated: dict):
        for node_type in self.nodes:
            self.nodes[node_type] = { k: v for k, v in self.nodes[node_type].items() if k in is_updated[node_type] }

    def get_nodes(self) -> Tuple[dict, dict]:
        def get_code_hash(obj):
            src = inspect.getsource(obj)
            return hashlib.md5(src.encode()).hexdigest()

        def try_set_node(name, obj, node_lookup, hash_lookup, is_updated, is_new):
            curr_hash = get_code_hash(obj)
            is_updated[name] = False
            is_new[name] = False
            if name not in hash_lookup:
                hash_lookup[name] = curr_hash
                is_new[name] = True
            if curr_hash != hash_lookup[name]:
                hash_lookup[name] = curr_hash
                is_updated[name] = True
            node_lookup[name] = obj

        is_updated = {"steps": { k: False for k in self.nodes["steps"] }, "resources": { k: False for k in self.nodes["resources"] }}
        is_new = {"steps": { k: False for k in self.nodes["steps"] }, "resources": { k: False for k in self.nodes["resources"] }}
        for root, dirs, files in os.walk(self.custom_nodes_path):
            for file in files:
                if not file.endswith('.py'):
                    continue
                module_name = file[:file.index('.py')]
                # trim beginning periods
                while module_name.startswith('.'):
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
                            try_set_node(name, obj, self.nodes["steps"], self.hashes["steps"], is_updated["steps"], is_new["steps"])
                        if issubclass(obj, Resource):
                            try_set_node(name, obj, self.nodes["resources"], self.hashes["resources"], is_updated["resources"], is_new["resources"])

        self._clean_hashes()
        self._clean_nodes(is_updated)
        return self.nodes, is_updated, is_new

StepState = Enum('StepState', ['EXECUTED'])

class GraphState:
    def __init__(self, custom_nodes_path: str, view_manager_queue: mp.Queue):
        sys.path.append(custom_nodes_path)
        self.custom_nodes_path = custom_nodes_path
        self.view_manager_queue = view_manager_queue
        self._dict_graph = {}
        self._dict_resources = {}
        self._steps: Dict[str, Step] = {}
        self._resources: Dict[str, Resource] = {}
        self._queues: Dict[str, MultiConsumerStateDictionaryQueue] = {}
        self._resource_values: dict = {}
        self._parent_iterators: Dict[str, Iterator] = {}
        self._node_catalog = NodeCatalog(custom_nodes_path)
        self._new_nodes: Dict[str, Dict[str, bool]] = {}
        self._updated_nodes: Dict[str, Dict[str, bool]] = {}
        self._step_states: Dict[str, Set[StepState]] = {}

    def update_state(self, graph: dict, graph_resources: dict):
        nodes, is_updated, is_new = self._node_catalog.get_nodes()
        self._new_nodes = is_new
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
            resources[resource_id] = resource_hub[resource_name](**resource_data["parameters"])
            if curr_resource is not None and curr_resource == resource_data and not is_updated_resource.get(resource_name, False):
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
                    step_input[param_name] = param_values[lookup['node']]
                else:
                    step_input[param_name] = lookup
            logger = Logger(self.view_manager_queue, step_id, step_name)
            step = step_hub[step_name](**step_input, id=step_id, logger=logger)
            steps[step_id] = step
            curr_step = self._dict_graph.get(step_id)
            if curr_step is not None and curr_step == step_data and not is_updated_step.get(step_name, False):
                queues[step_id] = self._queues[step_id]
                step_states[step_id] = self._step_states[step_id]
                previous_obj = self._steps[step_id]
                for parent in previous_obj.parents:
                    if parent.id in self._queues:
                        self._queues[parent.id].update_consumer(id(previous_obj), id(step))
            else:
                queues[step_id] = MultiConsumerStateDictionaryQueue()
                step_states[step_id] = set()

        # Next, connect the steps
        for step_id, step_data in graph.items():
            child_node = steps[step_id]
            for input in step_data['inputs']['in']:
                node = input['node']
                slot = input['slot']
                parent_node = steps[node]
                if parent_node not in child_node.parents:
                    parent_node.set_child(child_node, slot)
                # Note: Two objects with non-overlapping lifetimes may have the same id() value.
                # But in this case, the below child_node object is not overlapping because at
                # this point, any previous nodes in the graph are still in self._steps
                queues[parent_node.id].add_consumer(id(child_node), slot)
        for step_id in steps:
            parent_node = steps[step_id]
            children_ids = [id(child) for label_steps in parent_node.children.values() for child in label_steps]
            queues[step_id].remove_except(children_ids)
        def get_parent_iterator(step_id):
            step = steps[step_id]
            p_index = 0
            while True:
                yield step.parents[p_index]
                p_index = (p_index + 1) % len(step.parents)
        self._parent_iterators = { step_id: get_parent_iterator(step_id) for step_id in steps }

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
        self._consumer_idx = { k: v for k, v in self._consumer_idx.items() if k in consumer_ids }
        self._consumer_subs = { k: v for k, v in self._consumer_subs.items() if k in consumer_ids }
        
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
        # key, order_idx = self._order[idx]
        records = self._dict[key]
        if order_idx >= len(records):
            raise StopIteration
        value = records[order_idx]
        self._consumer_idx[consumer_id] = idx
        return value
