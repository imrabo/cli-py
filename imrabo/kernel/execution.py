"""
This module defines the core execution service of the imrabo kernel.
It orchestrates the lifecycle of an execution request, delegating
to various adapters (e.g., ArtifactResolver, EngineAdapter).
"""
import uuid
from typing import Iterator, Optional

from imrabo.kernel.contracts import (
    ExecutionRequest,
    ExecutionResult,
    ArtifactHandle,
    ArtifactResolver,
    EngineAdapter,
)

class KernelExecutionService:
    """
    Orchestrates the lifecycle of an execution, from artifact resolution
    to engine execution and result streaming.
    """
    def __init__(self, artifact_resolver: ArtifactResolver, engine_adapter: EngineAdapter):
        self.artifact_resolver = artifact_resolver
        self.engine_adapter = engine_adapter
        self._current_handle: Optional[ArtifactHandle] = None
        self._is_engine_loaded: bool = False

    def execute(self, request: ExecutionRequest) -> Iterator[ExecutionResult]:
        """
        Executes a given request through the kernel lifecycle.
        """
        request_id = request.request_id # For consistency
        
        try:
            # 1. Resolve Artifact
            yield ExecutionResult(
                request_id=request_id,
                status="resolving",
                output={"message": f"Resolving artifact: {request.artifact_ref}"},
                metrics={}
            )
            self._current_handle = self.artifact_resolver.ensure_available(request.artifact_ref)
            if not self._current_handle.is_available:
                raise RuntimeError(f"Artifact not available: {request.artifact_ref}")

            # 2. Load Engine (if not already loaded with this artifact)
            if not self._is_engine_loaded or self._current_handle.ref != getattr(self.engine_adapter, 'loaded_artifact_ref', None):
                yield ExecutionResult(
                    request_id=request_id,
                    status="loading_engine",
                    output={"message": f"Loading engine for artifact: {self._current_handle.ref}"},
                    metrics={}
                )
                self.engine_adapter.load(self._current_handle)
                self._is_engine_loaded = True
                setattr(self.engine_adapter, 'loaded_artifact_ref', self._current_handle.ref) # Track loaded artifact

            # 3. Execute
            yield ExecutionResult(
                request_id=request_id,
                status="executing",
                output={"message": "Executing request"},
                metrics={}
            )
            for result in self.engine_adapter.execute(request):
                yield result # Stream results directly from engine

            # 4. Final Cleanup/Completion (unloading engine happens on explicit stop/shutdown)
            yield ExecutionResult(
                request_id=request_id,
                status="completed",
                output={"message": "Execution finished"},
                metrics={} # Metrics from engine are already in results
            )

        except Exception as e:
            yield ExecutionResult(
                request_id=request_id,
                status="error",
                output={"error": str(e)},
                metrics={}
            )
            # Unload engine on error to ensure clean state
            self.engine_adapter.unload()
            self._is_engine_loaded = False
        finally:
            pass # No global unload here, as engine might be kept loaded for next request
                 # Explicit unload will be handled by daemon's lifecycle.

    def unload_engine(self):
        """Explicitly unloads the engine adapter."""
        if self._is_engine_loaded:
            self.engine_adapter.unload()
            self._is_engine_loaded = False
            self._current_handle = None
            setattr(self.engine_adapter, 'loaded_artifact_ref', None)
