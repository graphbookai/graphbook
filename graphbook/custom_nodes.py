import asyncio
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
import importlib
import importlib.util
import hashlib
import sys
import os
import os.path as osp
import inspect
from graphbook.steps import (
    Step,
    BatchStep,
    SourceStep,
    AsyncStep,
    Split,
    SplitNotesByItems,
    SplitItemField,
)
from graphbook.resources import Resource, FunctionResource

BUILT_IN_STEPS = [
    Step,
    BatchStep,
    SourceStep,
    AsyncStep,
    Split,
    SplitNotesByItems,
    SplitItemField,
]
BUILT_IN_RESOURCES = [Resource, FunctionResource]


class CustomModuleEventHandler(FileSystemEventHandler):
    def __init__(self, root_path, handler):
        super().__init__()
        self.root_path = osp.abspath(root_path)
        self.handler = handler
        self.ha = {}

    def on_created(self, event):
        if event.is_directory:
            return
        self.handle_new_file_sync(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self.handle_new_file_sync(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self.handle_new_file_sync(event.dest_path)

    async def handle_new_file(self, filename: str):
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
                print("Loaded", module_name)
            else:
                module = importlib.import_module(module_name)
                importlib.reload(module)
                print("Reloaded", module_name)
        except Exception as e:
            print(f"Error loading {module_name}: {e}")
            return

        module = sys.modules[module_name]
        await self.handler(filename, module)

    def handle_new_file_sync(self, filename: str):
        asyncio.run(self.handle_new_file(filename))

    async def init_custom_nodes(self):
        for root, dirs, files in os.walk(self.root_path):
            for file in files:
                await self.handle_new_file(osp.join(root, file))

    def init_custom_nodes_sync(self):
        asyncio.run(self.init_custom_nodes())


class CustomNodeImporter:
    def __init__(self, path, step_handler, resource_handler):
        self.websocket = None
        self.path = path
        self.step_handler = step_handler
        self.resource_handler = resource_handler
        sys.path.append(path)
        self.observer = Observer()
        self.event_handler = CustomModuleEventHandler(path, self.on_module)
        self.event_handler.init_custom_nodes_sync()

    def set_websocket(self, websocket):
        self.websocket = websocket

    async def on_module(self, filename, mod):
        for name, obj in inspect.getmembers(mod):
            if inspect.isclass(obj):
                if issubclass(obj, Step) and not obj in BUILT_IN_STEPS:
                    await self.step_handler(filename, name, obj)
                if issubclass(obj, Resource) and not obj in BUILT_IN_RESOURCES:
                    await self.resource_handler(filename, name, obj)

        if self.websocket is not None and not self.websocket.closed:
            await self.websocket.send_json({"type": "node_updated"})

    def start_observer(self):
        self.observer.schedule(self.event_handler, self.path, recursive=True)
        self.observer.start()

    def stop_observer(self):
        self.observer.stop()
        self.observer.join()
