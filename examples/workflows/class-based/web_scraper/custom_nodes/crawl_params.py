from graphbook.core.note import Note
from graphbook.core.resources import Resource

class CrawlParams(Resource):
    """
    This resource is used to store the parameters for link traversal using depth-first search.
    
    Args:
        max_depth (int): The maximum depth of link traversal.
    """
    RequiresInput = False
    Parameters = {
        "max_depth": {
            "type": "number",
            "default": 3
        }
    }
    Outputs = ["max_depth"]
    Category = "Custom"
    def __init__(self, max_depth):
        super().__init__()
        self.max_depth = max_depth

    def value(self) -> str:
        return self.max_depth
