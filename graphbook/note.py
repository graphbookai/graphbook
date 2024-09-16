import json

class Note:
    """
    The unit that passes through workflow steps. A Note contains a dictionary of items related to the note.

    Args:
        items (Dict[str, Any]): An optional dictionary of items to store in the Note

    Examples:
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

    def __str__(self):
        return json.dumps(self.items, indent=2)
