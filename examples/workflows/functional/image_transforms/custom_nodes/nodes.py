import torch
import torchvision.transforms.v2 as v2
from torchvision.transforms.v2 import RandomHorizontalFlip, RandomResizedCrop
from torchvision.transforms.v2 import ColorJitter as PyColorJitter

from graphbook import utils
from graphbook import step, param, output

@step("Transform/HorizontalFlip")
@param("p", type="number", default=0.5)
@output("out")
def horizontal_flip(ctx, data: dict):
    """Applies a horizontal flip to an image."""
    transform = RandomHorizontalFlip(p=ctx.p)
    data["img"] = utils.image(transform(data["image"]))
    ctx.log("Applied horizontal flip to image.")
    

@step("Transform/ResizedCrop")
@param("size", type="array", default=[224, 224])
@param("scale", type="array", default=[0.08, 1.0])
@param("ratio", type="array", default=[3. / 4., 4. / 3.])
@output("out")
def resized_crop(ctx, data: dict):
    """Applies a random resized crop to an image."""
    transform = RandomResizedCrop(size=ctx.size, scale=ctx.scale, ratio=ctx.ratio)
    data["img"] = utils.image(transform(data["img"]["value"]))
    ctx.log("Applied random resized crop to image.")
    
@step("Transform/ColorJitter")
@param("brightness", type="number", default=0.5)
@param("contrast", type="number", default=0.5)
@param("saturation", type="number", default=0.5)
@param("hue", type="number", default=0.5)
@output("out")
def color_jitter(ctx, data: dict):
    """Applies a color jitter to an image. """
    transform = PyColorJitter(brightness=ctx.brightness, contrast=ctx.contrast, saturation=ctx.saturation, hue=ctx.hue)
    data["img"] = utils.image(transform(data["img"]["value"]))
    ctx.log("Applied color jitter to image.")
    
@step("Transform/Normalize")
@param("mean", type="array", default=[0.485, 0.456, 0.406])
@param("std", type="array", default=[0.229, 0.224, 0.225])
@output("out")
def normalize(ctx, data: dict):
    """Normalizes the image."""
    transform_norm = v2.Compose([
        v2.ToImage(),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(ctx.mean, ctx.std)
    ])
    im = data["img"]["value"]
    if im.mode == "RGBA":
        im = im.convert("RGB")
    data["norm"] = transform_norm(im)

    ctx.log("Normalized image.")