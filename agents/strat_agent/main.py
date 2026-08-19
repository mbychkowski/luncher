import os
import uvicorn

port = int(os.getenv("PORT", 8081))
os.environ["PORT"] = str(port)

if __name__ == "__main__":
    print(f"[Strategy Agent] Starting Strategy Agent server on port {port}...")
    # reload_dirs pins the watcher to the agent package. Left unset, uvicorn walks
    # the whole agent directory including .venv -- ~15k files instead of ~10.
    # watchfiles is a declared dependency, so uvicorn uses it in preference to
    # its polling StatReload fallback.
    uvicorn.run(
        "app.fast_api_app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=["app"],
    )

