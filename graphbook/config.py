import os.path as osp
import yaml

GLOBAL_CONFIG = {}

def setup(config_path: str) -> dict:
    global GLOBAL_CONFIG
    if not osp.exists(config_path):
        return
    with open(config_path, "r") as f:
        GLOBAL_CONFIG = yaml.safe_load(f)
    
def get(key: str, default=None) -> any:
    return GLOBAL_CONFIG.get(key, default)
