from .base import Step, SourceStep, StepOutput
import json


class LoadJSONL(SourceStep):
    """
    Loads input JSONL file and returns a list of dict objects.

    Args:
        jsonl_path (str): Path to the JSONL file.
    """

    RequiresInput = False
    Parameters = {
        "jsonl_path": {
            "type": "resource",
        }
    }
    Outputs = ["out"]
    Category = "IO/Import"

    def __init__(self, jsonl_path, start_from=0):
        super().__init__()
        self.jsonl_path = jsonl_path
        self.start_from = start_from

    def load(self) -> StepOutput:
        with open(self.jsonl_path, "r") as f:
            data = [json.loads(line) for line in f][self.start_from :]
        return {"out": data}


class DumpJSONL(Step):
    """
    Writes dict objects as individual JSONs into a JSONL file.

    Args:
        jsonl_path (str): Path to the JSONL file.
    """

    RequiresInput = True
    Parameters = {
        "jsonl_path": {
            "type": "resource",
        }
    }
    Outputs = ["out"]
    Category = "IO/Export"

    def __init__(self, jsonl_path):
        super().__init__()
        self.jsonl_path = jsonl_path

    def on_after_item(self, data: dict):
        with open(self.jsonl_path, "a") as f:
            json.dump(data, f)
            f.write("\n")
