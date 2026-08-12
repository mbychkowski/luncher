# Auto-Reload Rule for Local Services

When running local services, dev servers, or agent servers (e.g. Uvicorn / FastAPI / Node / Vite), **ALWAYS** configure and run them using auto-reload (e.g., `reload=True` or `--reload`) if supported by the server framework.

This ensures code modifications take effect immediately without requiring manual process restarts.
