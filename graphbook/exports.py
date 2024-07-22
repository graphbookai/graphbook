import graphbook.steps as steps
import graphbook.resources.base as rbase
import graphbook.custom_nodes as custom_nodes
from aiohttp import web

default_exported_steps = {
    "Split": steps.Split,
    "SplitNotesByItems": steps.SplitNotesByItems,
    "SplitItemField": steps.SplitItemField,
    "DumpJSONL": steps.DumpJSONL,
    "LoadJSONL": steps.LoadJSONL,
}

default_exported_resources = {
    "Text": rbase.Resource,
    "Number": rbase.NumberResource,
    "Function": rbase.FunctionResource,
}


class NodeHub:
    def __init__(self, path):
        self.exported_steps = default_exported_steps
        self.exported_resources = default_exported_resources
        self.custom_node_importer = custom_nodes.CustomNodeImporter(
            path, self.handle_step, self.handle_resource
        )

    def start(self):
        self.custom_node_importer.start_observer()

    def stop(self):
        self.custom_node_importer.stop_observer()

    async def handle_step(self, filename, name, step):
        if name in self.exported_steps:
            print(f"Reloading custom step node {name} from {filename}")
        else:
            print(f"Loading custom step node {name} from {filename}")
        self.exported_steps[name] = step

    async def handle_resource(self, filename, name, resource):
        if name in self.exported_resources:
            print(f"Reloading custom resource node {name} from {filename}")
        else:
            print(f"Loading custom resource node {name} from {filename}")
        self.exported_resources[name] = resource

    def get_steps(self):
        return self.exported_steps

    def get_resources(self):
        return self.exported_resources

    def get_all(self):
        return {"steps": self.get_steps(), "resources": self.get_resources()}

    def get_exported_nodes(self):
        # Create directory structure for nodes based on their category
        def create_dir_structure(nodes):
            node_tree = {}
            for node_name in nodes:
                node = nodes[node_name]
                category_tree = node["category"].split("/")
                curr_category = node_tree
                for category in category_tree:
                    if curr_category.get(category) is None:
                        curr_category[category] = {"children": {}}
                    curr_category = curr_category[category]["children"]
                curr_category[node_name] = node
            return node_tree

        steps = {
            k: {
                "name": k,
                "parameters": v.Parameters,
                "inputs": ["in"] if v.RequiresInput else [],
                "outputs": v.Outputs,
                "category": v.Category,
            }
            for k, v in self.get_steps().items()
        }
        resources = {
            k: {
                "name": k,
                "parameters": v.Parameters,
                "category": v.Category,
            }
            for k, v in self.get_resources().items()
        }

        return {
            "steps": create_dir_structure(steps),
            "resources": create_dir_structure(resources),
        }

    def set_websocket(self, websocket: web.WebSocketResponse):
        self.custom_node_importer.set_websocket(websocket)
