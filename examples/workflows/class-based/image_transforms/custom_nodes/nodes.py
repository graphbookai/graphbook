import torch
import torchvision.transforms.v2 as v2
from torchvision.transforms.v2 import RandomHorizontalFlip, RandomResizedCrop
from torchvision.transforms.v2 import ColorJitter as PyColorJitter

from graphbook import utils
from graphbook.core.steps import Step

class HorizontalFlip(Step):
    """
    Applies a horizontal flip to an image.
    
    Args:
        p (float): Probability of applying the flip.
    """
    RequiresInput = True
    Parameters = {
        "p": {"type": "number", "default": 0.5}
    }
    Outputs = ["out"]
    Category = "Transform"
    
    def __init__(self, p=0.5):
        super().__init__()
        self.p = p

    def on_data(self, data: dict):
        transform = RandomHorizontalFlip(p=self.p)
        data["img"] = utils.image(transform(data["image"]))
        self.log("Applied horizontal flip to image.")
    
class ResizedCrop(Step):
    """
    Applies a random resized crop to an image.
    
    Args:
        size (tuple): Desired output size of the crop (height, width).
        scale (tuple): Range of size of the origin size cropped.
        ratio (tuple): Range of aspect ratio of the crop.
    """
    RequiresInput = True
    Parameters = {
        "size": {"type": "array", "default": [224, 224]},
        "scale": {"type": "array", "default": [0.08, 1.0]},
        "ratio": {"type": "array", "default": [3. / 4., 4. / 3.]}
    }
    Outputs = ["out"]
    Category = "Transform"
    
    def __init__(self, size=(224, 224), scale=(0.08, 1.0), ratio=(3. / 4., 4. / 3.)):
        super().__init__()
        self.size = size
        self.scale = scale
        self.ratio = ratio

    def on_data(self, data: dict):
        transform = RandomResizedCrop(size=self.size, scale=self.scale, ratio=self.ratio)
        data["img"] = utils.image(transform(data["img"]["value"]))
        self.log("Applied random resized crop to image.")
        

class ColorJitter(Step):
    """
    Applies a color jitter to an image.
    
    Args:
        brightness (float): How much to jitter brightness.
        contrast (float): How much to jitter contrast.
        saturation (float): How much to jitter saturation.
        hue (float): How much to jitter hue.
    """
    RequiresInput = True
    Parameters = {
        "brightness": {"type": "number", "default": 0.5},
        "contrast": {"type": "number", "default": 0.5},
        "saturation": {"type": "number", "default": 0.5},
        "hue": {"type": "number", "default": 0.5}
    }
    Outputs = ["out"]
    Category = "Transform"
    
    def __init__(self, brightness=0.5, contrast=0.5, saturation=0.5, hue=0.5):
        super().__init__()
        self.brightness = brightness
        self.contrast = contrast
        self.saturation = saturation
        self.hue = hue

    def on_data(self, data: dict):
        transform = PyColorJitter(brightness=self.brightness, contrast=self.contrast, saturation=self.saturation, hue=self.hue)
        data["img"] = utils.image(transform(data["img"]["value"]))
        self.log("Applied color jitter to image.")

class Normalize(Step):
    """
    Normalizes the image.
    
    Args:
        mean (list): Sequence of means for each channel.
        std (list): Sequence of standard deviations for each channel.
    """
    RequiresInput = True
    Parameters = {
        "mean": {"type": "array", "default": [0.485, 0.456, 0.406]},
        "std": {"type": "array", "default": [0.229, 0.224, 0.225]}
    }
    Outputs = ["out"]
    Category = "Transform"
    
    def __init__(self, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]):
        super().__init__()
        self.mean = mean
        self.std = std

    def on_data(self, data: dict):
        transform_norm = v2.Compose([
            v2.ToImage(),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(self.mean, self.std)
        ])
        im = data["img"]["value"]
        if im.mode == "RGBA":
            im = im.convert("RGB")
        data["norm"] = transform_norm(im)

        self.log("Normalized image.")