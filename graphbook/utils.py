MP_WORKER_TIMEOUT = 5.0
from typing import Iterable

def is_batchable(obj: any) -> bool:
    return isinstance(obj, Iterable)
