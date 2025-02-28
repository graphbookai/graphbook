from graphbook.steps import BatchStep, SourceStep
from graphbook.resources import Resource
import os
import os.path as osp
from transformers import ViTForImageClassification, ViTImageProcessor
import torch
import torchvision.transforms.functional as F
from PIL import Image
from typing import List


class PokemonClassifier(BatchStep):
    """
    The PokemonClassifier step uses the input Vision Transformer model and image processor to classify incoming images of Pokemon.

    Args:
        batch_size (int): The batch size for the model.
        item_key (str): The key to use for the image in the input.
        model (ViTForImageClassification): The Vision Transformer model to use for classification.
        image_processor (ViTImageProcessor): The image processor to use for the model
    """

    RequiresInput = True
    Parameters = {
        "batch_size": {"type": "number", "default": 8},
        "item_key": {"type": "string", "default": "image"},
        "model": {
            "type": "resource",
        },
        "image_processor": {
            "type": "resource",
        },
    }
    Outputs = ["out"]
    Category = "Custom"

    def __init__(
        self,
        batch_size,
        item_key,
        model: ViTForImageClassification,
        image_processor: ViTImageProcessor,
    ):
        super().__init__(batch_size, item_key)
        self.model = model
        self.image_processor = image_processor
        self.tp = 0
        self.num_samples = 0

    @staticmethod
    def load_fn(item: dict) -> torch.Tensor:
        im = Image.open(item["value"])
        image = F.to_tensor(im)
        if image.shape[0] == 1:
            image = image.repeat(3, 1, 1)
        elif image.shape[0] == 4:
            image = image[:3]
        return image

    @torch.no_grad()
    def on_item_batch(
        self, tensors: List[torch.Tensor], items: List[dict], pokemons: List[dict]
    ):
        extracted = self.image_processor(
            images=tensors, do_rescale=False, return_tensors="pt"
        )
        extracted = extracted.to("cuda")
        predicted_id = self.model(**extracted).logits.argmax(-1)
        for t, item, pokemon in zip(predicted_id, items, pokemons):
            item["prediction"] = self.model.config.id2label[t.item()]
            self.log(f"Predicted {item['value']} as {item['prediction']}")
            if item["prediction"] == pokemon["name"]:
                self.tp += 1
            self.num_samples += 1
        if self.num_samples > 0:
            self.log(f"Accuracy: {self.tp/self.num_samples:.2f}")


class LoadImageDataset(SourceStep):
    """
    Loads a dataset of images from a directory.

    Args:
        image_dir (str): The directory containing the images
    """

    RequiresInput = False
    Outputs = ["out"]
    Category = "Custom"
    Parameters = {"image_dir": {"type": "string", "default": "/data/pokemon"}}

    def __init__(self, image_dir: str):
        super().__init__()
        self.image_dir = image_dir

    def load(self):
        subdirs = os.listdir(self.image_dir)

        def create_dict(subdir):
            image_dir = osp.join(self.image_dir, subdir)
            return {
                    "name": subdir,
                    "image": [
                        {"value": osp.join(image_dir, img), "type": "image"}
                        for img in os.listdir(image_dir)
                    ],
                }

        return {"out": [create_dict(subdir) for subdir in subdirs]}


class ViTForImageClassificationResource(Resource):
    """
    A resource that loads a Vision Transformer model for image classification.

    Args:
        model_name (str): The name of the model to load taken from Huggingface's model hub.
    """

    Category = "Huggingface/Transformers"
    Parameters = {
        "model_name": {
            "type": "string",
            "description": "The name of the model to load.",
        }
    }

    def __init__(self, model_name: str):
        self.model = ViTForImageClassification.from_pretrained(model_name)
        self.model = self.model.to("cuda")
        super().__init__(self.model)


class ViTImageProcessorResource(Resource):
    """
    A resource that loads the corresponding image processor.

    Args:
        image_processor (str): The name of the image processor taken from Huggingface's model hub. This is typically the same as the model name.
    """

    Category = "Huggingface/Transformers"
    Parameters = {
        "image_processor": {
            "type": "string",
            "description": "The name of the image processor.",
        }
    }

    def __init__(self, image_processor: str):
        self.image_processor = ViTImageProcessor.from_pretrained(image_processor)
        super().__init__(self.image_processor)
