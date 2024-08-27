from .steps import SimpleStep
import os.path as osp
from graphbook.plugins import export, web


export("SimpleStep", SimpleStep)
    
web(osp.realpath(osp.join(osp.dirname(__file__), "../web")))
