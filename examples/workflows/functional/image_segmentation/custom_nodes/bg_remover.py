from graphbook import step, resource, param, batch, event
from transformers import AutoModelForImageSegmentation
import torchvision.transforms.functional as F
import torch.nn.functional
import torch
from typing import List
from PIL import Image
import os
import os.path as osp


@resource("Custom/RMBGModel")
@param(
    "model_name",
    type="string",
    description="The name of the model.",
    default="briaai/RMBG-1.4",
)
def rmbg_model(ctx):
    """
    The RMBGModel resource is used to load a model for removing the background from images.

    Args:
        model_name (str): The name of the model from Huggingface.
    """
    return AutoModelForImageSegmentation.from_pretrained(
        ctx.model_name, trust_remote_code=True
    ).to("cuda")


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


@staticmethod
def empty_cache():
    torch.cuda.empty_cache()


def init_output_dir(ctx, **kwargs):
    os.makedirs(ctx.output_dir, exist_ok=True)


@step("Custom/RemoveBackground")
@batch(4, "image")
@event("load_fn", load_fn)
@event("dump_fn", dump_fn)
@event("on_start", empty_cache)
@event("__init__", init_output_dir)
@param("model", type="resource")
@param("output_dir", type="string")
@torch.no_grad()
def remove_background(
    self, tensors: List[torch.Tensor], items: List[dict], data: List[dict]
):
    """
    The background remover step uses the input model to remove the background from images.

    Args:
        batch_size (int): The batch size for the model.
        item_key (str): The key to use for the image in the input dict.
        model (AutoModelForImageSegmentation): The model to use for background removal.
        output_dir (str): The directory to save the output images.
    """

    def get_output_path(data, input_path):
        return osp.join(self.output_dir, data["name"], osp.basename(input_path))

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
    paths = [get_output_path(data, input["value"]) for input, d in zip(items, data)]
    removed_bg = list(zip(resized, paths))
    for path, d in zip(paths, data):
        masks = d["masks"]
        if masks is None:
            masks = []
        masks.append({"value": path, "type": "image"})
        d["masks"] = masks

    return removed_bg
