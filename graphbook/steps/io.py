from .base import Step, SourceStep, Note, StepOutput
import json


class LoadJSONL(SourceStep):
    RequiresInput = False
    Parameters = {
        "jsonl_path": {
            "type": "resource",
        }
    }
    Outputs = ["out"]
    Category = "IO/Import"

    def __init__(self, id, logger, jsonl_path, start_from=0):
        super().__init__(id, logger)
        self.jsonl_path = jsonl_path
        self.start_from = start_from

    def load(self) -> StepOutput:
        with open(self.jsonl_path, "r") as f:
            data = [json.loads(line) for line in f][self.start_from :]
        notes = [
            Note(entry.get("key"), entry.get("annotation"), entry.get("items"))
            for entry in data
        ]
        return {"out": notes}


class DumpJSONL(Step):
    RequiresInput = True
    Parameters = {
        "jsonl_path": {
            "type": "resource",
        }
    }
    Outputs = ["out"]
    Category = "IO/Export"

    def __init__(self, id, logger, jsonl_path):
        super().__init__(id, logger)
        self.jsonl_path = jsonl_path

    def on_after_items(self, note: Note):
        with open(self.jsonl_path, "a") as f:
            note_entry = note.items
            json.dump(note_entry, f)
            f.write("\n")
