import json
import os
import hashlib
import requests
from pathlib import Path
import shutil # For disk space check

from imrabo.internal import paths
from imrabo.runtime import system # Assuming system.get_total_ram_gb() is here
from imrabo.internal.constants import MODEL_REGISTRY_FILE_NAME # Assuming this is the name of the central registry file

class ModelManager:
    def __init__(self):
        # Ensure the main models directory exists
        self.local_models_dir = Path(paths.get_models_dir())
        self.local_models_dir.mkdir(parents=True, exist_ok=True)
        
        # Load the global registry (imrabo/registry/models.json) for available models
        self.global_models_registry = self._load_global_models_registry()
        print("ModelManager initialized.")

    def _load_global_models_registry(self):
        # This path should point to the imrabo/registry/models.json within the package
        package_registry_path = Path(__file__).parent.parent / "registry" / "models.json"
        if not package_registry_path.exists():
            print(f"Error: Global model registry not found at {package_registry_path}")
            return {}
        with open(package_registry_path, "r") as f:
            return json.load(f)

    def get_preferred_model(self) -> dict | None:
        """
        Selects a model and its variant based on system RAM and the global registry.
        """
        system_ram_gb = system.get_total_ram_gb()
        
        best_model_data = None
        best_selected_variant = None

        for model_id, model_data in self.global_models_registry.items():
            if model_data["min_ram_gb"] <= system_ram_gb:
                # Assuming we pick the first variant for now as per MVP
                selected_variant = model_data["variants"][0] 
                
                # Check if this model is better than previously found
                if not best_model_data or model_data["min_ram_gb"] > best_model_data["min_ram_gb"]:
                    best_model_data = model_data
                    best_selected_variant = selected_variant

        if best_model_data and best_selected_variant:
            print(f"Selected model: {best_model_data['id']} ({best_selected_variant['id']}). System RAM: {system_ram_gb}GB, Required: {best_model_data['min_ram_gb']}GB")
            # Return the combined config which now includes the files array
            return {
                "id": best_model_data["id"],
                "engine": best_model_data["engine"],
                "min_ram_gb": best_model_data["min_ram_gb"],
                "variant_id": best_selected_variant["id"],
                "files": best_selected_variant["files"], # Pass the files array directly
                "total_size_gb": best_selected_variant["total_size_gb"]
            }
        else:
            print(f"Error: No suitable model found for {system_ram_gb}GB RAM.")
            return None

    def _calculate_sha256(self, file_path: Path) -> str:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def _validate_disk_space(self, total_size_gb: float, target_dir: Path) -> bool:
        """Checks if there is enough disk space in target_dir for the given total_size_gb."""
        total, used, free = shutil.disk_usage(target_dir)
        free_gb = free / (1024**3)
        required_gb = total_size_gb * 1.1 # Add a 10% buffer
        
        if free_gb < required_gb:
            print(f"Error: Not enough disk space. Required: {required_gb:.2f}GB, Available: {free_gb:.2f}GB")
            return False
        return True

    def download_asset(self, url: str, sha256: str, target_dir: Path, filename: str, file_size_gb: float):
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename
        
        if file_path.exists():
            print(f"Asset already exists at {file_path}. Verifying checksum...")
            if self._calculate_sha256(file_path) == sha256:
                print("Checksum matches. Using existing asset.")
                return file_path
            else:
                print("Checksum mismatch. Re-downloading asset.")
                file_path.unlink() # Delete corrupted file

        # Disk space check moved to ensure_model_available for total_size_gb
        # if not self._validate_disk_space(file_size_gb, target_dir):
        #     return None

        print(f"Downloading asset from {url} to {file_path}...")
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            if self._calculate_sha256(file_path) == sha256:
                print("Download complete and checksum verified.")
                return file_path
            else:
                print(f"Error: Checksum mismatch after download for {filename}. Deleting corrupted file.")
                file_path.unlink()
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error downloading asset from {url}: {e}")
            return None

    def ensure_model_available(self) -> Path | None:
        selected_model_config = self.get_preferred_model()
        if not selected_model_config:
            return None

        model_id = selected_model_config["id"]
        
        # Create model-specific subdirectory within local_models_dir
        model_specific_dir = self.local_models_dir / model_id
        model_specific_dir.mkdir(parents=True, exist_ok=True)

        model_manifest_path = model_specific_dir / MODEL_REGISTRY_FILE_NAME # model.json will be named MODEL_REGISTRY_FILE_NAME

        # Disk space validation for the total model size
        if not self._validate_disk_space(selected_model_config["total_size_gb"], model_specific_dir):
            return None

        all_files_available = True
        downloaded_paths = []
        main_gguf_path = None

        for file_info in selected_model_config["files"]:
            filename = file_info["filename"]
            url = file_info["url"]
            sha256 = file_info["sha256"]
            size_gb = file_info["size_gb"]
            
            file_path = model_specific_dir / filename
            downloaded_path = self.download_asset(
                url=url,
                sha256=sha256,
                target_dir=model_specific_dir,
                filename=filename,
                file_size_gb=size_gb # Pass individual file size
            )
            
            if not downloaded_path:
                all_files_available = False
                break
            downloaded_paths.append(downloaded_path)
            
            if filename.endswith(".gguf") and main_gguf_path is None: # Assuming the first GGUF file is the main one
                main_gguf_path = downloaded_path

        if all_files_available:
            print(f"All files for model {model_id} available and verified.")
            # Save the specific model variant config to a model.json file in its directory
            with open(model_manifest_path, "w") as f:
                json.dump(selected_model_config, f, indent=2)
            
            return main_gguf_path # Return path to the main GGUF file
        else:
            print("Failed to ensure all model files availability.")
            # Clean up partially downloaded files if any
            for path in downloaded_paths:
                if path.exists():
                    path.unlink()
            if model_manifest_path.exists():
                model_manifest_path.unlink()
            return None