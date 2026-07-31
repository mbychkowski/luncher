import os
import uvicorn

port = int(os.getenv("PORT", 8080))
os.environ["PORT"] = str(port)

from app.fast_api_app import app as a2a_app

if __name__ == "__main__":
    print(f"[Luncher Agent] Starting Luncher Orchestrator server on port {port}...")
    uvicorn.run(a2a_app, host="0.0.0.0", port=port)

