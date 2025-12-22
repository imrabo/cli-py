# import uvicorn
# from fastapi import FastAPI, Depends, Request, Response, status, HTTPException
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from fastapi.responses import StreamingResponse # Import StreamingResponse
# import asyncio
# import os
# import signal
# import sys
# from pathlib import Path
# from pydantic import BaseModel # Import BaseModel
# import json

# from imrabo.internal import paths
# from imrabo.internal.logging import get_logger
# from imrabo.internal.constants import RUNTIME_HOST, RUNTIME_PORT
# from imrabo.runtime.security import load_token, generate_token, save_token
# from imrabo.runtime.model_manager import ModelManager
# from imrabo.engine.factory import EngineFactory # Import EngineFactory
# from imrabo.engine.base import LLMEngine # Import LLMEngine

# logger = get_logger()
# app = FastAPI()
# event_loop: asyncio.AbstractEventLoop | None = None
# security = HTTPBearer()


# @app.on_event("startup")
# async def on_startup():
#     global event_loop
#     event_loop = asyncio.get_running_loop()

# # Pydantic model for the /run endpoint
# class PromptInput(BaseModel):
#     prompt: str

# # Global instances (will be initialized on startup)
# model_manager: ModelManager | None = None
# # llm_engine: LLMEngine | None = None # Removed global llm_engine

# # Configuration for the engine type
# ENGINE_TYPE = "llama_binary" # New config flag

# # --- Token Management ---
# def get_runtime_token() -> str:
#     token_file = Path(paths.get_runtime_token_file())
#     token = load_token(token_file)
#     if not token:
#         token = generate_token()
#         save_token(token, token_file)
#     return token

# RUNTIME_AUTH_TOKEN = get_runtime_token()

# async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
#     if credentials.scheme != "Bearer" or credentials.credentials != RUNTIME_AUTH_TOKEN:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid authentication credentials",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     return True

# # --- Startup/Shutdown Events ---
# @app.on_event("startup")
# async def startup_event():
#     global model_manager, llm_engine, current_model_path
#     logger.info("Starting imrabo runtime...")
#     logger.info(f"Configured LLM Engine Type: {ENGINE_TYPE}") # Added log message

#     model_manager = ModelManager()

#     # Ensure model is available
#     # For llama_binary, the model_manager still resolves the path, but the binary engine decides how to use it.
#     current_model_path = model_manager.ensure_model_available()
#     if not current_model_path:
#         logger.error("Failed to ensure model availability. Runtime will not start LLM engine.")
#         return

#     # Instantiate the LLM engine via factory
#     try:
#         llm_engine = EngineFactory.create(ENGINE_TYPE, current_model_path) # Pass current_model_path
#         llm_engine.load() # Call load without model_path, as per new contract
#     except Exception as e:
#         logger.error(f"Failed to load LLM engine: {e}. Runtime will not start LLM engine.")
#         print(f"ERROR: Failed to load LLM engine: {e}", file=sys.stderr)
#         llm_engine = None
#         return
    
#     logger.info("imrabo runtime started successfully.")

# @app.on_event("shutdown")
# async def shutdown_event():
#     global llm_engine
#     logger.info("Shutting down imrabo runtime...")
#     if llm_engine:
#         llm_engine.unload()
#     logger.info("imrabo runtime shutdown complete.")

# # --- API Endpoints ---

# @app.get("/health", dependencies=[Depends(verify_token)])
# async def health():
#     return {"status": "ok"}

# @app.get("/status", dependencies=[Depends(verify_token)])
# async def status_endpoint():
#     model_status = "unavailable"
#     model_details = {}
#     if current_model_path and current_model_path.exists():
#         model_status = "available"
#         model_details = {"path": str(current_model_path), "name": current_model_path.name}

#     llm_engine_status = "unavailable"
#     if llm_engine and llm_engine.llm is not None: # Check if the internal Llama instance is loaded
#         llm_engine_status = "loaded"
#     elif llm_engine:
#         llm_engine_status = "unloaded"

#     return {
#         "status": "running",
#         "model": model_status,
#         "model_details": model_details,
#         "llm_engine": llm_engine_status,
#         "runtime_pid": os.getpid()
#     }

# @app.post("/shutdown", dependencies=[Depends(verify_token)])
# async def shutdown_endpoint():
#     logger.info("Shutdown request received.")
#     # Perform graceful shutdown
#     if llm_engine:
#         llm_engine.unload()
    
#     # Exit the Uvicorn server gracefully
#     os.kill(os.getpid(), signal.SIGTERM)
#     return {"message": "Shutting down"}

# @app.post("/run", dependencies=[Depends(verify_token)])
# async def run_endpoint(prompt_input: PromptInput): # Use PromptInput model
#     global llm_engine
#     if not llm_engine:
#         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM engine is not initialized.")
    
#     health_status = llm_engine.health()
#     if health_status.get("status") != "ready":
#         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"LLM engine is not ready: {health_status.get('status', 'unknown')}")
    
#     async def stream_tokens():
#         try:
#             # Create a queue to hold streamed tokens
#             token_queue = asyncio.Queue()

#             def stream_callback(token: str):
#                 asyncio.run_coroutine_threadsafe(token_queue.put(token), event_loop)
#                 # asyncio.run_coroutine_threadsafe(token_queue.put(token), app.loop)

#             # Run inference in a separate thread to avoid blocking the event loop
#             loop = asyncio.get_event_loop()
#             await loop.run_in_executor(None, llm_engine.infer, prompt_input.prompt, stream_callback)
            
#             # Signal the end of the stream
#             asyncio.run_coroutine_threadsafe(token_queue.put(None), app.loop) # Use None as a sentinel
            
#             while True:
#                 token = await token_queue.get()
#                 if token is None: # Sentinel value indicates end of stream
#                     break
#                 yield f"data: {json.dumps({'content': token, 'stop': False})}\n\n"
            
#             # Send final stop signal
#             yield f"data: {json.dumps({'content': '', 'stop': True})}\n\n"

#         except Exception as e:
#             logger.error(f"Error during LLM generation: {e}")
#             error_data = {"error": f"Error during LLM generation: {e}"}
#             yield f"data: {json.dumps(error_data)}\n\n"
#             yield f"data: {json.dumps({'content': '', 'stop': True})}\n\n"

#     return StreamingResponse(stream_tokens(), media_type="text/event-stream")

# # --- Main entry point for Uvicorn ---
# if __name__ == "__main__":
#     logger.info(f"imrabo runtime token: {RUNTIME_AUTH_TOKEN}")
#     uvicorn.run(app, host=RUNTIME_HOST, port=RUNTIME_PORT, workers=1, reload=False)

import uvicorn
import asyncio
import os
import signal
import sys
import json
from pathlib import Path

from fastapi import FastAPI, Depends, status, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from imrabo.internal import paths
from imrabo.internal.logging import get_logger
from imrabo.internal.constants import RUNTIME_HOST, RUNTIME_PORT
from imrabo.runtime.security import load_token, generate_token, save_token
from imrabo.runtime.model_manager import ModelManager
from imrabo.engine.factory import EngineFactory
from imrabo.engine.base import LLMEngine

# ---------------------------------------------------------------------
# App + globals
# ---------------------------------------------------------------------

logger = get_logger(__name__)
app = FastAPI()
security = HTTPBearer()

event_loop: asyncio.AbstractEventLoop | None = None
model_manager: ModelManager | None = None
llm_engine: LLMEngine | None = None
current_model_path: Path | None = None

ENGINE_TYPE = "llama_binary"

# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------

def get_runtime_token() -> str:
    token_file = paths.get_runtime_token_file()
    token = load_token(token_file)
    if not token:
        token = generate_token()
        save_token(token, token_file)
    return token

RUNTIME_AUTH_TOKEN = get_runtime_token()


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
# Lifecycle
# ---------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    global event_loop, model_manager, llm_engine, current_model_path

    event_loop = asyncio.get_running_loop()
    logger.info("Starting imrabo runtime")
    logger.info("Configured engine", extra={"engine": ENGINE_TYPE})

    model_manager = ModelManager()

    try:
        current_model_path = model_manager.ensure_model_available()
        if not current_model_path:
            raise RuntimeError("Model resolution failed")

        llm_engine = EngineFactory.create(ENGINE_TYPE, current_model_path)
        llm_engine.load()

        logger.info("LLM engine loaded successfully")

    except Exception as e:
        logger.exception("Failed to initialize LLM engine")
        llm_engine = None


@app.on_event("shutdown")
async def on_shutdown():
    global llm_engine
    logger.info("Shutting down imrabo runtime")

    if llm_engine:
        llm_engine.unload()

    logger.info("Runtime shutdown complete")


# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------

class PromptInput(BaseModel):
    prompt: str


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------

@app.get("/health", dependencies=[Depends(verify_token)])
async def health():
    return {"status": "ok"}


@app.get("/status", dependencies=[Depends(verify_token)])
async def status_endpoint():
    return {
        "status": "running",
        "runtime_pid": os.getpid(),
        "model": {
            "available": bool(current_model_path and current_model_path.exists()),
            "path": str(current_model_path) if current_model_path else None,
        },
        "llm_engine": llm_engine.health() if llm_engine else {"status": "unavailable"},
    }


@app.post("/shutdown", dependencies=[Depends(verify_token)])
async def shutdown_endpoint():
    logger.info("Shutdown requested")
    os.kill(os.getpid(), signal.SIGTERM)
    return {"message": "Shutting down"}


@app.post("/run", dependencies=[Depends(verify_token)])
async def run_endpoint(prompt_input: PromptInput):
    if not llm_engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM engine is not initialized",
        )

    engine_health = llm_engine.health()
    if engine_health.get("status") != "ready":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM engine not ready: {engine_health.get('status')}",
        )

    async def stream_tokens():
        token_queue: asyncio.Queue[str | None] = asyncio.Queue()

        def stream_callback(token: str):
            # SAFE cross-thread → asyncio bridge
            asyncio.run_coroutine_threadsafe(
                token_queue.put(token),
                event_loop,
            )

        try:
            # Run blocking inference off the event loop
            await asyncio.get_running_loop().run_in_executor(
                None,
                llm_engine.infer,
                prompt_input.prompt,
                stream_callback,
            )

        except Exception as e:
            logger.exception("Inference error")
            yield f"data: {json.dumps({'error': str(e), 'stop': True})}\n\n"
            return

        # Normal streaming
        while True:
            token = await token_queue.get()
            if token is None:
                break

            yield f"data: {json.dumps({'content': token, 'stop': False})}\n\n"

        yield f"data: {json.dumps({'content': '', 'stop': True})}\n\n"

    return StreamingResponse(
        stream_tokens(),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting runtime server", extra={"port": RUNTIME_PORT})
    uvicorn.run(
        app,
        host=RUNTIME_HOST,
        port=RUNTIME_PORT,
        workers=1,
        reload=False,
    )
