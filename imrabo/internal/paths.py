# # Placeholder for path management
# import os

# def get_app_data_dir() -> str:
#     """
#     Returns the appropriate application data directory based on OS.
#     e.g., ~/.imrabo for Linux/macOS, %APPDATA%/imrabo for Windows.
#     """
#     if os.name == 'posix': # Linux, macOS
#         return os.path.join(os.path.expanduser("~"), ".imrabo")
#     elif os.name == 'nt': # Windows
#         return os.path.join(os.environ.get('APPDATA', os.path.expanduser("~")), "imrabo")
#     else:
#         return os.path.join(os.path.expanduser("~"), ".imrabo")

# def get_bin_dir() -> str:
#     return os.path.join(get_app_data_dir(), "bin")

# def get_models_dir() -> str:
#     return os.path.join(get_app_data_dir(), "models")

# def get_runtime_pid_file() -> str:
#     return os.path.join(get_app_data_dir(), "runtime.pid")

# def get_runtime_token_file() -> str:
#     return os.path.join(get_app_data_dir(), "runtime.token")

# def get_llama_binary_dir() -> str:
#     """
#     Returns the directory where the llama.cpp binary should be stored.
#     """
#     return os.path.join(get_app_data_dir(), "engine", "llama")

# def get_llama_server_binary_path() -> str:
#     """
#     Returns the full path to the llama-server.exe binary.
#     """
#     return os.path.join(get_llama_binary_dir(), "llama-server.exe")

# def get_model_registry_path() -> str:
#     from imrabo.internal.constants import MODEL_REGISTRY_FILE_NAME
#     return os.path.join(get_models_dir(), MODEL_REGISTRY_FILE_NAME)

# if __name__ == "__main__":
#     print(f"App Data Dir: {get_app_data_dir()}")
#     print(f"Bin Dir: {get_bin_dir()}")
#     print(f"Models Dir: {get_models_dir()}")
#     print(f"Runtime PID File: {get_runtime_pid_file()}")
#     print(f"Runtime Token File: {get_runtime_token_file()}")


import os
from pathlib import Path


# ---------------------------------------------------------------------
# Base directories
# ---------------------------------------------------------------------

def get_app_data_dir() -> Path:
    """
    Returns the application data directory.

    - Windows: %APPDATA%\\imrabo
    - Linux/macOS: ~/.imrabo
    """
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA", str(Path.home()))
        path = Path(base) / "imrabo"
    else:  # Linux / macOS
        path = Path.home() / ".imrabo"

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_bin_dir() -> Path:
    path = get_app_data_dir() / "bin"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_models_dir() -> Path:
    path = get_app_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------
# Runtime files
# ---------------------------------------------------------------------

def get_runtime_pid_file() -> Path:
    return get_app_data_dir() / "runtime.pid"


def get_runtime_token_file() -> Path:
    return get_app_data_dir() / "runtime.token"


# ---------------------------------------------------------------------
# Llama.cpp engine paths
# ---------------------------------------------------------------------

def get_llama_binary_dir() -> Path:
    """
    Directory where llama.cpp binaries are stored.
    """
    path = get_app_data_dir() / "engine" / "llama"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_llama_server_binary_path() -> Path:
    """
    Full path to llama-server executable.
    """
    return get_llama_binary_dir() / "llama-server.exe"


def get_llama_log_file() -> Path:
    """
    Log file for llama-server stderr/stdout.
    """
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "llama-server.log"


# ---------------------------------------------------------------------
# Registry / metadata
# ---------------------------------------------------------------------

def get_model_registry_path() -> Path:
    from imrabo.internal.constants import MODEL_REGISTRY_FILE_NAME
    return get_models_dir() / MODEL_REGISTRY_FILE_NAME


# ---------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------

if __name__ == "__main__":
    print("App Data Dir:", get_app_data_dir())
    print("Bin Dir:", get_bin_dir())
    print("Models Dir:", get_models_dir())
    print("Runtime PID File:", get_runtime_pid_file())
    print("Runtime Token File:", get_runtime_token_file())
    print("Llama Binary Dir:", get_llama_binary_dir())
    print("Llama Server Path:", get_llama_server_binary_path())
    print("Llama Log File:", get_llama_log_file())
