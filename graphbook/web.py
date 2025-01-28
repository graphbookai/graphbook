import os
import re
import signal
import multiprocessing as mp
import asyncio
import base64
import hashlib
import aiohttp
from typing import Optional
from aiohttp import web
from pathlib import Path
from .media import create_media_server
from .shm import MultiThreadedMemoryManager, RayMemoryManager
from .clients import ClientPool, Client, WebClient
from .plugins import setup_plugins
import json
import threading
import time
import atexit


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = web.Response(status=ex.status, text=ex.text)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, DELETE, PUT, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, sid"
    )
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


class GraphServer:
    def __init__(
        self,
        web_processor_args: dict,
        isolate_users: bool,
        no_sample: bool,
        close_event: mp.Event,
        setup_paths: Optional[dict] = None,
        web_dir: Optional[str] = None,
        host: str = "0.0.0.0",
        port: int = 8005,
        proc_queue: Optional[mp.Queue] = None,
        view_queue: Optional[mp.Queue] = None,
    ):
        self.host = host
        self.port = port
        self.close_event = close_event
        self.web_dir = web_dir
        if self.web_dir is None:
            self.web_dir = Path(__file__).parent.joinpath("web")
        else:
            self.web_dir = Path(self.web_dir)
        routes = web.RouteTableDef()
        self.routes = routes
        middlewares = [cors_middleware]
        max_upload_size = 100  # MB
        max_upload_size = round(max_upload_size * 1024 * 1024)
        self.app = web.Application(
            client_max_size=max_upload_size, middlewares=middlewares
        )
        self.plugins = setup_plugins()
        self.plugin_steps, self.plugin_resources, self.web_plugins = self.plugins
        node_plugins = (self.plugin_steps, self.plugin_resources)
        self.is_editor_enabled = setup_paths is not None
        self.img_mem = (
            MultiThreadedMemoryManager if self.is_editor_enabled else RayMemoryManager
        )
        self.client_pool = ClientPool(
            web_processor_args,
            node_plugins,
            isolate_users,
            no_sample,
            close_event,
            setup_paths=setup_paths,
            proc_queue=proc_queue,
            view_queue=view_queue,
        )

        if not self.web_dir.is_dir():
            print(
                f"Couldn't find web files inside {self.web_dir}. Will not serve web files."
            )
            self.web_dir = None

        def get_client(request: web.Request) -> Client:
            sid = request.headers.get("sid")
            if sid is None:
                raise web.HTTPUnauthorized()
            client = self.client_pool.get(sid)
            if client is None:
                raise web.HTTPUnauthorized()
            return client

        @routes.get("/ws")
        async def websocket_handler(request: web.Request, *_) -> web.WebSocketResponse:
            if self.close_event.is_set():
                print("Server is shutting down. Rejecting new client.")
                raise web.HTTPServiceUnavailable()

            ws = web.WebSocketResponse()
            try:
                await ws.prepare(request)
            except Exception as e:
                print(f"Error preparing websocket: {e}")
                return ws
            client = await self.client_pool.add_client(ws)

            def put_graph(req: dict):
                filename = req["filename"]
                nodes = req["nodes"]
                edges = req["edges"]
                full_path = client.get_root_path().joinpath(filename)
                with open(full_path, "w") as f:
                    serialized = {
                        "version": "0",
                        "type": "workflow",
                        "nodes": nodes,
                        "edges": edges,
                    }
                    json.dump(serialized, f)

            try:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        if msg.data == "close":
                            await self.client_pool.remove_client(client)
                        else:
                            req = msg.json()
                            if req["api"] == "graph" and req["cmd"] == "put_graph":
                                put_graph(req)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print("ws connection closed with exception %s" % ws.exception())
            finally:
                await self.client_pool.remove_client(client)

            return ws

        @routes.get("/")
        async def get(request: web.Request) -> web.Response:
            if self.web_dir is None:
                raise web.HTTPNotFound()
            return web.FileResponse(self.web_dir.joinpath("index.html"))

        @routes.get("/media")
        async def get_media(request: web.Request) -> web.Response:
            path = request.query.get("path", None)
            shm_id = request.query.get("shm_id", None)

            if path is not None:
                path = Path(path)
                if not path.exists():
                    raise web.HTTPNotFound()
                with open(path, "rb") as f:
                    data = f.read()
                return web.Response(body=data, content_type="image/png")

            if shm_id is not None:
                img = self.img_mem.get_image(shm_id)
                if img is None:
                    raise web.HTTPNotFound()
                return web.Response(body=img, content_type="image/png")

        @routes.post("/param_run/{id}")
        async def param_run(request: web.Request) -> web.Response:
            client: Client = get_client(request)
            graph_id = request.match_info.get("id")
            data = await request.json()
            params = data.get("params", {})
            proc_queue = client.get_processor().get_queue()
            proc_queue.put(
                {"cmd": "set_params", "graph_id": graph_id, "params": params}
            )
            return web.json_response({"success": True})

        @routes.get("/state/{step_id}/{pin_id}/{index}")
        async def get_output_note(request: web.Request) -> web.Response:
            client = get_client(request)
            step_id = request.match_info.get("step_id")
            pin_id = request.match_info.get("pin_id")
            index = int(request.match_info.get("index"))
            res = client.get_processor().get_output_note(step_id, pin_id, index)
            if (
                res
                and res.get("step_id") == step_id
                and res.get("pin_id") == pin_id
                and res.get("index") == index
            ):
                return web.json_response(res)

            return web.json_response({"error": "Could not get output note."})

        @routes.post("/prompt_response/{id}")
        async def prompt_response(request: web.Request) -> web.Response:
            client = get_client(request)
            step_id = request.match_info.get("id")
            data = await request.json()
            response = data.get("response")
            res = client.get_processor().handle_prompt_response(step_id, response)
            return web.json_response({"ok": res})

        if self.is_editor_enabled:

            @routes.post("/run")
            async def run_all(request: web.Request) -> web.Response:
                client: WebClient = get_client(request)
                data = await request.json()
                graph = data.get("graph", {})
                resources = data.get("resources", {})
                filename = data.get("filename", "")
                client.exec(
                    {
                        "cmd": "run_all",
                        "graph": graph,
                        "resources": resources,
                        "filename": filename,
                    },
                )
                return web.json_response({"success": True})

            @routes.get("/step_docstring/{name}")
            async def get_step_docstring(request: web.Request):
                client: WebClient = get_client(request)
                name = request.match_info.get("name")
                docstring = client.get_node_hub().get_step_docstring(name)
                return web.json_response({"content": docstring})

            @routes.get("/resource_docstring/{name}")
            async def get_resource_docstring(request: web.Request):
                client: WebClient = get_client(request)
                name = request.match_info.get("name")
                docstring = client.get_node_hub().get_resource_docstring(name)
                return web.json_response({"content": docstring})

            @routes.post("/run/{id}")
            async def run(request: web.Request) -> web.Response:
                client = get_client(request)
                step_id = request.match_info.get("id")
                data = await request.json()
                graph = data.get("graph", {})
                resources = data.get("resources", {})
                filename = data.get("filename", "")
                client.exec(
                    {
                        "cmd": "run",
                        "graph": graph,
                        "resources": resources,
                        "step_id": step_id,
                        "filename": filename,
                    },
                )
                return web.json_response({"success": True})

            @routes.post("/step/{id}")
            async def step(request: web.Request) -> web.Response:
                client = get_client(request)
                step_id = request.match_info.get("id")
                data = await request.json()
                graph = data.get("graph", {})
                resources = data.get("resources", {})
                filename = data.get("filename", "")
                client.exec(
                    {
                        "cmd": "step",
                        "graph": graph,
                        "resources": resources,
                        "step_id": step_id,
                        "filename": filename,
                    },
                )
                return web.json_response({"success": True})

            @routes.post("/pause")
            async def pause(request: web.Request) -> web.Response:
                client = get_client(request)
                client.get_processor().pause()
                return web.json_response({"success": True})

            @routes.post("/clear")
            @routes.post("/clear/{id}")
            async def clear(request: web.Request) -> web.Response:
                client: WebClient = get_client(request)
                node_id = request.match_info.get("id")
                client.exec({"cmd": "clear", "node_id": node_id})
                return web.json_response({"success": True})

            @routes.get("/nodes")
            async def get_nodes(request: web.Request) -> web.Response:
                client = get_client(request)
                nodes = client.nodes()
                return web.json_response(nodes)

            @routes.get(r"/docs/{path:.+}")
            async def get_docs(request: web.Request) -> web.Response:
                client = get_client(request)
                path = request.match_info.get("path", "")
                docs_path = client.get_docs_path()
                if docs_path is None:
                    raise web.HTTPNotFound()

                fullpath = docs_path.joinpath(path)
                if fullpath.exists():
                    with open(fullpath, "r") as f:
                        file_contents = f.read()
                        d = {"content": file_contents}
                        return web.json_response(d)
                else:
                    return web.json_response(
                        {"reason": "/%s: No such file or directory." % fullpath},
                        status=404,
                    )

            @routes.get("/fs")
            @routes.get(r"/fs/{path:.+}")
            async def get(request: web.Request) -> web.Response:
                client = get_client(request)
                path = request.match_info.get("path", "")
                client_path = client.get_root_path()
                if client_path is None:
                    raise web.HTTPNotFound()

                fullpath = client_path.joinpath(path)
                assert str(fullpath).startswith(
                    str(client_path)
                ), f"{fullpath} must be within {client_path}"

                def handle_fs_tree(p: Path, fn: callable) -> dict:
                    if Path.is_dir(p):
                        p_data = fn(p)
                        p_data["children"] = [
                            handle_fs_tree(f, fn) for f in Path.iterdir(p)
                        ]
                        return p_data
                    else:
                        return fn(p)

                def get_stat(path: Path) -> dict:
                    stat = path.stat()
                    rel_path = path.relative_to(fullpath)
                    st = {
                        "title": path.name,
                        "path": str(rel_path),
                        "path_from_cwd": str(fullpath.joinpath(rel_path)),
                        "dirname": str(Path(rel_path).parent),
                        "access_time": int(stat.st_atime),
                        "modification_time": int(stat.st_mtime),
                        "change_time": int(stat.st_ctime),
                    }

                    if not path.is_dir():
                        st["size"] = int(stat.st_size)

                    return st

                if fullpath.exists():
                    if request.query.get("stat", False):
                        stats = handle_fs_tree(fullpath, get_stat)
                        res = web.json_response(stats)
                        res.headers["Content-Type"] = "application/json; charset=utf-8"
                        return res

                    if fullpath.is_dir():
                        res = web.json_response(list(fullpath.iterdir()))
                        res.headers["Content-Type"] = "application/json; charset=utf-8"
                        return res
                    else:
                        r = request.headers.get("Range")
                        m = (
                            re.match(r"bytes=((\d+-\d+,)*(\d+-\d*))", r)
                            if r is not None
                            else None
                        )
                        if r is None or m is None:
                            with open(fullpath, "r") as f:
                                file_contents = f.read()
                                d = {"content": file_contents}
                                return web.json_response(d)
                else:
                    return web.json_response(
                        {"reason": "/%s: No such file or directory." % path}, status=404
                    )

            @routes.put("/fs")
            @routes.put(r"/fs/{path:.+}")
            async def put(request: web.Request) -> web.Response:
                client = get_client(request)
                path = request.match_info.get("path", "")
                client_path = client.get_root_path()
                if client_path is None:
                    raise web.HTTPNotFound()

                fullpath = client_path.joinpath(path)
                data = await request.json()
                if request.query.get("mv"):
                    topath = client_path.joinpath(request.query.get("mv"))
                    os.rename(fullpath, topath)
                    return web.json_response({}, status=200)

                is_file = data.get("is_file", False)
                file_contents = data.get("file_contents", "")
                hash_key = data.get("hash_key", "")

                if not is_file:
                    os.mkdir(fullpath)
                    return web.json_response({}, status=201)

                encoding = data.get("encoding", "")
                if encoding == "base64":
                    file_contents = base64.b64decode(file_contents)

                if fullpath.exists():
                    with open(fullpath, "r") as f:
                        current_hash = hashlib.md5(f.read().encode()).hexdigest()
                        if current_hash != hash_key:
                            print("Couldn't save file due to hash mismatch")
                            return web.json_response(
                                {"reason": "Hash mismatch."}, status=409
                            )

                with open(fullpath, "w") as f:
                    f.write(file_contents)
                    return web.json_response({}, status=201)

            @routes.delete("/fs/{path:.+}")
            async def delete(request: web.Request) -> web.Response:
                client: WebClient = get_client(request)
                path = request.match_info.get("path")
                client_path = client.get_root_path()
                if client_path is None:
                    raise web.HTTPNotFound()

                fullpath = client_path.joinpath(path)
                if fullpath.exists():
                    if fullpath.is_dir():
                        try:
                            fullpath.rmdir(fullpath)
                            return web.json_response({"success": True}, status=204)
                        except Exception as e:
                            return web.json_response(
                                {"reason": f"Error deleting directory {fullpath}: {e}"},
                                status=400,
                            )
                    else:
                        fullpath.unlink(True)
                        return web.json_response({"success": True}, status=204)
                else:
                    return web.json_response(
                        {"reason": f"No such file or directory {fullpath}."}, status=404
                    )

            @routes.get("/plugins")
            async def get_plugins(request: web.Request) -> web.Response:
                plugin_list = list(self.web_plugins.keys())
                return web.json_response(plugin_list)

            @routes.get("/plugins/{name}")
            async def get_plugin(request: web.Request) -> web.Response:
                plugin_name = request.match_info.get("name")
                plugin_location = self.web_plugins.get(plugin_name)
                if plugin_location is None:
                    raise web.HTTPNotFound(text=f"Plugin {plugin_name} not found.")
                return web.FileResponse(plugin_location)

    async def setup(self):
        self.app.router.add_routes(self.routes)
        if self.web_plugins:
            print("Loaded web plugins:")
            print(self.web_plugins)

        if self.web_dir is not None:
            self.app.router.add_routes([web.static("/", self.web_dir)])

        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        print(f"Started graph server at {self.host}:{self.port}")
        self.client_pool.start()
        

    def start(self):
        try:
            asyncio.run(self.setup())
        except KeyboardInterrupt:
            self.close_event.set()
            print("Exiting graph server")


def start_web(args):
    # The start method on some systems like Mac default to spawn
    if not args.spawn and mp.get_start_method() == "spawn":
        mp.set_start_method("fork", force=True)

    close_event = mp.Event()
    setup_paths = dict(
        workflow_dir=args.workflow_dir,
        custom_nodes_path=args.nodes_dir,
        docs_path=args.docs_dir,
    )

    web_processor_args = dict(
        continue_on_failure=args.continue_on_failure,
        copy_outputs=args.copy_outputs,
        spawn=args.spawn,
        num_workers=args.num_workers,
    )

    if args.start_media_server:
        p = mp.Process(target=create_media_server, args=(args,))
        p.daemon = True
        p.start()

    def cleanup():
        close_event.set()

    def signal_handler(*_):
        cleanup()
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    server = GraphServer(
        web_processor_args,
        args.isolate_users,
        args.no_sample,
        close_event,
        host=args.host,
        port=args.port,
        setup_paths=setup_paths,
    )
    server.start()


def async_start(host, port, proc_queue=None, view_queue=None):
    def _fn(close_event):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        server = GraphServer(
            {},
            isolate_users=False,
            no_sample=True,
            close_event=close_event,
            host=host,
            port=port,
            proc_queue=proc_queue,
            view_queue=view_queue,
        )



        try:
            loop.run_until_complete(server.setup())
            loop.run_forever()
        finally:
            pass
    
    close_event = mp.Event()  
    
    def shutdown():
        close_event.set()
        
    atexit.register(shutdown)
      

    thread = threading.Thread(
        target=_fn,
        args=(close_event,),
        daemon=True,
    )
    thread.start()
    
    def signal_handler(*_):
        close_event.set()
        time.sleep(.1)
        raise SystemExit()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

