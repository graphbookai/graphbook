import os
import re
import signal
import multiprocessing as mp
import asyncio
import json
import aiohttp
from aiohttp import web
from pathlib import Path
from typing import Optional

from graphbook.core.media import create_media_server
from graphbook.core.shm import MultiThreadedMemoryManager
from graphbook.core.clients import ClientPool, Client
from graphbook.core.web import Server, cors_middleware
from graphbook.core.serialization import deserialize_json_to_graph
from graphbook.ray.ray_executor import RayExecutor
from graphbook.ray.ray_img import RayMemoryManager
from graphbook.ray.ray_client import RayClientPool


class RayGraphServer(Server):
    """
    Server that processes graph execution requests using Ray.
    
    This server deserializes JSON workflows into Graph objects and executes them
    using the RayExecutor on a Ray cluster.
    """
    
    def __init__(
        self,
        close_event: mp.Event,
        ray_init_args: dict = None,
        web_dir: Optional[str] = None,
        log_dir: str = "logs",
        host: str = "0.0.0.0",
        port: int = 8005,
    ):
        # Initialize Ray executor with provided init args
        if ray_init_args is None:
            ray_init_args = {}
            
        self.ray_executor = RayExecutor(
            enable_logging=True,
            log_dir=log_dir,
            **ray_init_args
        )
        
        client_pool = self.ray_executor.get_client_pool()
        img_storage = self.ray_executor.get_img_storage()
        
        super().__init__(
            close_event,
            client_pool,
            img_storage,
            web_dir,
            host,
            port,
        )
        
        # Set up log directory reader to monitor logs
        from graphbook.logging.dag import LogDirectoryReader
        self.log_dir = Path(log_dir)
        self.log_reader = LogDirectoryReader(
            log_dir=log_dir,
            queue=img_storage.view_queue,
            poll_interval=0.5,
            close_event=close_event
        )
        self.log_reader.start()
        
        @self.routes.get("/logs")
        async def get_logs(request: web.Request) -> web.Response:
            """
            Get a list of all log files in the log directory
            """
            logs = []
            if self.log_dir.exists():
                for file in self.log_dir.iterdir():
                    if file.suffix == ".log":
                        logs.append(file.name)
            return web.json_response({"logs": logs})
        
        @self.routes.post("/run_workflow")
        async def run_workflow(request: web.Request) -> web.Response:
            """
            Endpoint to run a complete workflow described in JSON format.
            
            The JSON data must contain 'nodes' and 'edges' keys.
            """
            try:
                data = await request.json()
                workflow_json = data.get("workflow", {})
                workflow_name = data.get("name", "unnamed_workflow")
                enable_logging = data.get("enable_logging", True)
                
                # Deserialize JSON to Graph object
                graph = deserialize_json_to_graph(workflow_json)
                
                # Configure logging
                if enable_logging:
                    # Generate a unique log filename
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    log_filename = f"{workflow_name}-{timestamp}.log"
                    
                    # Update RayExecutor to enable logging
                    self.ray_executor.enable_logging = True
                    self.ray_executor.log_filename = log_filename
                else:
                    self.ray_executor.enable_logging = False
                
                # Execute the graph with Ray
                self.ray_executor.run(graph, workflow_name)
                
                # Get the log filename if logging is enabled
                log_info = {}
                if enable_logging:
                    log_info["log_filename"] = self.ray_executor.get_log_filename()
                
                return web.json_response({
                    "success": True, 
                    "message": f"Workflow '{workflow_name}' started",
                    **log_info
                })
            except ValueError as e:
                return web.json_response({"success": False, "error": str(e)}, status=400)
            except Exception as e:
                return web.json_response(
                    {"success": False, "error": f"Error processing workflow: {str(e)}"},
                    status=500
                )
                
        @self.routes.post("/run_workflow_step/{step_id}")
        async def run_workflow_step(request: web.Request) -> web.Response:
            """
            Endpoint to run a specific step in a workflow described in JSON format.
            
            The JSON data must contain 'nodes' and 'edges' keys.
            The step_id parameter specifies which step to run.
            """
            try:
                step_id = request.match_info.get("step_id")
                data = await request.json()
                workflow_json = data.get("workflow", {})
                workflow_name = data.get("name", "unnamed_workflow")
                enable_logging = data.get("enable_logging", True)
                
                # Deserialize JSON to Graph object
                graph = deserialize_json_to_graph(workflow_json)
                
                # Configure logging
                if enable_logging:
                    # Generate a unique log filename
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    log_filename = f"{workflow_name}-step-{step_id}-{timestamp}.log"
                    
                    # Update RayExecutor to enable logging
                    self.ray_executor.enable_logging = True
                    self.ray_executor.log_filename = log_filename
                else:
                    self.ray_executor.enable_logging = False
                
                # Execute the specific step with Ray
                self.ray_executor.run(graph, workflow_name, step_id)
                
                # Get the log filename if logging is enabled
                log_info = {}
                if enable_logging:
                    log_info["log_filename"] = self.ray_executor.get_log_filename()
                
                return web.json_response({
                    "success": True, 
                    "message": f"Step '{step_id}' in workflow '{workflow_name}' started",
                    **log_info
                })
            except ValueError as e:
                return web.json_response({"success": False, "error": str(e)}, status=400)
            except Exception as e:
                return web.json_response(
                    {"success": False, "error": f"Error processing workflow step: {str(e)}"},
                    status=500
                )


def start_ray_server(
    ray_init_args: dict = None,
    web_dir: Optional[str] = None,
    log_dir: str = "logs",
    host: str = "0.0.0.0",
    port: int = 8005,
):
    """
    Start a Ray Graph Server.
    
    Args:
        ray_init_args (dict): Arguments to pass to ray.init()
        web_dir (Optional[str]): Directory containing web UI files
        log_dir (str): Directory to write log files to
        host (str): Host address to bind to
        port (int): Port to listen on
    """
    close_event = mp.Event()
    
    server = RayGraphServer(
        close_event=close_event,
        ray_init_args=ray_init_args,
        web_dir=web_dir,
        log_dir=log_dir,
        host=host,
        port=port,
    )
    
    def cleanup(*_):
        close_event.set()
        raise KeyboardInterrupt()
    
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    
    try:
        asyncio.run(server.start(block=True))
    except KeyboardInterrupt:
        close_event.set()


def async_start_ray_server(
    host: str = "localhost",
    port: int = 8005,
    ray_init_args: dict = None,
    web_dir: Optional[str] = None,
    log_dir: str = "logs",
):
    """
    Start a Ray Graph Server in a separate thread.
    
    Args:
        host (str): Host address to bind to
        port (int): Port to listen on
        ray_init_args (dict): Arguments to pass to ray.init()
        web_dir (Optional[str]): Directory containing web UI files
        log_dir (str): Directory to write log files to
    
    Returns:
        mp.Event: Event that can be set to shutdown the server
    """
    close_event = mp.Event()
    
    def _fn():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        server = RayGraphServer(
            close_event=close_event,
            ray_init_args=ray_init_args,
            web_dir=web_dir,
            log_dir=log_dir,
            host=host,
            port=port,
        )
        
        try:
            loop.run_until_complete(server.start())
            loop.run_forever()
        finally:
            pass
    
    import threading
    import atexit
    
    def shutdown():
        close_event.set()
    
    atexit.register(shutdown)
    
    thread = threading.Thread(
        target=_fn,
        args=(),
        daemon=True,
    )
    thread.start()
    
    def signal_handler(*_):
        close_event.set()
        import time
        time.sleep(0.1)
        raise SystemExit()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    return close_event