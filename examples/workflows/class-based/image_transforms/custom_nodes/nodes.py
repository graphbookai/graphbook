# import graphbook_huggingface
# from graphbook_huggingface import HuggingfaceDataset
from PIL import Image
from graphbook.core.steps import Step
from torchvision.transforms.v2 import RandomHorizontalFlip, RandomResizedCrop, ColorJitter, Compose

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
    Outputs = ["image"]
    Category = "Transform"
    
    def __init__(self, p=0.5):
        super().__init__()
        self.p = p
        self.image = None

    def on_data(self, image: Image):
        transform = RandomHorizontalFlip(p=self.p)
        self.image = transform(image)
        self.log("Applied horizontal flip to image.")
        
    def route(self, data: dict) -> str:
        return "image"
    
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
    Outputs = ["image"]
    Category = "Transform"
    
    def __init__(self, size=(224, 224), scale=(0.08, 1.0), ratio=(3. / 4., 4. / 3.)):
        super().__init__()
        self.size = size
        self.scale = scale
        self.ratio = ratio
        self.image = None

    def on_data(self, image: Image):
        transform = RandomResizedCrop(size=self.size, scale=self.scale, ratio=self.ratio)
        self.image = transform(image)
        self.log("Applied random resized crop to image.")
        
    def route(self, data: dict) -> str:
        return "image"
