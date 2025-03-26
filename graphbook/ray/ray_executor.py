import ray
from graphbook.core.processing.graph_processor import Executor
from graphbook.core.processing.event_handler import FileEventHandler
from graphbook.core.serialization import (
    Graph,
    GraphNodeWrapper,
    GraphStepWrapper,
    GraphResourceWrapper,
)

from .ray_img import RayMemoryManager
from .ray_client import RayClientPool
import ray.util.queue
from typing import List
from .ray_processor import (
    GraphbookTaskContext,
    graphbook_task_context,
)
import graphbook.ray.ray_api as ray_api
from copy import deepcopy
import multiprocessing as mp


class RayExecutor(Executor):
    """
    Ray execution engine that runs Graphbook workflows using Ray.
    """

    def __init__(self, log_dir: str = "logs", **init_args):
        """
        Initialize the RayExecutor.

        Args:
            log_dir (str): Directory to store output logs. Can be a local path or an S3 URL.
                S3 URLs should be in the format 's3://bucket-name/path/to/logs/'.
                If None, logging is disabled.
            init_args (dict): Ray Initialization args to pass into ray.init(...)
        """
        if not ray.is_initialized():
            ray.init(**init_args)

        self.cmd_queue = ray.util.queue.Queue()
        self.view_queue = ray.util.queue.Queue()
        self.close_event = mp.Event()

        self.client_pool = RayClientPool(
            close_event=self.close_event,
            proc_queue=self.cmd_queue,
            view_queue=self.view_queue,
        )

        # Initialize the Ray step handler
        self.handler = ray_api.init_handler(self.cmd_queue, self.view_queue)

        # Set up logging
        # Note: S3 path validation will happen in LogManager when it's instantiated
        self.log_dir = log_dir

    def get_client_pool(self):
        return self.client_pool

    def get_img_storage(self):
        return RayMemoryManager

    def get_log_dir(self):
        """
        Get the log directory.

        Returns:
            str: The log directory
        """
        return self.log_dir

    def run(self, graph: Graph, name: str):
        """
        Execute the provided graph using Ray.

        Args:
            graph (Graph): The graph
            name (str): Name of the execution
        """
        # Create a new execution context with logging configuration
        context = GraphbookTaskContext(
            name=name,
            task_id=name,
        )

        # Initialize the execution and get the Ray dag
        leaf_nodes = self._build_ray_dag(graph)

        # Execute the dag
        with graphbook_task_context(context):
            # Start the execution
            ray.get(
                self.handler.handle_new_execution.remote(
                    context.name, graph.serialize(), self.log_dir, False
                )
            )

            final = self.handler.handle_end_execution.bind(*leaf_nodes)
            # Execute the workflow
            result = ray.get(final.execute())

            return result

    def _build_ray_dag(self, graph: Graph) -> List[ray.ObjectRef]:
        """
        Constructs a Ray DAG and returns the leaf nodes to the dag.

        Args:
            graph (Graph): The graph

        Returns:
            List[ray.ObjectRef]: The leaf nodes of the Ray DAG
        """
        step_actors = {
            step.id: ray_api.remote(step.get()) for step in graph.get_steps()
        }
        resource_actors = {
            resource.id: ray_api.remote(resource.get())
            for resource in graph.get_resources()
        }

        # Initialize step and resource actors
        step_handles = {}
        resource_handles = {}

        def setup_params_and_init(node: GraphNodeWrapper):
            # > Only recurs through Resources
            if node.id in resource_handles:
                return

            P = deepcopy(getattr(node.get(), "Parameters", {}))

            # Set default parameters
            for p_key, p_value in P.items():
                default_value = p_value.get("default", None)
                if default_value is not None:
                    P[p_key] = default_value

            # Set graph-specified parameters
            for p_key, p_value in node.params.items():
                if isinstance(p_value, GraphResourceWrapper):
                    if p_value.id in resource_handles:
                        P[p_key] = resource_handles[p_value.id]
                    else:
                        setup_params_and_init(p_value)  # <
                        P[p_key] = resource_handles[p_value.id]
                else:
                    P[p_key] = p_value

            actor_options = getattr(node.get(), "Ray_Options", {})
            if isinstance(node, GraphStepWrapper):
                step_actors[node.id].set_ray_options(**actor_options)
                step_actors[node.id].set_node_id(node.id)
                step_handles[node.id] = step_actors[node.id].remote(**P)
            else:
                resource_actors[node.id].set_ray_options(**actor_options)
                resource_actors[node.id].set_node_id(node.id)
                resource_handles[node.id] = resource_actors[node.id].remote(**P)

        for node in graph.get_steps():
            setup_params_and_init(node)
        for node in graph.get_resources():
            setup_params_and_init(node)

        # Bind steps
        step_outputs = {}

        def setup_binds(step: GraphStepWrapper):
            if step.id in step_outputs:
                return

            args = []
            for output_slot, parent_step in step.deps:
                if parent_step.id not in step_outputs:
                    setup_binds(parent_step)
                args.append(output_slot)
                args.append(step_outputs[parent_step.id])

            if len(args) > 0:
                step_outputs[step.id] = step_handles[step.id].bind(*args)
            else:  # Should be a source step
                step_outputs[step.id] = step_handles[step.id]

        for step in graph.get_steps():
            setup_binds(step)

        # Get the leaf nodes
        is_dependency = set()

        def set_is_dependency(step: GraphStepWrapper):
            for _, parent_step in step.deps:
                is_dependency.add(parent_step.id)
                set_is_dependency(parent_step)

        for step in graph.get_steps():
            if step.id not in is_dependency:
                set_is_dependency(step)

        leaf_nodes = [
            step_outputs.get(step.id)
            for step in graph.get_steps()
            if step.id not in is_dependency and step.id in step_outputs
        ]

        return leaf_nodes
