import asyncio
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
import importlib
import importlib.util
import hashlib
import sys
import os
import os.path as osp


# This function is used to convert a string to a function
# by interpreting the string as a python-typed function
# definition. This is used to allow the user to define
# custom functions in the graphbook UI.
def transform_function_string(func_str):
    func_str = func_str.strip()
    if not func_str.startswith("def"):
        raise ValueError("Function string must start with def")
    func_name = func_str[4 : func_str.index("(")].strip()

    # Create a new module
    module_name = "my_module"
    module_spec = importlib.util.spec_from_loader(module_name, loader=None)
    module = importlib.util.module_from_spec(module_spec)

    # Execute the function string in the module's namespace
    exec(func_str, module.__dict__)

    # Return the function from the module
    return getattr(module, func_name)


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

    async def on_module(self, filename, custom_nodes):
        if "exported_steps" in dir(custom_nodes):
            for k, v in custom_nodes.exported_steps.items():
                await self.step_handler(filename, k, v)
        if "exported_resources" in dir(custom_nodes):
            for k, v in custom_nodes.exported_resources.items():
                await self.resource_handler(filename, k, v)

        if self.websocket is not None and not self.websocket.closed:
            await self.websocket.send_json({"event": "node_updated"})
        else:
            print("No websocket to send node_updated event to")

    def start_observer(self):
        self.observer.schedule(self.event_handler, self.path, recursive=True)
        self.observer.start()

    def stop_observer(self):
        self.observer.stop()
        self.observer.join()
