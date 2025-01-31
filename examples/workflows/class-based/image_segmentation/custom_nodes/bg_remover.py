from graphbook.steps import BatchStep
from graphbook.resources import Resource
from graphbook import Note
from transformers import AutoModelForImageSegmentation
import torchvision.transforms.functional as F
import torch.nn.functional
import torch
from typing import List, Tuple
from PIL import Image
import os
import os.path as osp


class RMBGModel(Resource):
    """
    The RMBGModel resource is used to load a model for removing the background from images.
    
    Args:
        model_name (str): The name of the model from Huggingface.
    """

    Category = "Custom"
    Parameters = {
        "model_name": {
            "type": "string",
            "description": "The name of the image processor.",
        }
    }

    def __init__(self, model_name: str):
        super().__init__(
            AutoModelForImageSegmentation.from_pretrained(
                model_name, trust_remote_code=True
            ).to("cuda")
        )


class RemoveBackground(BatchStep):
    """
    The background remover step uses the input model to remove the background from images.
    
    Args:
        batch_size (int): The batch size for the model.
        item_key (str): The key to use for the image in the input Note.
        model (AutoModelForImageSegmentation): The model to use for background removal.
        output_dir (str): The directory to save the output images.
    """

    RequiresInput = True
    Parameters = {
        "model": {
            "type": "resource",
        },
        "batch_size": {
            "type": "number",
            "default": 8,
        },
        "item_key": {
            "type": "string",
            "default": "image",
        },
        "output_dir": {
            "type": "string",
        },
    }
    Outputs = ["out"]
    Category = "Custom"

    def __init__(
        self,
        batch_size,
        item_key,
        output_dir,
        model: AutoModelForImageSegmentation,
    ):
        super().__init__(batch_size, item_key)
        self.model = model
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def on_start(self):
        torch.cuda.empty_cache()

    @staticmethod
    def load_fn(item: dict) -> torch.Tensor:
        im = Image.open(item["value"])
        image = F.to_tensor(im)
        if image.shape[0] == 1:
            image = image.repeat(3, 1, 1)
        elif image.shape[0] == 4:
            image = image[:3]

        return image

    @staticmethod
    def dump_fn(t: torch.Tensor, output_path: str):
        dir = osp.dirname(output_path)
        os.makedirs(dir, exist_ok=True)
        img = F.to_pil_image(t)
        img.save(output_path)

    def get_output_path(self, note, input_path):
        return osp.join(self.output_dir, note["name"], osp.basename(input_path))

    @torch.no_grad()
    def on_item_batch(
        self, tensors: List[torch.Tensor], items: List[dict], notes: List[Note]
    ):
        og_sizes = [t.shape[1:] for t in tensors]

        images = [
            F.normalize(
                torch.nn.functional.interpolate(
                    torch.unsqueeze(image, 0), size=[1024, 1024], mode="bilinear"
                ),
                [0.5, 0.5, 0.5],
                [1.0, 1.0, 1.0],
            )
            for image in tensors
        ]
        images = torch.stack(images).to("cuda")
        images = torch.squeeze(images, 1)
        tup = self.model(images)
        result = tup[0][0]
        ma = torch.max(result)
        mi = torch.min(result)
        result = (result - mi) / (ma - mi)
        resized = [
            torch.squeeze(
                torch.nn.functional.interpolate(
                    torch.unsqueeze(image, 0), size=og_size, mode="bilinear"
                ),
                0,
            ).cpu()
            for image, og_size in zip(result, og_sizes)
        ]
        paths = [
            self.get_output_path(note, input["value"])
            for input, note in zip(items, notes)
        ]
        removed_bg = list(zip(resized, paths))
        for path, note in zip(paths, notes):
            masks = note["masks"]
            if masks is None:
                masks = []
            masks.append({"value": path, "type": "image"})
            note["masks"] = masks

        return removed_bg
