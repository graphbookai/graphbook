from ..utils import ExecutionContext
from ..steps.base import log

class Resource:
    """
    The base class for all resources in Graphbook. All resources should be a descendant from this class. Also acts as the resource for string values.
    """
    Parameters = {"val": {"type": "string"}}
    Category = "Util"

    def __init__(self, val=""):
        self.val = val
        
    def set_context(self, **context):
        """
        Sets the context of the step. This is useful for setting the node_id and node_name of the step.

        Args:
            **context: The context to set
        """
        ExecutionContext.update(**context)

    def log(self, msg, type="info"):
        """
        Logs the value of the resource.
        """
        log(msg, type)

    def value(self):
        return self.val

    def __str__(self):
        return str(self.val)

class NumberResource(Resource):
    """
    The number resource. This will parse the incoming value as a float.
    """
    Parameters = {"val": {"type": "number"}}
    Category = "Util"

    def __init__(self, val):
        super().__init__(val)
        
    def value(self):
        return float(self.val)


class FunctionResource(Resource):
    """
    The function resource. This will parse the incoming value as a function.
    """
    Parameters = {"val": {"type": "function"}}
    Category = "Util"

    def __init__(self, val):
        super().__init__(val)
        

class ListResource(Resource):
    """
    The list resource. This will parse the incoming value as a list of string.
    """
    Parameters = {"val": {"type": "list[string]"}}
    Category = "Util"

    def __init__(self, val):
        super().__init__(val)
        
    def value(self):
        return list(self.val)

class DictResource(Resource):
    """
    The list resource. This will parse the incoming value as a list of string.
    """
    Parameters = {"val": {"type": "dict"}}
    Category = "Util"

    def __init__(self, val):
        super().__init__(val)
        
    def value(self):
        return dict(self.val)
