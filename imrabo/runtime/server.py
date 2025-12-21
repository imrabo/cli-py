import uvicorn
from fastapi import FastAPI, Depends, Request, Response, status, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncio
import os
import signal
import sys
from pathlib import Path
import httpx # For making requests to llama.cpp server

from imrabo.internal import paths
from imrabo.internal.logging import get_logger
from imrabo.internal.constants import RUNTIME_HOST, RUNTIME_PORT
from imrabo.runtime.security import load_token, generate_token, save_token
from imrabo.runtime.model_manager import ModelManager
from imrabo.engine.llama_cpp import LlamaCppBinary

logger = get_logger()
app = FastAPI()
security = HTTPBearer()

# Global instances (will be initialized on startup)
model_manager: ModelManager | None = None
llama_cpp_process_manager: LlamaCppBinary | None = None # Renamed to avoid confusion with FastAPI app
current_model_path: Path | None = None
llama_cpp_api_url: str | None = None

# --- Token Management ---
def get_runtime_token() -> str:
    token_file = Path(paths.get_runtime_token_file())
    token = load_token(token_file)
    if not token:
        token = generate_token()
        save_token(token, token_file)
    return token

RUNTIME_AUTH_TOKEN = get_runtime_token()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.scheme != "Bearer" or credentials.credentials != RUNTIME_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True

# --- Startup/Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    global model_manager, llama_cpp_process_manager, current_model_path, llama_cpp_api_url
    logger.info("Starting imrabo runtime...")

    model_manager = ModelManager()

    # Ensure model is available
    current_model_path = model_manager.ensure_model_available()
    if not current_model_path:
        logger.error("Failed to ensure model availability. Runtime will not start model.")
        return

    # Ensure llama.cpp binary is available
    llama_cpp_binary_path = model_manager.ensure_llama_cpp_binary_available()
    if not llama_cpp_binary_path:
        logger.error("Failed to ensure llama.cpp binary availability. Runtime will not start model.")
        return

    # Llama.cpp server will run on a different port than the FastAPI app
    llama_cpp_server_port = RUNTIME_PORT + 1 
    llama_cpp_api_url = f"http://{RUNTIME_HOST}:{llama_cpp_server_port}"

    llama_cpp_process_manager = LlamaCppBinary(llama_cpp_binary_path, current_model_path)
    
    # Start llama.cpp server
    if not llama_cpp_process_manager.start_server(host=RUNTIME_HOST, port=llama_cpp_server_port):
        logger.error("Failed to start llama.cpp server.")
        return
    
    logger.info("imrabo runtime started successfully.")

@app.on_event("shutdown")
async def shutdown_event():
    global llama_cpp_process_manager
    logger.info("Shutting down imrabo runtime...")
    if llama_cpp_process_manager:
        llama_cpp_process_manager.stop_server()
    logger.info("imrabo runtime shutdown complete.")

# --- API Endpoints ---

@app.get("/health", dependencies=[Depends(verify_token)])
async def health():
    return {"status": "ok"}

@app.get("/status", dependencies=[Depends(verify_token)])
async def status_endpoint():
    model_status = "unavailable"
    model_details = {}
    if current_model_path and current_model_path.exists():
        model_status = "available"
        model_details = {"path": str(current_model_path), "name": current_model_path.name}

    llama_status = "unavailable"
    if llama_cpp_process_manager and llama_cpp_process_manager.is_server_running():
        llama_status = "running"
    elif llama_cpp_process_manager:
        llama_status = "stopped"

    return {
        "status": "running",
        "model": model_status,
        "model_details": model_details,
        "llama_cpp_server": llama_status,
        "llama_cpp_api_url": llama_cpp_api_url,
        "runtime_pid": os.getpid()
    }

@app.post("/shutdown", dependencies=[Depends(verify_token)])
async def shutdown_endpoint():
    logger.info("Shutdown request received.")
    # Perform graceful shutdown
    if llama_cpp_process_manager:
        llama_cpp_process_manager.stop_server()
    
    # Exit the Uvicorn server gracefully
    # This might need a bit more finessing for truly graceful shutdown in FastAPI
    # For now, let's signal the process to exit.
    os.kill(os.getpid(), signal.SIGTERM)
    return {"message": "Shutting down"}

@app.post("/run", dependencies=[Depends(verify_token)])
async def run_endpoint(request: Request):
    global llama_cpp_api_url
    if not llama_cpp_process_manager or not llama_cpp_process_manager.is_server_running() or not llama_cpp_api_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Llama.cpp server is not running or API URL is not set.")
    
    payload = await request.json()
    prompt = payload.get("prompt")
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt is required.")

    # Prepare payload for llama.cpp /completion endpoint
    # Assuming llama.cpp server uses a structure like:
    llama_cpp_payload = {
        "prompt": prompt,
        "n_predict": -1, # Generate until EOS
        "temperature": 0.7,
        "stream": True # Request streaming response
    }
    
    # Make an async HTTP request to the llama.cpp server and stream the response back
    async def stream_from_llama_cpp():
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", f"{llama_cpp_api_url}/completion", json=llama_cpp_payload, timeout=None) as response:
                    # Check for an error response on the initial connection
                    response.raise_for_status()
                    # Stream the raw chunks back to the client
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except httpx.RequestError as exc:
            logger.error("Request to llama.cpp server failed", error=str(exc))
            error_data = {"error": "Connection to the internal LLM engine failed."}
            yield f"data: {json.dumps(error_data)}\n\n"
            yield f"data: {json.dumps({'stop': True})}\n\n"
        except httpx.HTTPStatusError as exc:
            logger.error(
                "llama.cpp server returned an error", 
                status_code=exc.response.status_code, 
                response=exc.response.text
            )
            error_data = {"error": f"Internal LLM engine returned status {exc.response.status_code}"}
            yield f"data: {json.dumps(error_data)}\n\n"
            yield f"data: {json.dumps({'stop': True})}\n\n"

    return Response(stream_from_llama_cpp(), media_type="text/event-stream")

# --- Main entry point for Uvicorn ---
if __name__ == "__main__":
    logger.info(f"imrabo runtime token: {RUNTIME_AUTH_TOKEN}")
    uvicorn.run(app, host=RUNTIME_HOST, port=RUNTIME_PORT)
