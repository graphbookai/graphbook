import asyncio
from aiohttp import web
import os.path as osp

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

class MediaServer:
    def __init__(
        self,
        address="0.0.0.0",
        port=8006,
        root_path="./workflow",
    ):
        self.address = address
        self.port = port
        self.root_path = root_path
        routes = web.RouteTableDef()
        self.routes = routes
        middlewares = [cors_middleware]
        self.app = web.Application(
            middlewares=middlewares
        )
        
        @routes.put("/set")
        async def set_var_handler(request: web.Request):
            data = await request.json()
            root_path = data.get("root_path")
            if root_path:
                self.root_path = root_path
            return web.json_response({"root_path": self.root_path})
        
        @routes.get(r"/{path:.*}")
        async def handle(request: web.Request) -> web.Response:
            path = request.match_info["path"]
            full_path = osp.join(self.root_path, path)
            if not osp.exists(full_path):
                return web.HTTPNotFound()
            with open(full_path, "rb") as f:
                content = f.read()
            return web.Response(body=content)
        
        
    async def _async_start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.address, self.port, shutdown_timeout=0.5)
        await site.start()
        await asyncio.Event().wait()

    def start(self):
        self.app.router.add_routes(self.routes)
        print(f"Starting media server at {self.address}:{self.port}")
        try:
            asyncio.run(self._async_start())
        except KeyboardInterrupt:
            print("Exiting media server")
