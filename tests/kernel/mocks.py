from typing import Any, Iterator, List, Optional
from pathlib import Path
from imrabo.kernel.contracts import ArtifactHandle, ArtifactResolver, EngineAdapter, ExecutionRequest, ExecutionResult

class MockArtifactResolver(ArtifactResolver):
    """A mock implementation of ArtifactResolver for testing."""
    def __init__(self, default_handle: ArtifactHandle):
        self._default_handle = default_handle
        self.resolved_refs = []
        self.ensure_available_calls = []
        self.list_available_calls = []
        self.force_resolve_error = False
        self.force_ensure_available_error = False

    def resolve(self, ref: str) -> ArtifactHandle:
        self.resolved_refs.append(ref)
        if self.force_resolve_error:
            raise RuntimeError(f"Mock resolve error for {ref}")
        if ref == self._default_handle.ref:
            return self._default_handle
        return ArtifactHandle(ref=ref, is_available=False, location=None, metadata={})

    def ensure_available(self, ref: str) -> ArtifactHandle:
        self.ensure_available_calls.append(ref)
        if self.force_ensure_available_error:
            raise RuntimeError(f"Mock ensure_available error for {ref}")
        if ref == self._default_handle.ref:
            return ArtifactHandle(ref=ref, is_available=True, location=self._default_handle.location, metadata=self._default_handle.metadata)
        return ArtifactHandle(ref=ref, is_available=False, location=None, metadata={})

    def list_available(self) -> List[ArtifactHandle]:
        self.list_available_calls.append(True)
        if self.force_resolve_error: # Re-use for generic listing error
            raise RuntimeError("Mock list_available error")
        return [self._default_handle] if self._default_handle.is_available else []


class MockEngineAdapter(EngineAdapter):
    """A mock implementation of EngineAdapter for testing."""
    def __init__(self, results_to_yield: List[ExecutionResult] = None):
        self.loaded_artifact_ref: Optional[str] = None
        self.load_calls = []
        self.execute_calls = []
        self.unload_calls = []
        self.force_load_error = False
        self.force_execute_error = False
        self.force_unload_error = False
        self._results_to_yield = results_to_yield if results_to_yield is not None else []
        self._current_result_index = 0

    def load(self, handle: ArtifactHandle) -> None:
        self.load_calls.append(handle)
        if self.force_load_error:
            raise RuntimeError(f"Mock load error for {handle.ref}")
        self.loaded_artifact_ref = handle.ref

    def execute(self, request: ExecutionRequest) -> Iterator[ExecutionResult]:
        self.execute_calls.append(request)
        if self.force_execute_error:
            raise RuntimeError(f"Mock execute error for {request.request_id}")
        
        for i in range(self._current_result_index, len(self._results_to_yield)):
            yield self._results_to_yield[i]
            self._current_result_index = i + 1

    def unload(self) -> None:
        self.unload_calls.append(True)
        if self.force_unload_error:
            raise RuntimeError("Mock unload error")
        self.loaded_artifact_ref = None
        self._current_result_index = 0

