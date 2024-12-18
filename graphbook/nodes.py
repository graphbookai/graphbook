from typing import Tuple
from . import steps, resources
from .doc2md import convert_to_md
from aiohttp import web
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
import importlib
import importlib.util
import hashlib
import sys
import os
import os.path as osp
import inspect
import traceback
from .decorators import get_steps, get_resources
from .viewer import ViewManager


BUILT_IN_STEPS = [
    steps.Step,
    steps.BatchStep,
    steps.PromptStep,
    steps.SourceStep,
    steps.GeneratorSourceStep,
    steps.AsyncStep,
    steps.Split,
    steps.SplitNotesByItems,
    steps.SplitItemField,
    steps.Copy,
]
BUILT_IN_RESOURCES = [
    resources.Resource,
    resources.NumberResource,
    resources.FunctionResource,
    resources.ListResource,
    resources.DictResource,
]

default_exported_steps = {
    "Split": steps.Split,
    "SplitNotesByItems": steps.SplitNotesByItems,
    "SplitItemField": steps.SplitItemField,
    "Copy": steps.Copy,
    "DumpJSONL": steps.DumpJSONL,
    "LoadJSONL": steps.LoadJSONL,
}

default_exported_resources = {
    "Text": resources.Resource,
    "Number": resources.NumberResource,
    "Function": resources.FunctionResource,
    "List": resources.ListResource,
    "Dict": resources.DictResource,
}


class NodeHub:
    def __init__(self, path: str, plugins: Tuple[dict, dict], view_manager: ViewManager):
        self.exported_steps = default_exported_steps
        self.exported_resources = default_exported_resources
        self.view_manager = view_manager
        self.custom_node_importer = CustomNodeImporter(
            path, self.handle_step, self.handle_resource, self.handle_module
        )
        plugin_steps, plugin_resources = plugins
        for plugin in plugin_steps:
            self.exported_steps.update(plugin_steps[plugin])
        for plugin in plugin_resources:
            self.exported_resources.update(plugin_resources[plugin])

    def start(self):
        self.custom_node_importer.start_observer()

    def stop(self):
        self.custom_node_importer.stop_observer()
        
    def handle_module(self, filename, module):
        self.view_manager.set_state("node_updated")

    def handle_step(self, filename, name, step):
        print(f"{filename}: {name} (step)")
        self.exported_steps[name] = step

    def handle_resource(self, filename, name, resource):
        print(f"{filename}: {name} (resource)")
        self.exported_resources[name] = resource

    def get_steps(self):
        return self.exported_steps

    def get_resources(self):
        return self.exported_resources

    def get_all(self):
        return {"steps": self.get_steps(), "resources": self.get_resources()}

    def get_step_docstring(self, name):
        if name in self.exported_steps:
            docstring = self.exported_steps[name].__doc__
            if docstring is not None:
                docstring = convert_to_md(docstring)
                return docstring
        return None

    def get_resource_docstring(self, name):
        if name in self.exported_resources:
            docstring = self.exported_resources[name].__doc__
            if docstring is not None:
                docstring = convert_to_md(docstring)
                return docstring
        return None

    def get_exported_nodes(self):
        # Create directory structure for nodes based on their category
        def create_dir_structure(nodes):
            node_tree = {}
            for node_name in nodes:
                node = nodes[node_name]
                if node["category"] == "":
                    node_tree[node_name] = node
                else:
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


class CustomModuleEventHandler(FileSystemEventHandler):
    def __init__(self, root_path, handler):
        super().__init__()
        self.root_path = osp.abspath(root_path)
        self.handler = handler
        self.ha = {}

    def on_created(self, event):
        if event.is_directory:
            return
        self.handle_new_file(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self.handle_new_file(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self.handle_new_file(event.dest_path)

    def handle_new_file(self, filename: str):
        filename = osp.abspath(filename)
        assert filename.startswith(
            self.root_path
        ), f"Received extraneous file {filename} during tracking of {self.root_path}"
        if not filename.endswith(".py"):
            return

        with open(filename, "r") as f:
            contents = f.read()

        hash_code = hashlib.md5(contents.encode()).hexdigest()
        og_hash_code = self.ha.get(filename, None)
        if hash_code == og_hash_code:
            return

        self.ha[filename] = hash_code
        filename = filename[len(self.root_path) + 1 :]
        components = filename[: filename.index(".py")].split("/")
        module_name = ".".join(components)

        try:
            if og_hash_code is None:
                importlib.import_module(module_name)
            else:
                module = importlib.import_module(module_name)
                importlib.reload(module)
        except Exception as e:
            print(f"Error loading {module_name}:")
            traceback.print_exc()
            return

        module = sys.modules[module_name]
        self.handler(filename, module)

    def init_custom_nodes(self):
        for root, dirs, files in os.walk(self.root_path):
            for file in files:
                self.handle_new_file(osp.join(root, file))

class CustomNodeImporter:
    def __init__(self, path, step_handler, resource_handler, module_handler):
        self.websocket = None
        self.path = path
        self.step_handler = step_handler
        self.resource_handler = resource_handler
        self.module_handler = module_handler
        sys.path.append(path)
        self.observer = Observer()
        self.event_handler = CustomModuleEventHandler(path, self.on_module)
        self.event_handler.init_custom_nodes()

    def on_module(self, filename, mod):
        for name, obj in inspect.getmembers(mod):
            if inspect.isclass(obj):
                if issubclass(obj, steps.Step) and not obj in BUILT_IN_STEPS:
                    self.step_handler(filename, name, obj)
                if issubclass(obj, resources.Resource) and not obj in BUILT_IN_RESOURCES:
                    self.resource_handler(filename, name, obj)

        for name, cls in get_steps().items():
            self.step_handler(filename, name, cls)
        for name, cls in get_resources().items():
            self.resource_handler(filename, name, cls)
            
        self.module_handler(filename, mod)            

    def start_observer(self):
        self.observer.schedule(self.event_handler, self.path, recursive=True)
        self.observer.start()

    def stop_observer(self):
        self.observer.stop()
        self.observer.join()
