class Resource:
    Parameters = {"val": {"type": "string"}}
    Category = "Util"

    def __init__(self, val):
        self.val = val

    def value(self):
        return self.val

    def __str__(self):
        return str(self.val)


class NumberResource(Resource):
    Parameters = {"val": {"type": "number"}}
    Category = "Util"

    def __init__(self, val):
        super().__init__(val)
        
    def value(self):
        return float(self.val)


class FunctionResource(Resource):
    Parameters = {"val": {"type": "function"}}
    Category = "Util"

    def __init__(self, val):
        super().__init__(val)
