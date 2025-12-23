import uvicorn
import asyncio
import os
import signal
import sys
import json
from pathlib import Path
import typer

from fastapi import FastAPI, Depends, status, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Corrected imports for the new structure
from imrabo.internal import paths
from imrabo.internal.logging import get_logger
from imrabo.internal.constants import RUNTIME_HOST, RUNTIME_PORT
# The security module will also need to be moved or adapted eventually
from imrabo.internal.security import load_token, generate_token, save_token

# Kernel contracts are the new interface
from imrabo.kernel.contracts import ExecutionRequest, ExecutionResult

# Placeholder for the kernel. In a real app, this would be injected.
class KernelPlaceholder:
    def get_status(self):
        # This would query kernel subsystems
        return {"status": "ok_from_kernel"}

    def execute(self, request: ExecutionRequest):
        # This would delegate to the kernel's execution service
        print(f"Kernel received request: {request}")
        yield ExecutionResult(request_id=request.request_id, status="streaming", output={"content": "Hello, ", "stop": False}, metrics={})
        yield ExecutionResult(request_id=request.request_id, status="streaming", output={"content": "world!", "stop": False}, metrics={})
        yield ExecutionResult(request_id=request.request_id, status="completed", output={"content": "", "stop": True}, metrics={"time": 1.23})

kernel = KernelPlaceholder()


# --------------------------------------------------------------------- 
# App
# --------------------------------------------------------------------- 

logger = get_logger(__name__)
app = FastAPI()
cli_app = typer.Typer()
security = HTTPBearer()


# --------------------------------------------------------------------- 
# Auth (remains in the adapter layer)
# --------------------------------------------------------------------- 

# def get_runtime_token() -> str:
#     token_file = paths.get_runtime_token_file()
#     token = load_token(token_file)
#     if not token:
#         token = generate_token()
#         save_token(token, token_file)
#     return token

# RUNTIME_AUTH_TOKEN = get_runtime_token()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials.scheme != "Bearer" or credentials.credentials != RUNTIME_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


# --------------------------------------------------------------------- 
# Models
# --------------------------------------------------------------------- 

class PromptInput(BaseModel):
    prompt: str


# --------------------------------------------------------------------- 
# Endpoints (adapt HTTP to Kernel contracts)
# --------------------------------------------------------------------- 

@app.get("/health", dependencies=[Depends(verify_token)])
async def health():
    return {"status": "ok"}


@app.get("/status", dependencies=[Depends(verify_token)])
async def status_endpoint():
    # Delegate to kernel
    return kernel.get_status()


@app.post("/shutdown", dependencies=[Depends(verify_token)])
async def shutdown_endpoint():
    # This is a process-level concern, stays here for now
    logger.info("Shutdown requested")
    os.kill(os.getpid(), signal.SIGTERM)
    return {"message": "Shutting down"}


@app.post("/run", dependencies=[Depends(verify_token)])
async def run_endpoint(prompt_input: PromptInput):
    # 1. Translate HTTP request to Kernel ExecutionRequest
    # In the future, model/variant IDs would be part of the request
    request = ExecutionRequest(
        request_id="some_unique_id", # Should be generated
        artifact_ref="model:some_model/variant:some_variant",
        input=prompt_input.prompt,
        constraints={},
        capabilities=["streaming"]
    )

    # 2. Define how to stream kernel results back over HTTP
    async def stream_events():
        try:
            # 3. Call the kernel
            for result in kernel.execute(request):
                # 4. Translate ExecutionResult back to HTTP SSE format
                yield f"data: {json.dumps(result.output)}\\n\n"
                if result.status == "completed":
                    break
        except Exception as e:
            logger.exception("Kernel execution error")
            error_payload = {"error": str(e), "stop": True}
            yield f"data: {json.dumps(error_payload)}\\n\n"

    # 5. Return the streaming response
    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
    )


# --------------------------------------------------------------------- 
# Entry point (Simplified)
# --------------------------------------------------------------------- 

@cli_app.command()
def main(
    # These options are now for configuring the adapter, not the engine
    host: str = typer.Option(RUNTIME_HOST, help="Host to bind the server to."),
    port: int = typer.Option(RUNTIME_PORT, help="Port to bind the server to."),
):
    """
    Main entry point for the runtime server adapter.
    It does NOT load models or engines.
    """
    logger.info("Starting imrabo runtime adapter")
    
    # In a real scenario, the kernel would be initialized and passed here
    # from a higher-level application bootstrapper.

    logger.info("Starting API server", extra={"host": host, "port": port})
    uvicorn.run(
        app,
        host=host,
        port=port,
        workers=1,
        reload=False,
    )

if __name__ == "__main__":
    cli_app()