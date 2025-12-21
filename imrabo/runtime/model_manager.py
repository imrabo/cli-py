import json
import os
import hashlib
import requests # For downloading
from pathlib import Path

from imrabo.internal import paths
from imrabo.runtime import system

# Placeholder for model management logic
class ModelManager:
    def __init__(self):
        self.models_registry = self._load_models_registry()
        print("ModelManager initialized.")

    def _load_models_registry(self):
        registry_path = Path(__file__).parent.parent / "registry" / "models.json"
        if not registry_path.exists():
            print(f"Error: Model registry not found at {registry_path}")
            return {}
        with open(registry_path, "r") as f:
            return json.load(f)

    def get_preferred_model(self):
        """
        Selects a model based on system RAM.
        Prioritizes the 7B model if sufficient RAM is available, otherwise falls back to 1.5B.
        """
        system_ram_gb = system.get_total_ram_gb()
        
        qwen_7b_config = self.models_registry.get("qwen2.5-7b")
        qwen_1_5b_config = self.models_registry.get("qwen2.5-1.5b")

        if qwen_7b_config and system_ram_gb >= qwen_7b_config["min_ram_gb"]:
            print(f"Selected 7B model. System RAM: {system_ram_gb}GB, Required: {qwen_7b_config['min_ram_gb']}GB")
            return qwen_7b_config
        elif qwen_1_5b_config and system_ram_gb >= qwen_1_5b_config["min_ram_gb"]:
            print(f"Selected 1.5B model. System RAM: {system_ram_gb}GB, Required: {qwen_1_5b_config['min_ram_gb']}GB")
            return qwen_1_5b_config
        else:
            print(f"Error: No suitable model found for {system_ram_gb}GB RAM.")
            return None

    def _calculate_sha256(self, file_path: Path) -> str:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def download_asset(self, url: str, sha256: str, target_dir: Path, filename: str):
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

    def ensure_model_available(self):
        selected_model = self.get_preferred_model()
        if not selected_model:
            return None

        model_variant = selected_model["variants"][0] # Assuming first variant for MVP
        model_filename = f"{selected_model['id']}-{model_variant['id']}.gguf"
        
        model_path = paths.get_models_dir()
        downloaded_path = self.download_asset(
            url=model_variant["url"],
            sha256=model_variant["sha256"],
            target_dir=Path(model_path),
            filename=model_filename
        )
        return downloaded_path

    def ensure_llama_cpp_binary_available(self):
        # For MVP, a simple placeholder that works cross-platform.
        print("Ensuring llama.cpp binary is available (placeholder)...")
        bin_dir = Path(paths.get_bin_dir())
        bin_dir.mkdir(parents=True, exist_ok=True)

        # A simple python script that sleeps is a good cross-platform placeholder server.
        dummy_binary_path = bin_dir / "dummy_llama_server.py"

        if not dummy_binary_path.exists():
            dummy_script_content = (
                "import time\n"
                "import sys\n"
                "print(f'Dummy llama.cpp server started with args: {sys.argv}')\n"
                "print('Process will sleep for an hour to simulate a running server.')\n"
                "time.sleep(3600)\n"
            )
            with open(dummy_binary_path, "w") as f:
                f.write(dummy_script_content)
        
        return dummy_binary_path

if __name__ == "__main__":
    manager = ModelManager()
    
    # Test preferred model selection
    print("\n--- Testing Model Selection ---")
    selected_model_config = manager.get_preferred_model()
    if selected_model_config:
        print(f"Preferred model config: {selected_model_config['id']}")
    else:
        print("No preferred model selected.")

    # Test dummy asset download (needs actual URLs in models.json to fully test)
    print("\n--- Testing Asset Download (Model) ---")
    # Note: This will try to download from example.com, which will fail.
    # Replace URLs in models.json with actual downloadable files for real testing.
    # The dummy_binary_path will be created.
    # downloaded_model = manager.ensure_model_available()
    # if downloaded_model:
    #     print(f"Model ensured available at: {downloaded_model}")
    # else:
    #     print("Failed to ensure model availability.")

    print("\n--- Testing Binary Availability ---")
    llama_binary_path = manager.ensure_llama_cpp_binary_available()
    print(f"Llama.cpp binary placeholder at: {llama_binary_path}")
