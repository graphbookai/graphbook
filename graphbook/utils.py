from typing import Iterable
import importlib


MP_WORKER_TIMEOUT = 5.0

def is_batchable(obj: any) -> bool:
    return isinstance(obj, Iterable)

"""
This function is used to convert a string to a function
by interpreting the string as a python-typed function
definition. This is used to allow the user to define
custom functions in the graphbook UI.
"""
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
