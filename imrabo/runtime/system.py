# Placeholder for system detection logic
import platform
import psutil

def get_os_info():
    return platform.system()

def get_cpu_arch():
    return platform.machine()

def get_total_ram_gb():
    return round(psutil.virtual_memory().total / (1024**3), 2)

if __name__ == "__main__":
    print(f"OS: {get_os_info()}")
    print(f"Architecture: {get_cpu_arch()}")
    print(f"Total RAM: {get_total_ram_gb()} GB")
