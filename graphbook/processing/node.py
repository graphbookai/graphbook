import ray
import ray.actor
from ray.dag import DAGNode
from typing import Union, List, Any, Dict
from ray.dag.output_node import MultiOutputNode



class GraphbookNode(DAGNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _execute_impl(
        self, *args, **kwargs
    ) -> Union[ray.ObjectRef, "ray.actor.ActorHandle"]:
        """Execute this node, assuming args have been transformed already."""
        
        raise NotImplementedError

    def _copy_impl(
        self,
        new_args: List[Any],
        new_kwargs: Dict[str, Any],
        new_options: Dict[str, Any],
        new_other_args_to_resolve: Dict[str, Any],
    ) -> "DAGNode":
        """Return a copy of this node with the given new args."""
        raise NotImplementedError