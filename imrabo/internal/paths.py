# Placeholder for path management
import os

def get_app_data_dir() -> str:
    """
    Returns the appropriate application data directory based on OS.
    e.g., ~/.imrabo for Linux/macOS, %APPDATA%/imrabo for Windows.
    """
    if os.name == 'posix': # Linux, macOS
        return os.path.join(os.path.expanduser("~"), ".imrabo")
    elif os.name == 'nt': # Windows
        return os.path.join(os.environ.get('APPDATA', os.path.expanduser("~")), "imrabo")
    else:
        return os.path.join(os.path.expanduser("~"), ".imrabo")

def get_bin_dir() -> str:
    return os.path.join(get_app_data_dir(), "bin")

def get_models_dir() -> str:
    return os.path.join(get_app_data_dir(), "models")

def get_runtime_pid_file() -> str:
    return os.path.join(get_app_data_dir(), "runtime.pid")

def get_runtime_token_file() -> str:
    return os.path.join(get_app_data_dir(), "runtime.token")


if __name__ == "__main__":
    print(f"App Data Dir: {get_app_data_dir()}")
    print(f"Bin Dir: {get_bin_dir()}")
    print(f"Models Dir: {get_models_dir()}")
    print(f"Runtime PID File: {get_runtime_pid_file()}")
    print(f"Runtime Token File: {get_runtime_token_file()}")
