from __future__ import annotations
from typing import Dict, Tuple, List, Iterator, Set, Optional, Union, Any, TYPE_CHECKING
import importlib, importlib.util, inspect
import os
import hashlib
from enum import Enum
from pathlib import Path
from graphbook.core.steps import Step, PromptStep, StepOutput
from graphbook.core.resources import Resource
from graphbook.core.viewer import ViewManagerInterface
from graphbook.core.plugins import setup_plugins
from graphbook.core.utils import transform_json_log, ExecutionContext
from graphbook.core import nodes

if TYPE_CHECKING:
    from graphbook.core.serialization import Graph


class NodeInstantiationError(Exception):
    def __init__(self, message: str, node_id: str, node_name: str):
        message = f"Error instantiating node {node_name} with id {node_id}:\n{message}"
        super().__init__(message)
        self.node_id = node_id
        self.node_name = node_name


class NodeCatalog:
    def __init__(self, custom_nodes_path: Path):
        self.custom_nodes_path = custom_nodes_path
        self.nodes = {"steps": {}, "resources": {}}
        self.nodes["steps"] |= nodes.default_exported_steps
        self.nodes["resources"] |= nodes.default_exported_resources
        self.plugins = setup_plugins()
        steps, resources, _ = self.plugins
        for plugin in steps:
            self.nodes["steps"] |= steps[plugin]
        for plugin in resources:
            self.nodes["steps"] |= resources[plugin]
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
        for root, dirs, files in os.walk(str(self.custom_nodes_path)):
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
                mod = self._get_module(os.path.join(root, file))

                # get node classes
                for _, obj in inspect.getmembers(mod):
                    if inspect.isclass(obj):
                        if issubclass(obj, Step):
                            self.nodes["steps"][obj.__name__] = obj
                            updated_nodes["steps"][obj.__name__] = True
                        if issubclass(obj, Resource):
                            self.nodes["resources"][obj.__name__] = obj
                            updated_nodes["resources"][obj.__name__] = True

        return updated_nodes

    def get_nodes(self) -> Tuple[dict, dict]:
        updated_nodes = self._update_custom_nodes()
        return self.nodes, updated_nodes


StepState = Enum("StepState", ["EXECUTED", "EXECUTED_THIS_RUN"])


class GraphState:
    def __init__(self, custom_nodes_path: Path):
        self.view_manager: ViewManagerInterface = None
        self._dict_graph = {}
        self._dict_resources = {}
        self._steps: Dict[str, Step] = {}
        self._queues: Dict[str, MultiConsumerStateDictionaryQueue] = {}
        self._resource_values: dict = {}
        self._parent_iterators: Dict[str, Iterator] = {}
        self._node_catalog = NodeCatalog(custom_nodes_path)
        self._updated_nodes: Dict[str, Dict[str, bool]] = {}
        self._step_states: Dict[str, Set[StepState]] = {}
        self._step_graph = {"child": {}, "parent": {}}

    def set_viewer(self, viewer: ViewManagerInterface):
        self.view_manager = viewer

    def update_state(self, graph: dict, graph_resources: dict):
        nodes, is_updated = self._node_catalog.get_nodes()
        self._updated_nodes = is_updated
        step_hub = nodes["steps"]
        resource_hub = nodes["resources"]
        is_updated_step = is_updated["steps"]
        is_updated_resource = is_updated["resources"]

        # First, create resources that the steps depend on
        resource_values = {}
        dict_resources = {}
        resource_has_changed = {}

        def set_resource_value(resource_id, resource_data):
            if resource_id in resource_values:
                return
            curr_resource = self._dict_resources.get(resource_id)
            resource_name = resource_data["name"]

            p = {}
            input_resources_have_changed = False
            for p_key, p_value in resource_data["parameters"].items():
                if isinstance(p_value, dict) and "node" in p_value:
                    p_id = p_value["node"]
                    set_resource_value(p_id, graph_resources[p_id])
                    p[p_key] = resource_values[p_id]
                    input_resources_have_changed |= resource_has_changed[p_id]
                else:
                    p[p_key] = p_value

            if (
                curr_resource is not None
                and curr_resource == resource_data
                and not is_updated_resource.get(resource_name, False)
                and not input_resources_have_changed
            ):
                resource_values[resource_id] = self._resource_values[resource_id]
                dict_resources[resource_id] = curr_resource
                resource_has_changed[resource_id] = False
            else:
                if curr_resource is not None:
                    del curr_resource, self._dict_resources[resource_id]
                try:
                    ExecutionContext.update(
                        node_id=resource_id, node_name=resource_name
                    )
                    self.view_manager.handle_start(resource_id)
                    resource: Resource = resource_hub[resource_name](**p)
                    resource_values[resource_id] = resource.value()
                except KeyError:
                    raise NodeInstantiationError(
                        f"No resource node with name {resource_name} found",
                        resource_id,
                        resource_name,
                    )
                except Exception as e:
                    raise NodeInstantiationError(str(e), resource_id, resource_name)
                dict_resources[resource_id] = resource_data
                resource_has_changed[resource_id] = True
                return resource_values[resource_id]

        for resource_id, resource_data in graph_resources.items():
            set_resource_value(resource_id, resource_data)

        # Next, create all steps
        steps: Dict[str, Step] = {}
        queues: Dict[str, MultiConsumerStateDictionaryQueue] = {}
        step_states: Dict[str, Set[StepState]] = {}
        step_graph = {"child": {}, "parent": {}}
        for step_id, step_data in graph.items():
            step_name = step_data["name"]
            step_input = {}
            step_input_has_changed = False
            for param_name, lookup in step_data["parameters"].items():
                if isinstance(lookup, dict) and "node" in lookup:
                    step_input[param_name] = resource_values[lookup["node"]]
                    step_input_has_changed |= resource_has_changed[lookup["node"]]
                else:
                    step_input[param_name] = lookup
            curr_step = self._dict_graph.get(step_id)

            if (
                curr_step is not None
                and curr_step == step_data
                and not step_input_has_changed
                and not is_updated_step.get(step_name, False)
            ):
                steps[step_id] = self._steps[step_id]
                queues[step_id] = self._queues[step_id]
                step_states[step_id] = self._step_states[step_id]
                step_states[step_id].discard(StepState.EXECUTED_THIS_RUN)
                step_graph["parent"][step_id] = self._step_graph["parent"][step_id]
                step_graph["child"][step_id] = self._step_graph["child"][step_id]
            else:
                try:
                    step = step_hub[step_name](**step_input)
                    step.id = step_id
                except KeyError:
                    raise NodeInstantiationError(
                        f"No step node with name {step_name} found", step_id, step_name
                    )
                except Exception as e:
                    raise NodeInstantiationError(str(e), step_id, step_name)
                steps[step_id] = step
                queues[step_id] = MultiConsumerStateDictionaryQueue()
                step_states[step_id] = set()

                # Remove old consumers from parents
                previous_obj = self._steps.get(step_id)
                if previous_obj is not None:
                    parent_ids = self._step_graph["parent"][previous_obj.id]
                    for parent_id in parent_ids:
                        if parent_id in self._queues:
                            self._queues[parent_id].remove_consumer(id(previous_obj))
            step_graph["parent"][step_id] = set()
            step_graph["child"][step_id] = set()

        # Next, connect the steps
        for step_id, step_data in graph.items():
            child_node = steps[step_id]
            for input in step_data["inputs"]:
                node = input["node"]
                slot = input["slot"]
                parent_node = steps[node]
                step_graph["parent"][child_node.id].add(parent_node.id)
                step_graph["child"][parent_node.id].add(child_node.id)
                # Note: Two objects with non-overlapping lifetimes may have the same id() value.
                # But in this case, the below child_node object is not overlapping because at
                # this point, any previous nodes in the graph are still in self._steps
                queues[parent_node.id].add_consumer(id(child_node), slot)

        # Remove consumers from parents that are not children
        for step_id in steps:
            parent_node = steps[step_id]
            children_ids = [
                id(steps[child_id]) for child_id in step_graph["child"][step_id]
            ]
            queues[step_id].remove_all_except(children_ids)

        def get_parent_iterator(step_id):
            p_index = 0
            parents = list(self._step_graph["parent"][step_id])
            while True:
                yield parents[p_index]
                p_index = (p_index + 1) % len(parents)

        self._parent_iterators = {
            step_id: get_parent_iterator(step_id) for step_id in steps
        }

        # Update current graph and resource state
        self._dict_graph = graph
        self._dict_resources = dict_resources
        self._steps = steps
        self._queues = queues
        self._resource_values = resource_values
        self._step_states = step_states
        self._step_graph = step_graph

    def update_state_py(self, graph: "Graph", params: dict):
        from graphbook.core.serialization import GraphResourceWrapper

        # First, create resources that the steps depend on
        resource_values = {}
        resources = {}
        resource_has_changed = {}

        def set_resource_value(resource: "GraphResourceWrapper"):
            resource_id = resource.id
            if resource_id in resource_values:
                return

            resource_params = params.get(resource_id, {})
            resource_class = resource.node
            resource_name = resource_class.__name__
            p = {}
            input_resources_have_changed = False
            for p_key, p_value in resource.params.items():
                if isinstance(p_value, GraphResourceWrapper):
                    p_node: "GraphResourceWrapper" = p_value
                    set_resource_value(p_node)
                    p[p_key] = resource_values[p_node.id]
                    input_resources_have_changed |= resource_has_changed[p_node.id]
                else:
                    p[p_key] = p_value
            # Overwrite params from values in the UI
            p.update(resource_params)

            curr_resource = self._dict_resources.get(
                resource_id
            )  # Actual resource object
            curr_resource_value = self._resource_values.get(resource_id)
            if (
                isinstance(curr_resource, resource_class)
                and curr_resource_value is not None
                and not input_resources_have_changed
            ):
                resource_values[resource_id] = curr_resource_value
                resource_has_changed[resource_id] = False
            else:
                if curr_resource is not None:
                    del self._dict_resources[resource_id]
                if curr_resource_value is not None:
                    del self._resource_values[resource_id]
                try:
                    ExecutionContext.update(
                        node_id=resource_id, node_name=resource_name
                    )
                    self.view_manager.handle_start(resource_id)
                    resource: Resource = resource_class(**p)
                    resource_values[resource_id] = resource.value()
                except Exception as e:
                    raise NodeInstantiationError(str(e), resource_id, resource_name)
                resources[resource_id] = resource
                resource_has_changed[resource_id] = True

        for resource in graph.get_resources():
            set_resource_value(resource)

        # Next, create all steps
        steps: Dict[str, Step] = {}
        queues: Dict[str, MultiConsumerStateDictionaryQueue] = {}
        step_states: Dict[str, Set[StepState]] = {}
        step_graph = {"child": {}, "parent": {}}
        for step in graph.get_steps():
            step_id = step.id
            step_class = step.node
            step_name = step_class.__name__
            step_params = params.get(step_id, {})
            p = {}
            step_input_has_changed = step_params != self._dict_graph.get(step_id)
            for p_key, p_value in step.params.items():
                if isinstance(p_value, GraphResourceWrapper):
                    resource = p_value
                    p[p_key] = resource_values[resource.id]
                    step_input_has_changed |= resource_has_changed[resource.id]
                else:
                    p[p_key] = p_value
            # Overwrite params from values in the UI
            p.update(step_params)

            curr_step = self._steps.get(step_id)
            if isinstance(curr_step, step_class) and not step_input_has_changed:
                steps[step_id] = self._steps[step_id]
                queues[step_id] = self._queues[step_id]
                step_states[step_id] = self._step_states[step_id]
                step_states[step_id].discard(StepState.EXECUTED_THIS_RUN)
                step_graph["parent"][step_id] = self._step_graph["parent"][step_id]
                step_graph["child"][step_id] = self._step_graph["child"][step_id]
            else:
                try:
                    step = step_class(**p)
                    step.id = step_id
                except Exception as e:
                    raise NodeInstantiationError(str(e), step_id, step_name)
                steps[step_id] = step
                queues[step_id] = MultiConsumerStateDictionaryQueue()
                step_states[step_id] = set()

                # Remove old consumers from parents
                previous_obj = self._steps.get(step_id)
                if previous_obj is not None:
                    parent_ids = self._step_graph["parent"][previous_obj.id]
                    for parent_id in parent_ids:
                        if parent_id in self._queues:
                            self._queues[parent_id].remove_consumer(id(previous_obj))
            step_graph["parent"][step_id] = set()
            step_graph["child"][step_id] = set()

        # Next, connect the steps
        for step in graph.get_steps():
            child_node = step
            for slot, parent_node in step.deps:
                step_graph["parent"][child_node.id].add(parent_node.id)
                step_graph["child"][parent_node.id].add(child_node.id)
                # Note: Two objects with non-overlapping lifetimes may have the same id() value.
                # But in this case, the below child_node object is not overlapping because at
                # this point, any previous nodes in the graph are still in self._steps
                queues[parent_node.id].add_consumer(id(steps[child_node.id]), slot)

        # Remove consumers from parents that are not children
        for step_id in steps:
            parent_node = steps[step_id]
            children_ids = [
                id(steps[child_id]) for child_id in step_graph["child"][step_id]
            ]
            queues[step_id].remove_all_except(children_ids)

        def get_parent_iterator(step_id):
            p_index = 0
            parents = list(self._step_graph["parent"][step_id])
            while True:
                yield parents[p_index]
                p_index = (p_index + 1) % len(parents)

        self._parent_iterators = {
            step_id: get_parent_iterator(step_id) for step_id in steps
        }

        # Update current graph and resource state
        self._dict_graph = params  # Used to track changes in params
        self._steps = steps
        self._queues = queues
        self._dict_resources = resources  # Actual resource objects
        self._resource_values = resource_values
        self._step_states = step_states
        self._step_graph = step_graph

    def create_parent_subgraph(self, step_id: str):
        new_steps = {}
        q = []
        q.append(step_id)
        while q:
            step_id = q.pop(0)
            if step_id in new_steps:
                continue

            new_steps[step_id] = self._steps[step_id]
            for parent_id in self._step_graph["parent"][step_id]:
                q.append(parent_id)
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
            children = self._step_graph["child"][step_id]
            for child_id in children:
                dfs(child_id)
            ordered_steps.append(step)

        for step_id in steps:
            dfs(step_id)
        return ordered_steps[::-1]

    def handle_outputs(self, step_id: str, outputs: StepOutput):
        for label, records in outputs.items():
            self._queues[step_id].enqueue(label, records)
        self._step_states[step_id].add(StepState.EXECUTED)
        self._step_states[step_id].add(StepState.EXECUTED_THIS_RUN)
        self.view_manager.handle_queue_size(step_id, self._queues[step_id].dict_sizes())
        for pin, output in outputs.items():
            if len(output) == 0:
                continue
            self.view_manager.handle_output(
                step_id, pin, transform_json_log(output[-1])
            )

    def get_resource_values(self) -> dict:
        return self._resource_values

    def clear_outputs(self, node_id: Optional[str] = None):
        if node_id is None:
            for q in self._queues.values():
                q.clear()
            for step_id in self._step_states:
                self.view_manager.handle_queue_size(
                    step_id, self._queues[step_id].dict_sizes()
                )
                self._step_states[step_id] = set()
                self._steps[step_id].on_clear()
            self._dict_resources.clear()
            self._resource_values.clear()
        else:
            if node_id in self._queues:
                self._queues[node_id].clear()
                step = self._steps[node_id]
                for parent_id in self._step_graph["parent"][node_id]:
                    self._queues[parent_id].reset_consumer_idx(id(step))
                self._step_states[node_id] = set()
                self.view_manager.handle_queue_size(
                    node_id, self._queues[node_id].dict_sizes()
                )
                self._steps[node_id].on_clear()
            elif node_id in self._dict_resources:
                del self._resource_values[node_id], self._dict_resources[node_id]

    def get_input(self, step: Step) -> Any:
        num_parents = len(self._step_graph["parent"][step.id])
        i = 0
        while i < num_parents:
            next_parent_id = next(self._parent_iterators[step.id])
            try:
                next_input = self._queues[next_parent_id].dequeue(id(step))
                return next_input
            except StopIteration:
                i += 1
        raise StopIteration

    def get_state(self, step: Union[Step, str], state: StepState) -> bool:
        step_id = step.id if isinstance(step, Step) else step
        return state in self._step_states[step_id]

    def get_output(self, step_id: str, pin_id: str, index: int) -> dict:
        step_queue = self._queues.get(step_id)
        entry = {"step_id": step_id, "pin_id": pin_id, "index": index, "data": None}
        if step_queue is None:
            return entry
        internal_list = step_queue._dict.get(pin_id)
        if internal_list is None:
            return entry
        if index >= len(internal_list):
            return entry
        data = internal_list[index]
        entry.update(data=data)
        return entry

    def handle_prompt_response(self, step_id: str, response: dict) -> bool:
        step = self._steps.get(step_id)
        if not isinstance(step, PromptStep):
            return False
        try:
            step.handle_prompt_response(response)
            return True
        except:
            return False

    def get_step(self, step_id: str):
        return self._steps.get(step_id)

    def get_resource(self, resource_id: str):
        return self._dict_resources.get(resource_id)


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
        if self._consumer_idx.get(consumer_id):
            del self._consumer_idx[consumer_id]
            del self._consumer_subs[consumer_id]

    def remove_all_except(self, consumer_ids: List[int]):
        self._consumer_idx = {
            k: v for k, v in self._consumer_idx.items() if k in consumer_ids
        }
        self._consumer_subs = {
            k: v for k, v in self._consumer_subs.items() if k in consumer_ids
        }

    def enqueue(self, key: str, records: List[Any]):
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

    def dict_sizes(self):
        return {k: len(v) for k, v in self._dict.items()}

    def clear(self):
        self._dict.clear()
        self._order.clear()
        for consumer_id in self._consumer_subs:
            self._consumer_idx[consumer_id] = 0
            self._consumer_subs[consumer_id] = set()

    def reset_consumer_idx(self, consumer_id: int):
        self._consumer_idx[consumer_id] = 0
