from graphbook.core.resources import Resource

class PersonalInfo(Resource):
    """
    This resource is used to store the personal information of the user. Currently,
    this only contains the API key for the Firecrawl API.
    
    Args:
        api_key (str): The API key for the Firecrawl API.
    """
    RequiresInput = False
    Parameters = {
        "api_key": {
            "type": "string",
            "default": "<API_KEY_HERE>"
        }
    }
    Outputs = ["api_key"]
    Category = "Custom"
    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def value(self) -> str:
        return self.api_key
