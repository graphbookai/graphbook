from graphbook.core.note import Note
from graphbook.core.steps import SourceStep

class UrlSource(SourceStep):
    """Stores a web page URL for use in a workflow.

    Args:
        url (str): The URL of the page to use in a workflow.
    """
    RequiresInput = False
    Parameters = {
        "url": {
            "type": "string",
            "default": "https://www.graphbook.ai/"
        }
    }
    Outputs = ["url"]
    Category = "Custom"
    def __init__(self, url):
        super().__init__()
        self.url = url

    def load(self):
        return {
            "url": [Note({"url": self.url})]
        }

    def route(self, data: dict) -> str:
        return "url"
