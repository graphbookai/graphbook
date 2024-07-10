from .base import Step, SourceStep, DataRecord, DataItem, StepOutput
import json
import os
import os.path as osp

class LoadJSONAsDataRecords(SourceStep):
    RequiresInput = False
    Parameters = {
        "json_path": {
            "type": "resource",
        }
    }
    Outputs = ["out"]
    Category = "IO/Import"
    def __init__(self, id, logger, json_path):
        super().__init__(id, logger)
        self.json_path = json_path

    def load(self) -> StepOutput:
        with open(self.json_path, 'r') as f:
            data = json.load(f)
        records = [DataRecord(k, v, v.get("items", {})) for k, v in data.items()]
        return {
            "out": records
        }

class LoadJSON(SourceStep):
    RequiresInput = False
    Parameters = {
        "json_path": {
            "type": "resource",
        }
    }
    Outputs = ["out"]
    Category = "IO/Import"
    def __init__(self, id, logger, json_path):
        super().__init__(id, logger)
        self.json_path = json_path

    def load(self) -> StepOutput:
        with open(self.json_path, 'r') as f:
            data = json.load(f)
        records = [DataRecord(k, v.get("annotation", {}), v.get("items", {})) for k, v in data.items()]
        return {
            "out": records
        }

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
        with open(self.jsonl_path, 'r') as f:
            data = [json.loads(line) for line in f][self.start_from:]
        records = [DataRecord(entry.get("key"), entry.get("annotation"), entry.get("items")) for entry in data]
        return {
            "out": records
        }

class LoadImageDataset(SourceStep):
    RequiresInput = False
    Parameters = {
        "image_dir": {
            "type": "string",
        }
    }
    Outputs = ["out"]
    Category = "IO/Import"
    def __init__(self, id, logger, image_dir):
        super().__init__(id, logger)
        self.image_dir = image_dir

    def create_datarecord(self, subdir):
        key = subdir
        subdir = osp.join(self.image_dir, subdir)
        images = [osp.join(subdir, s) for s in os.listdir(subdir)]
        items = {"image": [DataItem(image) for image in images]}
        return DataRecord(key, items=items)

    def load(self) -> StepOutput:
        image_subdirs = os.listdir(self.image_dir)
        records = [self.create_datarecord(subdir) for subdir in image_subdirs]
        return {
            "out": records
        }

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

    def on_after_items(self, data_record: DataRecord):
        with open(self.jsonl_path, 'a') as f:
            record_entry = data_record.json()
            json.dump(record_entry, f)
            f.write("\n")
