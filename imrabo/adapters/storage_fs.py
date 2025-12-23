"""
A concrete implementation of the ArtifactResolver that uses the local filesystem
and a JSON registry for model storage and discovery.
"""
import json
import hashlib
import time
import shutil
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any

from imrabo.internal import paths
from imrabo.internal.constants import MODEL_REGISTRY_FILE_NAME
from imrabo.kernel.artifacts import ArtifactResolver, ArtifactHandle


class FileSystemArtifactResolver(ArtifactResolver):
    """
    Manages artifacts stored on the local filesystem, sourced from a JSON registry.
    This is an 'adapter' in the hexagonal architecture.
    """
    def __init__(self, registry_path: Path, models_dir: Path):
        self._registry = self._load_registry(registry_path)
        self._models = self._registry.get("models", {})
        self._models_dir = models_dir
        self._models_dir.mkdir(parents=True, exist_ok=True)

    def _load_registry(self, registry_path: Path) -> Dict[str, Any]:
        if not registry_path.exists():
            raise RuntimeError(f"Model registry not found: {registry_path}")
        with open(registry_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_model_config(self, ref: str) -> Optional[dict]:
        # Simple ref parsing for now: "model:id/variant:id"
        parts = ref.split("/")
        model_id = parts[0].split(":")[1] if len(parts) > 0 and ":" in parts[0] else None
        variant_id = parts[1].split(":")[1] if len(parts) > 1 and ":" in parts[1] else None
        
        model = self._models.get(model_id)
        if not model:
            return None
        
        variants = model.get("variants", [])
        if not variants:
            return None
            
        variant = next((v for v in variants if v["id"] == variant_id), None) if variant_id else variants[0]
        if not variant:
            return None

        # Combine model and variant info into a single config
        config = model.copy()
        config.update(variant)
        config["model_id"] = model["id"]
        return config
    
    def _calculate_sha256(self, file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _download_file(self, url: str, target_path: Path, expected_sha: str) -> bool:
        temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(temp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
            
            actual_sha = self._calculate_sha256(temp_path)
            if actual_sha != expected_sha:
                print(f"Error: Checksum mismatch for {target_path.name}")
                return False
            
            temp_path.replace(target_path)
            return True
        except Exception as e:
            print(f"Error: Download failed for {target_path.name}: {e}")
            return False
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def resolve(self, ref: str) -> ArtifactHandle:
        config = self._get_model_config(ref)
        if not config:
            return ArtifactHandle(ref=ref, is_available=False, location=None, metadata={})

        model_dir = self._models_dir / config["model_id"]
        main_gguf = next((f["filename"] for f in config.get("files", []) if f["filename"].endswith(".gguf")), None)
        
        if not main_gguf or not (model_dir / main_gguf).exists():
            return ArtifactHandle(ref=ref, is_available=False, location=model_dir, metadata=config)
            
        return ArtifactHandle(ref=ref, is_available=True, location=model_dir / main_gguf, metadata=config)

    def ensure_available(self, ref: str) -> ArtifactHandle:
        handle = self.resolve(ref)
        if handle.is_available:
            return handle

        config = self._get_model_config(ref)
        if not config:
            raise ValueError(f"Could not resolve config for artifact: {ref}")

        model_dir = self._models_dir / config["model_id"]
        model_dir.mkdir(parents=True, exist_ok=True)

        for file_info in config.get("files", []):
            target_path = model_dir / file_info["filename"]
            if target_path.exists():
                if self._calculate_sha256(target_path) == file_info["sha256"]:
                    print(f"File already exists and is valid: {file_info['filename']}")
                    continue
            
            print(f"Downloading {file_info['filename']}...")
            success = self._download_file(file_info["url"], target_path, file_info["sha256"])
            if not success:
                raise RuntimeError(f"Failed to download and verify {file_info['filename']}")

        return self.resolve(ref)

    def list_available(self) -> list[ArtifactHandle]:
        handles = []
        for model_dir in self._models_dir.iterdir():
            if model_dir.is_dir():
                # This is a simplification. A real implementation would read a manifest
                # to reconstruct the original 'ref'. For now, we'll use the folder name.
                ref = f"model:{model_dir.name}/variant:unknown"
                handles.append(self.resolve(ref))
        return [h for h in handles if h.is_available]
