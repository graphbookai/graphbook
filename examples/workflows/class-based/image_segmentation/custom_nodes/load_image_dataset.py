from graphbook.steps import SourceStep
from graphbook import Note
import torchvision.transforms.functional as F
import os
import os.path as osp


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

        def create_note(subdir):
            image_dir = osp.join(self.image_dir, subdir)
            return Note(
                {
                    "name": subdir,
                    "image": [
                        {"value": osp.join(image_dir, img), "type": "image"}
                        for img in os.listdir(image_dir)
                    ],
                }
            )

        return {"out": [create_note(subdir) for subdir in subdirs]}
