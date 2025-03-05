from __future__ import annotations
from typing import Any, Dict, Union, Optional
import importlib
import shutil
import subprocess
import os
import platform
import threading
import traceback
import queue
import asyncio
from PIL import Image
from .note import Note
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor

try:
    from torch import Tensor
except ImportError:
    Tensor = None


MP_WORKER_TIMEOUT = 5.0


def is_batchable(obj: Any) -> bool:
    return isinstance(obj, list) or (Tensor is not None and isinstance(obj, Tensor))


def transform_function_string(func_str: str):
    """
    This function is used to convert a string to a function
    by interpreting the string as a python-typed function
    definition. This is used to allow the user to define
    custom functions in the graphbook UI.
    """
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


def get_gpu_util():
    def safe_float_cast(strNumber):
        try:
            number = float(strNumber)
        except ValueError:
            number = float("nan")
        return number

    if platform.system() == "Windows":
        # If the platform is Windows and nvidia-smi
        # could not be found from the environment path,
        # try to find it from system drive with default installation path
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi is None:
            nvidia_smi = (
                "%s\\Program Files\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe"
                % os.environ["systemdrive"]
            )
    else:
        nvidia_smi = "nvidia-smi"

    # Get ID, processing and memory utilization for all GPUs
    try:
        p = subprocess.Popen(
            [
                nvidia_smi,
                "--query-gpu=index,uuid,utilization.gpu,memory.total,memory.used,memory.free,driver_version,name,gpu_serial,display_active,display_mode,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            stdout=subprocess.PIPE,
        )
        stdout, _ = p.communicate()
    except:
        return []

    output = stdout.decode("UTF-8")
    lines = output.split(os.linesep)
    numDevices = len(lines) - 1
    GPUs = []
    for g in range(numDevices):
        line = lines[g]
        vals = line.split(", ")
        for i in range(12):
            if i == 0:
                device_id = int(vals[i])
            # elif (i == 1):
            #     uuid = vals[i]
            elif i == 2:
                gpu_util = safe_float_cast(vals[i])
            elif i == 3:
                mem_total = safe_float_cast(vals[i])
            elif i == 4:
                mem_used = safe_float_cast(vals[i])
            # elif (i == 5):
            #     memFree = safe_float_cast(vals[i])
            # elif (i == 6):
            #     driver = vals[i]
            elif i == 7:
                gpu_name = vals[i]
            # elif (i == 8):
            #     serial = vals[i]
            # elif (i == 9):
            #     display_active = vals[i]
            # elif (i == 10):
            #     display_mode = vals[i]
            # elif (i == 11):
            #     temp_gpu = safe_float_cast(vals[i]);
        gpu_mem = (mem_used / mem_total) * 100
        GPUs.append(
            {
                "id": device_id,
                "name": gpu_name,
                "util": gpu_util,
                "mem": gpu_mem,
            }
        )
    return GPUs


def convert_dict_values_to_list(d: dict):
    for k, v in d.items():
        if not isinstance(v, list):
            d[k] = [v]


def transform_json_log(log: Any) -> Any:
    if isinstance(log, Note):
        return transform_json_log(log.items)
    if isinstance(log, dict):
        return {k: transform_json_log(v) for k, v in log.items()}
    if isinstance(log, list):
        return [transform_json_log(v) for v in log]
    if isinstance(log, tuple):
        return [transform_json_log(v) for v in log]
    if isinstance(log, set):
        return [transform_json_log(v) for v in log]
    if isinstance(log, bytes):
        return f"(bytes of length {len(log)})"
    if Tensor is not None and isinstance(log, Tensor):
        return f"(Tensor of shape {log.shape})"
    if isinstance(log, Image.Image):
        return f"(PIL Image of size {log.size})"
    if (
        isinstance(log, float)
        or isinstance(log, int)
        or isinstance(log, str)
        or isinstance(log, bool)
    ):
        return log
    if hasattr(log, "__str__"):
        return str(log)
    return "(Not JSON serializable)"


def image(path_or_pil: Union[str, Image.Image]) -> dict:
    """
    A simple helper function to create a Graphbook-recognizable image object.
    A path to an image file or a PIL Image object is supported for rendering in the UI.
    If the image is a PIL Image object, Graphbook will attempt to store it in a shared memory region if the feature is enabled.
    If shared memory is disabled, PIL Image objects will not be rendered in the UI.

    Args:
        path_or_pil (Union[str, Image.Image]): A path to an image file or a PIL Image object.
    """
    assert isinstance(path_or_pil, str) or isinstance(path_or_pil, Image.Image)
    return {"type": "image", "value": path_or_pil}


class ExecutionContext:
    _storage = threading.local()

    @classmethod
    def get_context(cls) -> Dict[str, Any]:
        if not hasattr(cls._storage, "context"):
            cls._storage.context = {}
        return cls._storage.context

    @classmethod
    def update(cls, **kwargs):
        context = cls.get_context()
        context.update(kwargs)

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        return cls.get_context().get(key, default)


class TaskLoop:
    def __init__(
        self,
        interval_seconds: float = MP_WORKER_TIMEOUT,
        close_event: Optional[asyncio.Event] = None,
    ):
        self._stop_event = close_event or asyncio.Event()
        self._interval = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @abstractmethod
    async def loop(self) -> None:
        """Override this method with the work to be done periodically"""
        pass

    async def _run(self):
        while not self._stop_event.is_set():
            try:
                await self.loop()
            except Exception as e:
                traceback.print_exc()
            try:
                await asyncio.sleep(self._interval)
            except Exception as e:
                traceback.print_exc()

    def start(self):
        """Start the worker in the current event loop"""
        try:
            self._loop = asyncio.get_event_loop()
            self._task = self._loop.create_task(self._run())
        except:
            traceback.print_exc()

    async def stop(self):
        """Stop the worker"""
        if self._task:
            self._stop_event.set()
            await self._task


class QueueTaskLoop(TaskLoop):
    def __init__(
        self,
        queue: queue.Queue,
        interval_seconds: float = MP_WORKER_TIMEOUT,
        close_event: Optional[asyncio.Event] = None,
    ):
        super().__init__(interval_seconds, close_event)
        self.queue = queue
        self.executor = ThreadPoolExecutor(max_workers=4)

    @abstractmethod
    def loop(self, work: dict) -> None:
        """Override this method with the work to be done periodically"""
        raise NotImplementedError

    async def _run(self):
        while not self._stop_event.is_set():
            try:
                work = self.queue.get_nowait()
                self.loop(work)
            except queue.Empty:
                await asyncio.sleep(self._interval)
            except asyncio.exceptions.CancelledError:
                self._stop_event.set()
                return
            except RuntimeError:
                self._stop_event.set()
                return
            except Exception as e:
                if RAY_AVAILABLE and isinstance(e, RAY_UTIL_QUEUE.Empty):
                    await asyncio.sleep(self._interval)
                else:
                    traceback.print_exc()
                    raise Exception(f"MultiGraphViewManager Error: {e}")


try:
    import ray
    import ray.util.queue

    RAY_AVAILABLE = True
    RAY = ray
    RAY_UTIL_QUEUE = ray.util.queue
except ImportError:
    RAY_AVAILABLE = False
    RAY = None
    RAY_UTIL_QUEUE = None
