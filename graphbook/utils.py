from __future__ import annotations
from enum import Enum
from typing import Iterable
import importlib
import shutil
import subprocess
import os
import platform
import multiprocessing.connection as mpc


MP_WORKER_TIMEOUT = 5.0
ProcessorStateRequest = Enum(
    "ProcessorStateRequest",
    ["GET_OUTPUT_NOTE", "GET_WORKER_QUEUE_SIZES", "GET_RUNNING_STATE"],
)


def is_batchable(obj: any) -> bool:
    return isinstance(obj, Iterable)


def transform_function_string(func_str):
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


def poll_conn_for(
    conn: mpc.Connection, req: ProcessorStateRequest, body: dict = None
) -> dict:
    req_data = {"cmd": req}
    if body:
        req_data.update(body)
    conn.send(req_data)
    if conn.poll(timeout=MP_WORKER_TIMEOUT):
        res = conn.recv()
        if res.get("res") == req:
            return res.get("data")
    return None


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
