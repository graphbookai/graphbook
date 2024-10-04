import os
import os.path as osp
import re
import signal
import multiprocessing as mp
import multiprocessing.connection as mpc
import asyncio
import base64
import hashlib
import aiohttp
import traceback
from aiohttp import web
from graphbook.processing.web_processor import WebInstanceProcessor
from graphbook.viewer import ViewManager
from graphbook.exports import NodeHub
from graphbook.state import UIState
from graphbook.media import create_media_server
from graphbook.utils import poll_conn_for, ProcessorStateRequest
from graphbook.shm import SharedMemoryManager


try:
    import magic
except ImportError:
    magic = None
    print(
        "Warn: Optional libmagic library not found. Filesystem will not be able to determine MIME types."
    )


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
        processor_queue: mp.Queue,
        state_conn: mpc.Connection,
        processor_pause_event: mp.Event,
        view_manager_queue: mp.Queue,
        img_mem_args: dict,
        close_event: mp.Event,
        root_path: str,
        custom_nodes_path: str,
        docs_path: str,
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
        self.node_hub = NodeHub(custom_nodes_path)
        self.ui_state = None
        routes = web.RouteTableDef()
        self.routes = routes
        self.view_manager = ViewManager(view_manager_queue, close_event, state_conn)
        self.img_mem = SharedMemoryManager(**img_mem_args) if img_mem_args else None
        abs_root_path = osp.abspath(root_path)
        middlewares = [cors_middleware]
        max_upload_size = 100  # MB
        max_upload_size = round(max_upload_size * 1024 * 1024)
        self.app = web.Application(
            client_max_size=max_upload_size, middlewares=middlewares
        )

        if not osp.isdir(self.web_dir):
            print(
                f"Couldn't find web files inside {self.web_dir}. Will not serve web files."
            )
            self.web_dir = None

        @routes.get("/ws")
        async def websocket_handler(request):
            if self.close_event.is_set():
                raise web.HTTPServiceUnavailable()
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            self.ui_state = UIState(root_path, ws)

            self.node_hub.set_websocket(ws)  # Set the WebSocket in NodeHub

            sid = self.view_manager.add_client(ws)
            try:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        if msg.data == "close":
                            await ws.close()
                        else:
                            req = msg.json()  # Unhandled
                            if req["api"] == "graph":
                                self.ui_state.cmd(req)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print("ws connection closed with exception %s" % ws.exception())
            finally:
                await self.view_manager.remove_client(sid)

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
        async def run_all(request: web.Request) -> web.Response:
            data = await request.json()
            graph = data.get("graph", {})
            resources = data.get("resources", {})
            filename = data.get("filename", "")
            processor_queue.put(
                {
                    "cmd": "run_all",
                    "graph": graph,
                    "resources": resources,
                    "filename": filename,
                }
            )
            return web.json_response({"success": True})

        @routes.post("/run/{id}")
        async def run(request: web.Request) -> web.Response:
            step_id = request.match_info.get("id")
            data = await request.json()
            graph = data.get("graph", {})
            resources = data.get("resources", {})
            filename = data.get("filename", "")
            processor_queue.put(
                {
                    "cmd": "run",
                    "graph": graph,
                    "resources": resources,
                    "step_id": step_id,
                    "filename": filename,
                }
            )
            return web.json_response({"success": True})

        @routes.post("/step/{id}")
        async def step(request: web.Request) -> web.Response:
            step_id = request.match_info.get("id")
            data = await request.json()
            graph = data.get("graph", {})
            resources = data.get("resources", {})
            filename = data.get("filename", "")
            processor_queue.put(
                {
                    "cmd": "step",
                    "graph": graph,
                    "resources": resources,
                    "step_id": step_id,
                    "filename": filename,
                }
            )
            return web.json_response({"success": True})

        @routes.post("/pause")
        async def pause(request: web.Request) -> web.Response:
            processor_pause_event.set()
            return web.json_response({"success": True})

        @routes.post("/clear")
        @routes.post("/clear/{id}")
        async def clear(request: web.Request) -> web.Response:
            node_id = request.match_info.get("id")
            processor_queue.put(
                {
                    "cmd": "clear",
                    "node_id": node_id,
                }
            )
            return web.json_response({"success": True})
        
        @routes.post("/prompt_response/{id}")
        async def prompt_response(request: web.Request) -> web.Response:
            step_id = request.match_info.get("id")
            data = await request.json()
            response = data.get("response")
            res = poll_conn_for(state_conn, ProcessorStateRequest.PROMPT_RESPONSE, {"step_id": step_id, "response": response})
            return web.json_response(res)

        @routes.get("/nodes")
        async def get_nodes(request: web.Request) -> web.Response:
            return web.json_response(self.node_hub.get_exported_nodes())

        @routes.get("/state/{step_id}/{pin_id}/{index}")
        async def get_output_note(request: web.Request) -> web.Response:
            step_id = request.match_info.get("step_id")
            pin_id = request.match_info.get("pin_id")
            index = int(request.match_info.get("index"))
            res = poll_conn_for(
                state_conn,
                ProcessorStateRequest.GET_OUTPUT_NOTE,
                {"step_id": step_id, "pin_id": pin_id, "index": index},
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
            res = poll_conn_for(state_conn, ProcessorStateRequest.GET_RUNNING_STATE)
            return web.json_response(res)

        @routes.get(r"/docs/{path:.+}")
        async def get_docs(request: web.Request):
            path = request.match_info.get("path")
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

        @routes.get("/step_docstring/{name}")
        async def get_step_docstring(request: web.Request):
            name = request.match_info.get("name")
            docstring = self.node_hub.get_step_docstring(name)
            return web.json_response({"content": docstring})

        @routes.get("/resource_docstring/{name}")
        async def get_resource_docstring(request: web.Request):
            name = request.match_info.get("name")
            docstring = self.node_hub.get_resource_docstring(name)
            return web.json_response({"content": docstring})

        @routes.get("/fs")
        @routes.get(r"/fs/{path:.+}")
        async def get(request: web.Request):
            path = request.match_info.get("path", "")
            fullpath = osp.join(abs_root_path, path)
            assert fullpath.startswith(
                abs_root_path
            ), f"{fullpath} must be within {abs_root_path}"

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
                    if magic is not None:
                        mime = magic.from_file(path, mime=True)
                        if mime is None:
                            mime = "application/octet-stream"
                        else:
                            mime = mime.replace(" [ [", "")
                        st["mime"] = mime
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
        async def put(request: web.Request):
            path = request.match_info.get("path")
            fullpath = osp.join(root_path, path)
            data = await request.json()
            if request.query.get("mv"):
                topath = osp.join(root_path, request.query.get("mv"))
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
                    print(current_hash, hash_key)
                    if current_hash != hash_key:
                        return web.json_response(
                            {"reason": "Hash mismatch."}, status=409
                        )

            with open(fullpath, "w") as f:
                f.write(file_contents)
                return web.json_response({}, status=201)

        @routes.delete("/fs/{path:.+}")
        async def delete(request):
            path = request.match_info.get("path")
            fullpath = osp.join(root_path, path)
            assert fullpath.startswith(
                root_path
            ), f"{fullpath} must be within {root_path}"

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
        async def get_plugins(request):
            plugin_list = list(self.node_hub.get_web_plugins().keys())
            return web.json_response(plugin_list)

        @routes.get("/plugins/{name}")
        async def get_plugin(request):
            plugin_name = request.match_info.get("name")
            plugin_location = self.node_hub.get_web_plugins().get(plugin_name)
            if plugin_location is None:
                raise web.HTTPNotFound(body=f"Plugin {plugin_name} not found.")
            return web.FileResponse(plugin_location)

    async def _async_start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self.view_manager.start)
        await asyncio.Event().wait()

    def start(self):
        self.app.router.add_routes(self.routes)

        web_plugins = self.node_hub.get_web_plugins()
        if web_plugins:
            print("Loaded web plugins:")
            print(web_plugins)

        if self.web_dir is not None:
            self.app.router.add_routes([web.static("/", self.web_dir)])

        print(f"Starting graph server at {self.host}:{self.port}")
        self.node_hub.start()
        try:
            asyncio.run(self._async_start())
        except KeyboardInterrupt:
            self.node_hub.stop()
            print("Exiting graph server")


def create_graph_server(
    args,
    cmd_queue,
    state_conn,
    processor_pause_event,
    view_manager_queue,
    close_event,
    img_mem_args,
    root_path,
    custom_nodes_path,
    docs_path,
    web_dir,
):
    server = GraphServer(
        cmd_queue,
        state_conn,
        processor_pause_event,
        view_manager_queue,
        img_mem_args,
        close_event,
        root_path=root_path,
        custom_nodes_path=custom_nodes_path,
        docs_path=docs_path,
        web_dir=web_dir,
        host=args.host,
        port=args.port,
    )
    server.start()


def start_web(args):
    cmd_queue = mp.Queue()
    parent_conn, child_conn = mp.Pipe()
    view_manager_queue = mp.Queue()
    img_mem = (
        SharedMemoryManager(size=args.img_shm_size) if args.img_shm_size > 0 else None
    )
    close_event = mp.Event()
    pause_event = mp.Event()
    workflow_dir = args.workflow_dir
    custom_nodes_path = args.nodes_dir
    docs_path = args.docs_dir
    if not osp.exists(workflow_dir):
        os.mkdir(workflow_dir)
    if not osp.exists(custom_nodes_path):
        os.mkdir(custom_nodes_path)
    if not osp.exists(docs_path):
        os.mkdir(docs_path)
    processes = [
        mp.Process(
            target=create_graph_server,
            args=(
                args,
                cmd_queue,
                child_conn,
                pause_event,
                view_manager_queue,
                close_event,
                img_mem.get_shared_args() if img_mem else {},
                workflow_dir,
                custom_nodes_path,
                docs_path,
                args.web_dir,
            ),
        ),
    ]
    if args.start_media_server:
        processes.append(mp.Process(target=create_media_server, args=(args,)))

    for p in processes:
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

    async def start():
        processor = WebInstanceProcessor(
            cmd_queue,
            parent_conn,
            view_manager_queue,
            img_mem,
            args.continue_on_failure,
            args.copy_outputs,
            custom_nodes_path,
            close_event,
            pause_event,
            args.num_workers,
        )
        try:
            await processor.start_loop()
        finally:
            cleanup()

    asyncio.run(start())
