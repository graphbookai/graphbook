import json
from .utils import is_batchable
from typing import Iterable
from torch import Tensor

# class DataItem:
#     """
#     Data structure containing the text, audio, image, or video coupled with its annotation.

#     Args:
#         item (str): A path to media, string of text, or the actual data item to store
#         type (str): Optional string to specify the type of data this is
#         annotation (dict): A dictionary of annotations for this item

#     Example:
#         .. highlight:: python
#         .. code-block:: python

#             d = DataItem("path/to/image.jpg", "image", {"prediction": "dog"})
#     """

#     def __init__(self, item, type=None, annotation={}):
#         self.item = item
#         self.type = type
#         self.annotation = annotation

#     def __str__(self):
#         return f"{'('+self.type+')' if self.type else ''}Item {self.item}: Annotations: {self.annotation}"

#     def json(self):
#         """
#         Returns DataItem into a serialized JSON format
#         """
#         return {"item": self.item, "type": self.type, "annotation": self.annotation}


class Note:
    """
    The unit that passes through workflow steps. A Note contains a dictionary of items related to the record.

    Args:
        items (Dict[str, any]): An optional dictionary of items to store in the Note

    Example:
        .. highlight:: python
        .. code-block:: python

            d = Note( {"images": [PIL.Image("image_of_dog.png")]} )
    """

    def __init__(self, items: dict = {}):
        self.items = items

    def __setitem__(self, key: str, value: str):
        """
        A convenient function to add an item to the note

        Args:
            key (str): The item key
            value (str): The value of the item
        """
        self.items[key] = value
        
    def __getitem__(self, key: str):
        """
        A convenient function to retrieve an item

        Args:
            item_key (str): The item key to retrieve from
        """
        return self.items.get(key)
    
    def annotate(self, key: str, index: int, annotation: str):
        """
        Should only use if item at key is an iterable or Tensor. Otherwise, use __setitem__. Annotates an item in the note.
        The string annotation will be stored in the Note as an item with key being *"{item_key}_annotation"* at index.

        Args:
            item_key (str): The item key to annotate
            annotation (dict): The annotation to add to the item
        """
        to_be_annotated = self.items.get(key)
        if not to_be_annotated:
            return None
        if not is_batchable(to_be_annotated):
            return None
        annotation_key = f"{key}_annotation"
        annotations = self.items.get(annotation_key)
        n = len(to_be_annotated)
        if not annotations:
            self.items[annotation_key] = [None for _ in range(n)]
        
        self.items[annotation_key][index] = annotation

    def __str__(self):
        return json.dumps(self.items, indent=2)
