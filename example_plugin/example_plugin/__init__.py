from .nodes import SimpleStep
from .nodes import SimpleResource
import os.path as osp
from graphbook.plugins import export, web


export("SimpleStep", SimpleStep)
export("SimpleResource", SimpleResource)
    
web(osp.realpath(osp.join(osp.dirname(__file__), "../web/dist/bundle.js")))
