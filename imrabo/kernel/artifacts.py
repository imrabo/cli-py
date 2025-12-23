"""
Defines the abstract contracts for resolving and managing artifacts.

This is a core part of the Kernel. It defines the 'port' for which
storage and registry adapters must be provided.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

@dataclass
class ArtifactHandle:
    """
    A handle to a resolved artifact, providing access to its location and metadata.
    The kernel operates on these handles, not on concrete file paths or URLs.
    """
    ref: str
    is_available: bool
    location: Any  # Could be a Path, a URL, a database key, etc.
    metadata: dict

class ArtifactResolver(Protocol):
    """
    The interface (port) for any system that can resolve an artifact reference
    string into a concrete, usable handle.
    """

    @abstractmethod
    def resolve(self, ref: str) -> ArtifactHandle:
        """
        Resolves an artifact reference string into a handle.

        This method should not perform downloads or long operations. It should
        check for the local availability of the artifact and return a handle
        reflecting its state.

        Args:
            ref: The reference string (e.g., "model:llama3/variant:8b-instruct").

        Returns:
            An ArtifactHandle.
        """
        ...

    @abstractmethod
    def ensure_available(self, ref: str) -> ArtifactHandle:
        """
        Ensures an artifact is available for use, potentially downloading it.

        This method is expected to be a long-running operation.

        Args:
            ref: The reference string.

        Returns:
            An ArtifactHandle, which should have `is_available=True` on success.
        """
        ...

    @abstractmethod
    def list_available(self) -> list[ArtifactHandle]:
        """
        Lists all artifacts that are currently available locally.
        """
        ...
