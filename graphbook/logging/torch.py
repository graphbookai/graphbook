from typing import List, Union, Optional, Sequence, Callable
from graphbook.core.logs.data import DAGLogger, DAGNodeRef, CallableNode
from PIL import Image
from pathlib import Path

try:
    from torch import Tensor
    from torchvision.transforms.functional import to_pil_image
    from torchvision.transforms.v2 import Transform as TransformV2, Compose as ComposeV2
    from torchvision.transforms import Compose
except ImportError:
    raise ImportError(
        "torch and torchvision are required for graphbook.logging.torch. Try installing them e.g. `pip install torch torchvision`"
    )


class TensorDAGNodeRef(DAGNodeRef):
    """
    Inherits from DAGNodeRef and adds the ability to log PIL images or tensors.
    You should not create this directly, but instead use the :meth:`graphbook.logging.torch.TransformsLogger.node` to create one.
    """

    def __init__(
        self,
        id: str,
        name: str,
        doc: str,
        filepath: Path,
        lock,
        *back_refs: List["TensorDAGNodeRef"]
    ):
        super().__init__(id, name, doc, filepath, lock, *back_refs)

    def log(self, pil_or_tensor: Union[Image.Image, Tensor]):
        """
        Logs a PIL image or tensor to the node in the associated DAG.

        Args:
            pil_or_tensor: The PIL image or tensor to log.
        """
        if isinstance(pil_or_tensor, Tensor):
            pil_or_tensor = to_pil_image(pil_or_tensor)
        return super().log(pil_or_tensor)


class TransformsLogger(DAGLogger):
    """
    A DAG logger designed specifically to log the image outputs from torchvision transforms.

    Args:
        name: Name of the DAG. Will randomly generate an ID if not provided
        log_dir: Directory to store the log files. Defaults to logs/
        log_every: Log every nth transform. Defaults to 1 (log every time).

    Example:
        .. highlight:: python
        .. code-block:: python

            from torchvision import transforms as T
            import torch
            from PIL import Image
            import graphbook as gb

            l = gb.TransformsLogger()
            transforms = T.Compose([
                T.ToTensor(),
                T.CenterCrop(600),
                T.Grayscale(),
                T.RandomHorizontalFlip(p=1),
            ])
            transforms = l.log(transforms)

            img_path = "<YOUR_IMAGE_PATH>"
            img = Image.open(img_path)
            img = transforms(img)
    """

    def __init__(
        self,
        name: Optional[str] = None,
        log_dir: Optional[str] = "logs",
        log_every: int = 1,
    ):
        super().__init__(name, log_dir)
        self.log_every = log_every

    def _handle_sequence(self, transforms: Sequence[Callable]):
        new_sequence = []
        last_ref = None
        for t in transforms:
            back_refs = [last_ref] if last_ref is not None else []
            node = self._handle_single(t, back_refs)
            new_sequence.append(t)
            new_sequence.append(CallableNode(node, self.log_every))
            last_ref = node
        return Compose(new_sequence)

    def node(
        self, name: str, doc: str, *back_refs: List[TensorDAGNodeRef]
    ) -> TensorDAGNodeRef:
        """
        Creates a new node in the DAG that can log PIL images or tensors.

        Args:
            name: Name of the node
            doc: Description of the node
            back_refs: List of back references to other nodes

        Returns:
            TensorDAGNodeRef: The reference to the new node
        """
        node = TensorDAGNodeRef(
            str(self.id_idx), name, doc, self.filepath, self.lock, *back_refs
        )
        self._write_node(
            str(self.id_idx),
            name=name,
            doc=doc,
            back_refs=[ref.id for ref in back_refs],
        )
        self.nodes.append(node)
        self.id_idx += 1
        return node

    def _handle_single(self, t: Callable, back_refs: List[TensorDAGNodeRef]):
        name = t.__class__.__name__
        doc = t.__doc__ if t.__doc__ is not None else ""
        return self.node(name, doc, *back_refs)

    def log(self, transform: Union[TransformV2, Compose, ComposeV2]):
        """
        Sets up the transforms to log the image outputs.

        Args:
            transform: A torchvision transform or a sequence of transforms
        """
        if isinstance(transform, Compose) or isinstance(transform, ComposeV2):
            return self._handle_sequence(transform.transforms)
        elif isinstance(transform, TransformV2):
            return self._handle_sequence([transform])
        else:
            raise TypeError("Input should be a Transform or Compose object.")
