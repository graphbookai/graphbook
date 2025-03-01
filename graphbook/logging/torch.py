from typing import List, Union, Optional, Sequence, Callable
from torchvision.transforms import Compose
from graphbook.logging.logger import DAGLogger, DAGNodeRef, CallableNode

try:
    from torchvision.transforms.v2 import Transform as TransformV2, Compose as ComposeV2
    from torchvision.transforms import Compose
except ImportError:
    raise ImportError("torch and torchvision are required for graphbook.logging.TransformsLogger. Try installing them e.g. `pip install graphbook[logging]`")


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

    def _handle_single(self, t: Callable, back_refs: List[DAGNodeRef]):
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
