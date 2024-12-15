import os
import os.path as osp
import re
import signal
import multiprocessing as mp
import asyncio
import base64
import hashlib
import aiohttp
from aiohttp import web
from .media import create_media_server
from .utils import ProcessorStateRequest
from .shm import SharedMemoryManager
from .clients import ClientPool
from .plugins import setup_plugins
import json


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
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


class GraphServer:
    def __init__(
        self,
        web_processor_args: dict,
        img_mem_args: dict,
        setup_paths: dict,
        isolate_users: bool,
        no_sample: bool,
        close_event: mp.Event,
        web_dir: str | None = None,
        host="0.0.0.0",
        port=8005,
    ):
        self.host = host
        self.port = port
        self.close_event = close_event
        self.web_dir = web_dir
        if self.web_dir is None:
            self.web_dir = osp.join(osp.dirname(__file__), "web")
        routes = web.RouteTableDef()
        self.routes = routes
        self.img_mem = SharedMemoryManager(**img_mem_args) if img_mem_args else None
        middlewares = [cors_middleware]
        max_upload_size = 100  # MB
        max_upload_size = round(max_upload_size * 1024 * 1024)
        self.app = web.Application(
            client_max_size=max_upload_size, middlewares=middlewares
        )
        self.plugins = setup_plugins()
        self.plugin_steps, self.plugin_resources, self.web_plugins = self.plugins
        node_plugins = (self.plugin_steps, self.plugin_resources)
        self.client_pool = ClientPool(
            web_processor_args,
            setup_paths,
            node_plugins,
            isolate_users,
            no_sample,
            close_event,
        )

        if not osp.isdir(self.web_dir):
            print(
                f"Couldn't find web files inside {self.web_dir}. Will not serve web files."
            )
            self.web_dir = None

        @routes.get("/ws")
        async def websocket_handler(request: web.Request, *_) -> web.WebSocketResponse:
            if self.close_event.is_set():
                raise web.HTTPServiceUnavailable()

            ws = web.WebSocketResponse()
            await ws.prepare(request)
            sid = self.client_pool.add_client(ws)

            def put_graph(req: dict):
                full_path = osp.join(self.client_pool.get_root_path(sid), filename)
                filename = req["filename"]
                nodes = req["nodes"]
                edges = req["edges"]
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
                            await ws.close()
                        else:
                            req = msg.json()  # Unhandled
                            if req["api"] == "graph" and req["cmd"] == "put_graph":
                                put_graph(req)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print("ws connection closed with exception %s" % ws.exception())
            finally:
                await self.client_pool.remove_client(sid)

            return ws

        @routes.get("/")
        async def get(request: web.Request) -> web.Response:
            if self.web_dir is None:
                raise web.HTTPNotFound(body="No web files found.")
            return web.FileResponse(osp.join(self.web_dir, "index.html"))

        @routes.get("/media")
        async def get_media(request: web.Request) -> web.Response:
            path = request.query.get("path", None)
            shm_id = request.query.get("shm_id", None)

            if path is not None:
                if not osp.exists(path):
                    raise web.HTTPNotFound()
                return web.FileResponse(path)

            if shm_id is not None:
                if self.img_mem is None:
                    raise web.HTTPNotFound()
                img = self.img_mem.get_image(shm_id)
                if img is None:
                    raise web.HTTPNotFound()
                return web.Response(body=img, content_type="image/png")

        @routes.post("/run")
        async def run_all(request: web.Request, sid) -> web.Response:
            data = await request.json()
            graph = data.get("graph", {})
            resources = data.get("resources", {})
            filename = data.get("filename", "")
            self.client_pool.exec(
                sid,
                {
                    "cmd": "run_all",
                    "graph": graph,
                    "resources": resources,
                    "filename": filename,
                },
            )
            return web.json_response({"success": True})

        @routes.post("/run/{id}")
        async def run(request: web.Request) -> web.Response:
            sid = request.headers.get("sid")
            step_id = request.match_info.get("id")
            data = await request.json()
            graph = data.get("graph", {})
            resources = data.get("resources", {})
            filename = data.get("filename", "")
            self.client_pool.exec(
                sid,
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
            sid = request.headers.get("sid")
            step_id = request.match_info.get("id")
            data = await request.json()
            graph = data.get("graph", {})
            resources = data.get("resources", {})
            filename = data.get("filename", "")
            self.client_pool.exec(
                sid,
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
            sid = request.headers.get("sid")
            self.client_pool.exec(sid, {"cmd": "pause"})
            return web.json_response({"success": True})

        @routes.post("/clear")
        @routes.post("/clear/{id}")
        async def clear(request: web.Request) -> web.Response:
            sid = request.headers.get("sid")
            node_id = request.match_info.get("id")
            self.client_pool.exec(sid, {"cmd": "clear", "node_id": node_id})
            return web.json_response({"success": True})

        @routes.post("/prompt_response/{id}")
        async def prompt_response(request: web.Request) -> web.Response:
            sid = request.headers.get("sid")
            step_id = request.match_info.get("id")
            data = await request.json()
            response = data.get("response")
            res = self.client_pool.poll(
                sid,
                ProcessorStateRequest.PROMPT_RESPONSE,
                {
                    "step_id": step_id,
                    "response": response,
                },
            )
            return web.json_response(res)

        @routes.get("/nodes")
        async def get_nodes(request: web.Request) -> web.Response:
            sid = request.headers.get("sid")
            nodes = self.client_pool.nodes(sid)
            return web.json_response(nodes)

        @routes.get("/state/{step_id}/{pin_id}/{index}")
        async def get_output_note(request: web.Request) -> web.Response:
            sid = request.headers.get("sid")
            step_id = request.match_info.get("step_id")
            pin_id = request.match_info.get("pin_id")
            index = int(request.match_info.get("index"))
            res = self.client_pool.poll(
                sid,
                ProcessorStateRequest.GET_OUTPUT_NOTE,
                {
                    "step_id": step_id,
                    "pin_id": pin_id,
                    "index": index,
                },
            )
            if (
                res
                and res.get("step_id") == step_id
                and res.get("pin_id") == pin_id
                and res.get("index") == index
            ):
                return web.json_response(res)

            return web.json_response({"error": "Could not get output note."})

        @routes.get("/state")
        async def get_run_state(request: web.Request) -> web.Response:
            sid = request.headers.get("sid")
            res = self.client_pool.poll(sid, ProcessorStateRequest.GET_RUNNING_STATE)
            return web.json_response(res)

        @routes.get("/step_docstring/{name}")
        async def get_step_docstring(request: web.Request):
            sid = request.headers.get("sid")
            name = request.match_info.get("name")
            docstring = self.client_pool.step_doc(sid, name)
            return web.json_response({"content": docstring})

        @routes.get("/resource_docstring/{name}")
        async def get_resource_docstring(request: web.Request):
            sid = request.headers.get("sid")
            name = request.match_info.get("name")
            docstring = self.client_pool.resource_doc(sid, name)
            return web.json_response({"content": docstring})

        @routes.get(r"/docs/{path:.+}")
        async def get_docs(request: web.Request) -> web.Response:
            sid = request.headers.get("sid")
            path = request.match_info.get("path")
            docs_path = self.client_pool.get_docs_path(sid)
            fullpath = osp.join(docs_path, path)

            if osp.exists(fullpath):
                with open(fullpath, "r") as f:
                    file_contents = f.read()
                    d = {"content": file_contents}
                    return web.json_response(d)
            else:
                return web.json_response(
                    {"reason": "/%s: No such file or directory." % fullpath}, status=404
                )

        @routes.get("/fs")
        @routes.get(r"/fs/{path:.+}")
        async def get(request: web.Request) -> web.Response:
            sid = request.headers.get("sid")
            print(sid)
            path = request.match_info.get("path", "")
            client_path = self.client_pool.get_root_path(sid)
            print(client_path)
            fullpath = osp.join(client_path, path)  # client_path
            assert fullpath.startswith(
                client_path
            ), f"{fullpath} must be within {client_path}"

            def handle_fs_tree(p: str, fn: callable) -> dict:
                if osp.isdir(p):
                    p_data = fn(p)
                    p_data["children"] = [
                        handle_fs_tree(osp.join(p, f), fn) for f in os.listdir(p)
                    ]
                    return p_data
                else:
                    return fn(p)

            def get_stat(path):
                stat = os.stat(path)
                rel_path = osp.relpath(path, abs_root_path)
                st = {
                    "title": osp.basename(rel_path),
                    "path": rel_path,
                    "path_from_cwd": osp.join(root_path, rel_path),
                    "dirname": osp.dirname(rel_path),
                    "from_root": osp.basename(abs_root_path),
                    "access_time": int(stat.st_atime),
                    "modification_time": int(stat.st_mtime),
                    "change_time": int(stat.st_ctime),
                }

                if not osp.isdir(path):
                    st["size"] = int(stat.st_size)

                return st

            if osp.exists(fullpath):
                if request.query.get("stat", False):
                    stats = handle_fs_tree(fullpath, get_stat)
                    res = web.json_response(stats)
                    res.headers["Content-Type"] = "application/json; charset=utf-8"
                    return res

                if osp.isdir(fullpath):
                    res = web.json_response(os.listdir(fullpath))
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
            sid = request.headers.get("sid")
            path = request.match_info.get("path")
            client_path = self.client_pool.get_root_path(sid)
            fullpath = osp.join(client_path, path)
            data = await request.json()
            if request.query.get("mv"):
                topath = osp.join(client_path, request.query.get("mv"))
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

            if osp.exists(fullpath):
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
            sid = request.headers.get("sid")
            path = request.match_info.get("path")
            client_path = self.client_pool.get_root_path(sid)
            fullpath = osp.join(client_path, path)
            assert fullpath.startswith(
                client_path
            ), f"{fullpath} must be within {client_path}"

            if osp.exists(fullpath):
                if osp.isdir(fullpath):
                    if os.listdir(fullpath) == []:
                        os.rmdir(fullpath)
                        return web.json_response({"success": True}, status=204)
                    else:
                        return web.json_response(
                            {"reason": "/%s: Directory is not empty." % path},
                            status=403,
                        )
                else:
                    os.remove(fullpath)
                    return web.json_response({"success": True}, status=204)
            else:
                return web.json_response(
                    {"reason": "/%s: No such file or directory." % path}, status=404
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
                raise web.HTTPNotFound(body=f"Plugin {plugin_name} not found.")
            return web.FileResponse(plugin_location)

    async def _async_start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        await asyncio.Event().wait()

    async def on_shutdown(self):
        self.client_pool.close_all()

    def start(self):
        self.app.router.add_routes(self.routes)
        if self.web_plugins:
            print("Loaded web plugins:")
            print(self.web_plugins)

        if self.web_dir is not None:
            self.app.router.add_routes([web.static("/", self.web_dir)])

        self.app.on_shutdown.append(self.on_shutdown)

        print(f"Starting graph server at {self.host}:{self.port}")
        try:
            asyncio.run(self._async_start())
        except KeyboardInterrupt:
            print("Exiting graph server")


def create_graph_server(
    args,
    web_processor_args,
    img_mem_args,
    setup_paths,
    close_event,
    web_dir,
):
    server = GraphServer(
        web_processor_args,
        img_mem_args,
        setup_paths,
        args.isolate_users,
        args.no_sample,
        close_event,
        web_dir=web_dir,
        host=args.host,
        port=args.port,
    )
    server.start()


def start_web(args):
    # The start method on some systems like Mac default to spawn
    if not args.spawn and mp.get_start_method() == "spawn":
        mp.set_start_method("fork", force=True)

    img_mem = (
        SharedMemoryManager(size=args.img_shm_size) if args.img_shm_size > 0 else None
    )
    close_event = mp.Event()
    setup_paths = dict(
        workflow_dir=args.workflow_dir,
        custom_nodes_path=args.nodes_dir,
        docs_path=args.docs_dir,
    )

    web_processor_args = dict(
        img_mem=img_mem,
        continue_on_failure=args.continue_on_failure,
        copy_outputs=args.copy_outputs,
        close_event=close_event,
        spawn=args.spawn,
        num_workers=args.num_workers,
    )

    if args.start_media_server:
        p = mp.Process(target=create_media_server, args=(args,))
        p.daemon = True
        p.start()

    def cleanup():
        close_event.set()

        if img_mem:
            try:
                img_mem.close()
            except FileNotFoundError:
                pass

    def signal_handler(*_):
        cleanup()
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    create_graph_server(
        args,
        web_processor_args,
        img_mem.get_shared_args() if img_mem else {},
        setup_paths,
        close_event,
        args.web_dir,
    )
