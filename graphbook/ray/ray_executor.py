import ray
from graphbook.core.processing.graph_processor import Executor
from graphbook.core.serialization import (
    Graph,
    GraphNodeWrapper,
    GraphStepWrapper,
    GraphResourceWrapper,
)
from graphbook.core.steps import Step
from graphbook.core.resources import Resource
from .ray_img import RayMemoryManager
from .ray_client import RayClientPool
import ray.util.queue
from typing import Optional, Tuple, Dict
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

    def __init__(
        self,
        use_file_viewing: bool = False,
        **init_args
    ):
        """
        Initialize the RayExecutor.
        
        Args:
            use_file_viewing (bool): Whether to enable logging of step outputs to a DAG log file
            init_args (dict): Ray Initialization args to pass into ray.init(...)
        """
        if not ray.is_initialized():
            ray.init(**init_args)

        self.cmd_queue = ray.util.queue.Queue()
        self.view_queue = ray.util.queue.Queue()


        self.client_pool = RayClientPool(
            close_event=mp.Event(),
            proc_queue=self.cmd_queue,
            view_queue=self.view_queue,
        )

        # Initialize the Ray step handler
        self.handler = ray_api.init_handler(self.cmd_queue, self.view_queue)
        
        # Current execution log info
        self.use_file_viewing = use_file_viewing

    def get_client_pool(self):
        return self.client_pool

    def get_img_storage(self):
        return RayMemoryManager
    
    def get_log_filename(self):
        """
        Get the current log filename.
        
        Returns:
            str: The current log filename or None if logging is not enabled
        """
        if not self.enable_logging:
            return None
        return self.current_log_filename

    def run(self, graph: Graph, name: str, step_id: Optional[str] = None):
        """
        Execute the provided graph using Ray.

        Args:
            graph (Graph): The graph
            name (str): Name of the execution
            step_id (Optional[str]): If provided, only run the specified step and its dependencies
        """
        # Create a new execution context with logging configuration
        context = GraphbookTaskContext(
            name=name,
            task_id=name,
            enable_logging=self.enable_logging,
            log_dir=self.log_dir,
            log_filename=self.current_log_filename,
        )
        
        # Set up logging if enabled
        if self.enable_logging:
            # Import here to avoid circular imports
            from graphbook.logging.ray import RayLogWriter
            
            # Generate log filename if needed
            if self.log_filename is None:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                self.current_log_filename = f"{name}-{timestamp}.log"
            else:
                self.current_log_filename = self.log_filename
                
            # Store execution ID
            self.current_execution_id = name
            
            # Initialize logger
            logger = RayLogWriter().get_logger(
                execution_id=name,
                log_dir=self.log_dir,
                log_filename=self.current_log_filename
            )
            
            # Initialize nodes from graph
            serialized_graph = graph.serialize()
            logger.initialize_from_graph(serialized_graph)

        # Initialize the execution and get the Ray dag
        leaf_nodes = self._build_ray_dag(graph, step_id)

        # Execute the dag
        with graphbook_task_context(context):
            # Start the execution
            ray.get(
                self.handler.handle_new_execution.remote(
                    context.name, graph.serialize(), False
                )
            )

            final = self.handler.handle_end_execution.bind(*leaf_nodes)
            # Execute the workflow
            return ray.get(final.execute())

    def _build_ray_dag(
        self, graph: Graph, step_id: Optional[str] = None
    ) -> Tuple[Dict[str, Step], Dict[str, Resource]]:
        """
        Constructs a Ray DAG and returns the leaf nodes to the dag
        """
        # steps = {step.id: step for step in graph.get_steps()}
        # resources = {resource.id: resource for resource in graph.get_resources()}
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
