from .base import StepOutput, DataItem, BatchStep
from PIL import Image
from typing import Tuple
from transformers import AutoModel, AutoImageProcessor
import torch
import torchvision.transforms.functional as F
import os.path as osp
import os
import pickle

class HFImageProcessorStep(BatchStep):
    RequiresInput = True
    Parameters = {
        "batch_size": {
            "type": "number",
            "default": 8
        },
        "item_key": {
            "type": "string",
            "default": "image"
        },
        "output_dir": {
            "type": "string"
        },
        "model": {
            "type": "resource",
        },
        "processor": {
            "type": "resource",
        },
    }
    Outputs = ["out"]
    Category = "Huggingface/Transformers"
    def __init__(self, id, logger, batch_size, item_key, model: AutoModel, processor: AutoImageProcessor):
        super().__init__(id, logger, batch_size, item_key)
        self.model = model
        self.processor = processor
        self.file_name_ctr = 0

    @staticmethod
    def load_fn(item: DataItem) -> torch.Tensor:
        im = Image.open(item.item)
        image = F.to_tensor(im)
        if image.shape[0] == 1:
            image = image.repeat(3, 1, 1)
        elif image.shape[0] == 4:
            image = image[:3]
        return image
    
    @staticmethod
    def dump_fn(file_data: torch.Tensor, root_dir: str, uid: int) -> str:
        os.makedirs(root_dir, exist_ok=True)
        if isinstance(file_data, torch.Tensor):
            # PKL
            file_name = osp.join(root_dir, f"image_hidden_states_{uid}.pkl")
        elif isinstance(file_data, Image.Image):
            # Image
            pass
        with open(file_name, "wb") as f:
            pickle.dump(file_data, f)
        return file_name

    @torch.no_grad()
    def on_item_batch(self, tensors, items, records) -> StepOutput:
        # Manipulate
        inputs = self.processor(images=tensors, do_rescale=False, return_tensors="pt")
        outputs = self.model(**inputs).last_hidden_state
        self.logger.log(f"Processed {len(outputs)} images and produced {outputs.shape} hidden states.")

        # Optionally return data to be dumped
        return {
            "image_hidden_states": outputs
        }
