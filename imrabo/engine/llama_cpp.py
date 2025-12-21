import subprocess
import os
import time
from pathlib import Path

from imrabo.internal import paths
from imrabo.internal.logging import configure_logging
from imrabo.internal.constants import RUNTIME_HOST, RUNTIME_PORT

logger = configure_logging()

class LlamaCppBinary:
    def __init__(self, binary_path: Path, model_path: Path):
        self.binary_path = binary_path
        self.model_path = model_path
        self.process: subprocess.Popen | None = None
        logger.info(f"LlamaCppBinary initialized with binary: {binary_path}, model: {model_path}")

    def start_server(self, host: str = RUNTIME_HOST, port: int = RUNTIME_PORT):
        if not self.binary_path.exists():
            logger.error(f"Llama.cpp binary not found at {self.binary_path}")
            return False
        if not self.model_path.exists():
            logger.error(f"Model GGUF file not found at {self.model_path}")
            return False

        if self.is_server_running():
            logger.info("Llama.cpp server already running.")
            return True

        # Assuming llama.cpp has a 'server' executable or 'main' with --port argument
        # For simplicity in MVP, let's assume 'main' executable with --port
        # Real llama.cpp server might be a separate executable or specific arguments.
        command = [
            str(self.binary_path),
            "-m", str(self.model_path),
            "--host", host,
            "--port", str(port),
            "-c", "4096", # Context size
            "-n", "-1",  # Infinite generation
            "-t", "4",   # Threads
            "--mlock" # Lock model into RAM
        ]
        
        # Redirect stdout/stderr to files for debugging and to prevent blocking
        log_dir = Path(paths.get_app_data_dir()) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_log = open(log_dir / "llama_cpp_stdout.log", "a")
        stderr_log = open(log_dir / "llama_cpp_stderr.log", "a")

        try:
            self.process = subprocess.Popen(
                command,
                stdout=stdout_log,
                stderr=stderr_log,
                preexec_fn=os.setsid if os.name != 'nt' else None, # Detach on Unix-like
                creationflags=subprocess.DETACHED_PROCESS if os.name == 'nt' else 0 # Detach on Windows
            )
            logger.info(f"Started llama.cpp server with PID: {self.process.pid}")
            # Give it a moment to start
            time.sleep(2) 
            return True
        except Exception as e:
            logger.error(f"Failed to start llama.cpp server: {e}")
            if self.process:
                self.process.kill()
            return False

    def stop_server(self):
        if self.process and self.is_server_running():
            logger.info(f"Stopping llama.cpp server with PID: {self.process.pid}")
            self.process.terminate() # SIGTERM
            self.process.wait(timeout=5) # Wait for a few seconds
            if self.process.poll() is None: # If still running
                logger.warning(f"Llama.cpp server PID {self.process.pid} did not terminate gracefully. Killing...")
                self.process.kill() # SIGKILL
            self.process = None
            logger.info("Llama.cpp server stopped.")
        else:
            logger.info("Llama.cpp server not running or already stopped.")

    def is_server_running(self):
        if self.process:
            return self.process.poll() is None
        return False

# Example usage (for testing)
if __name__ == "__main__":
    # Ensure dummy binary and model exist for testing
    app_data_dir = Path(paths.get_app_data_dir())
    bin_dir = Path(paths.get_bin_dir())
    models_dir = Path(paths.get_models_dir())
    
    bin_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    dummy_binary_path = bin_dir / "llama_cpp_dummy_binary"
    dummy_model_path = models_dir / "dummy_model.gguf"

    if not dummy_binary_path.exists():
        with open(dummy_binary_path, "w") as f:
            f.write("#!/bin/bash\necho 'Dummy llama.cpp binary executed'\n")
        os.chmod(dummy_binary_path, 0o755)

    if not dummy_model_path.exists():
        with open(dummy_model_path, "w") as f:
            f.write("DUMMY_MODEL_CONTENT")

    # The actual llama.cpp server usually needs specific parameters
    # The dummy binary here won't actually start a server.
    # This is just for testing the subprocess management.
    
    llama_cpp = LlamaCppBinary(dummy_binary_path, dummy_model_path)
    
    print("\n--- Testing Llama.cpp Server Management ---")
    
    # Try starting
    print("Attempting to start server...")
    if llama_cpp.start_server(port=8080):
        print(f"Server process started. Running: {llama_cpp.is_server_running()}")
        time.sleep(1) # Give it a moment

        # Try stopping
        print("Attempting to stop server...")
        llama_cpp.stop_server()
        print(f"Server process running after stop: {llama_cpp.is_server_running()}")
    else:
        print("Failed to start server.")

    print("\n--- Test complete ---")
