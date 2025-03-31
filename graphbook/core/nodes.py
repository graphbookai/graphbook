from typing import Tuple, Optional
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from pathlib import Path
import importlib
import importlib.util
import hashlib
import os
import inspect
import traceback
from graphbook.core import steps, resources
from graphbook.core.doc2md import convert_to_md
from graphbook.core.viewer import MultiGraphViewManager


BUILT_IN_STEPS = [
    steps.Step,
    steps.BatchStep,
    steps.PromptStep,
    steps.SourceStep,
    steps.GeneratorSourceStep,
    steps.AsyncStep,
    steps.Split,
    steps.SplitByItems,
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
    "SplitByItems": steps.SplitByItems,
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
    def __init__(
        self,
        plugins: Tuple[dict, dict],
        view_manager: MultiGraphViewManager,
        path: Optional[Path] = None,
    ):
        self.exported_steps = default_exported_steps
        self.exported_resources = default_exported_resources
        self.view_manager = view_manager
        if path:
            self.custom_node_importer = CustomNodeImporter(
                path, self.handle_step, self.handle_resource, self.handle_module
            )
        else:
            self.custom_node_importer = None
        plugin_steps, plugin_resources = plugins
        for plugin in plugin_steps:
            self.exported_steps.update(plugin_steps[plugin])
        for plugin in plugin_resources:
            self.exported_resources.update(plugin_resources[plugin])

    def start(self):
        if self.custom_node_importer:
            self.custom_node_importer.start_observer()

    def stop(self):
        if self.custom_node_importer:
            if self.custom_node_importer.observer.is_alive():
                self.custom_node_importer.stop_observer()

    def handle_module(self, filename, module):
        self.view_manager.set_state(None, "node_updated")

    def handle_step(self, filename: Path, name: str, step: steps.Step):
        print(f"{filename.name}: {name} (step)")
        self.exported_steps[name] = step

    def handle_resource(self, filename: Path, name: str, resource: resources.Resource):
        print(f"{filename.name}: {name} (resource)")
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

        step_catalog = {
            k: {
                "name": k,
                "parameters": getattr(v, "Parameters", {}),
                "inputs": ["in"] if not issubclass(v, steps.SourceStep) else [],
                "outputs": getattr(v, "Outputs", ["out"]),
                "category": getattr(v, "Category", ""),
                "doc": v.__doc__.strip() if v.__doc__ else "",
                "module": v.__module__,
            }
            for k, v in self.get_steps().items()
        }
        resource_catalog = {
            k: {
                "name": k,
                "parameters": getattr(v, "Parameters", {}),
                "category": getattr(v, "Category", ""),
                "doc": v.__doc__.strip() if v.__doc__ else "",
                "module": v.__module__,
            }
            for k, v in self.get_resources().items()
        }

        return {
            "steps": create_dir_structure(step_catalog),
            "resources": create_dir_structure(resource_catalog),
        }


class CustomModuleEventHandler(FileSystemEventHandler):
    def __init__(self, root_path: Path, handler: callable):
        super().__init__()
        self.root_path = Path(root_path).absolute()
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
        filepath = Path(filename)
        if not filepath.suffix == ".py":
            return

        contents = filepath.read_text()
        hash_code = hashlib.md5(contents.encode()).hexdigest()
        og_hash_code = self.ha.get(filename, None)
        if hash_code == og_hash_code:
            return

        self.ha[filename] = hash_code
        try:
            module_spec = importlib.util.spec_from_file_location(
                "transient_module", filepath
            )
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
        except Exception:
            print(f"Error loading {filename}:")
            traceback.print_exc()
            return

        self.handler(filepath, module)

    def init_custom_nodes(self):
        for root, dirs, files in os.walk(self.root_path):
            for file in files:
                self.handle_new_file(Path(root).joinpath(file))


class CustomNodeImporter:
    def __init__(
        self,
        path: Path,
        step_handler: callable,
        resource_handler: callable,
        module_handler: callable,
    ):
        self.websocket = None
        self.path = path
        self.step_handler = step_handler
        self.resource_handler = resource_handler
        self.module_handler = module_handler
        self.observer = Observer()
        self.event_handler = CustomModuleEventHandler(path, self.on_module)
        self.event_handler.init_custom_nodes()

    def on_module(self, filename: Path, mod):
        for name, obj in inspect.getmembers(mod):
            if inspect.isclass(obj):
                if issubclass(obj, steps.Step) and not obj in BUILT_IN_STEPS:
                    self.step_handler(filename, obj.__name__, obj)
                if (
                    issubclass(obj, resources.Resource)
                    and not obj in BUILT_IN_RESOURCES
                ):
                    self.resource_handler(filename, obj.__name__, obj)

        self.module_handler(filename, mod)

    def start_observer(self):
        self.observer.schedule(self.event_handler, self.path, recursive=True)
        self.observer.start()

    def stop_observer(self):
        self.observer.stop()
        self.observer.join()
