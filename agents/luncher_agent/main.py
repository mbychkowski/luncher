import os
import uvicorn
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# We import the root_agent from agent.py
from app.agent import root_agent

from fastapi import Request
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.a2a.utils.agent_to_a2a import to_a2a

port = int(os.getenv("PORT", 8082))

# 1. Create native A2A server
a2a_server = to_a2a(root_agent, port=port)

# 2. Trigger a2a_server's lifespan during FastAPI application startup
@asynccontextmanager
async def lifespan(app):
    async with a2a_server.router.lifespan_context(a2a_server):
        yield

# 3. Create ADK FastAPI app (serving Web UI playground + ADK SSE /run_sse)
agents_dir = os.path.dirname(os.path.abspath(__file__))
a2a_app = get_fast_api_app(
    agents_dir=agents_dir,
    web=True,
    a2a=False,
    host="0.0.0.0",
    port=port,
    lifespan=lifespan,
)

# 4. Mount sub-apps for sub-paths and GET requests
a2a_app.mount("/a2a/luncher_agent", a2a_server)
a2a_app.mount("/a2a/luncher-agents", a2a_server)
a2a_app.mount("/a2a/app", a2a_server)

# 5. Middleware to transparently rewrite exact /a2a/* paths without trailing slash redirects
@a2a_app.middleware("http")
async def a2a_path_middleware(request: Request, call_next):
    if request.url.path in ("/a2a/luncher_agent", "/a2a/luncher-agents", "/a2a/app"):
        scope = dict(request.scope)
        scope["path"] = "/"
        response_data = []
        async def send(message):
            if message["type"] == "http.response.start":
                scope["response_status"] = message["status"]
                scope["response_headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                response_data.append(message.get("body", b""))
        await a2a_server(scope, request.receive, send)
        from fastapi.responses import Response
        return Response(
            content=b"".join(response_data),
            status_code=scope.get("response_status", 200),
            headers=dict((k.decode(), v.decode()) for k, v in scope.get("response_headers", []))
        )
    return await call_next(request)

if __name__ == "__main__":
    print(f"[Orchestrator] Starting ADK Web UI & A2A server on port {port}...")
    uvicorn.run(a2a_app, host="0.0.0.0", port=port)
