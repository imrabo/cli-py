from typing import Any, Protocol, Iterator
from dataclasses import dataclass

from imrabo.kernel.artifacts import ArtifactHandle


@dataclass
class ExecutionRequest:
    """
    An immutable request to execute a task against an artifact.
    This is a pure data contract with no logic.
    """
    request_id: str
    artifact_ref: str
    input: Any
    constraints: dict
    capabilities: list[str]

    def __post_init__(self):
        if not self.request_id:
            raise ValueError("request_id cannot be empty")
        if not self.artifact_ref:
            raise ValueError("artifact_ref cannot be empty")
        if not all(isinstance(cap, str) for cap in self.capabilities):
            raise TypeError("All capabilities must be strings")


@dataclass
class ExecutionResult:
    """
    An immutable result of an execution request.
    This is a pure data contract with no logic.
    """
    request_id: str
    status: str  # e.g., 'streaming', 'completed', 'error'
    output: Any
    metrics: dict


class EngineAdapter(Protocol):
    """
    Defines the contract for an execution engine.
    The Kernel interacts with engines ONLY through this interface.
    """

    def load(self, handle: ArtifactHandle) -> None:
        """
        Load the artifact specified by the handle into the engine.
        This may be a no-op if the engine is stateless.
        """
        ...

    def execute(self, request: ExecutionRequest) -> Iterator[ExecutionResult]:
        """
        Execute a request and stream back results.
        This is the core method for running inference, a build, or any other task.
        """
        ...

    def unload(self) -> None:
        """
        Unload the current artifact, releasing resources.
        """
        ...
