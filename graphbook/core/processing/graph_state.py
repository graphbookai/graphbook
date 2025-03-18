from __future__ import annotations
from typing import Dict, Tuple, List, Iterator, Set, Union, TYPE_CHECKING
from graphbook.core.steps import Step, PromptStep, StepOutput
from graphbook.core.resources import Resource
from graphbook.core.viewer import ViewManagerInterface
from graphbook.core.utils import ExecutionContext
from graphbook.core.processing.state import NodeInstantiationError, StepState


if TYPE_CHECKING:
    from graphbook.core.serialization import Graph

class GraphState:
    def __init__(self,):
        self.view_manager: ViewManagerInterface = None
        self._dict_graph = {}
        self._dict_resources = {}
        self._steps: Dict[str, Step] = {}
        self._resource_values: dict = {}
        self._parent_iterators: Dict[str, Iterator] = {}
        self._updated_nodes: Dict[str, Dict[str, bool]] = {}
        self._step_states: Dict[str, Set[StepState]] = {}
        self._step_graph: Dict[str, Dict[str, Set[Tuple[str, str]]]] = {"child": {}, "parent": {}}
        
    def set_viewer(self, viewer: ViewManagerInterface):
        self.view_manager = viewer

    def get_resource_values(self) -> dict:
        return self._resource_values
    
    def get_state(self, step: Union[Step, str], state: StepState) -> bool:
        step_id = step.id if isinstance(step, Step) else step
        return state in self._step_states[step_id]
    
    def create_parent_subgraph(self, step_id: str):
        new_steps = {}
        q = []
        q.append(step_id)
        while q:
            step_id = q.pop(0)
            if step_id in new_steps:
                continue

            new_steps[step_id] = self._steps[step_id]
            for parent_id, _ in self._step_graph["parent"][step_id]:
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
            for child_id, _ in children:
                dfs(child_id)
            ordered_steps.append(step)

        for step_id in steps:
            dfs(step_id)
        return ordered_steps[::-1]
    
    def set_executed(self, step_id: str):
        self._step_states[step_id].add(StepState.EXECUTED)
        self._step_states[step_id].add(StepState.EXECUTED_THIS_RUN)
        
    def handle_prompt_response(self, step_id: str, response: dict) -> bool:
        step = self._steps.get(step_id)
        if not isinstance(step, PromptStep):
            return False
        try:
            step.handle_prompt_response(response)
            return True
        except:
            return False

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
        step_states: Dict[str, Set[StepState]] = {}
        step_graph: Dict[str, Dict[str, Set[Tuple[str, str]]]] = {"child": {}, "parent": {}}
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
                step_graph["parent"][child_node.id].add((parent_node.id, slot))
                step_graph["child"][parent_node.id].add((child_node.id, slot))
                # Note: Two objects with non-overlapping lifetimes may have the same id() value.
                # But in this case, the below child_node object is not overlapping because at
                # this point, any previous nodes in the graph are still in self._steps

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
        self._dict_resources = resources  # Actual resource objects
        self._resource_values = resource_values
        self._step_states = step_states
        self._step_graph = step_graph
    
    def get_depending_children(self, parent_id: str, slot: str) -> List[Step]:
        children: List[Step] = []
        for child_id, child_slot in self._step_graph["child"][parent_id]:
            if child_slot == slot:
                children.append(self._steps[child_id])
        return children
