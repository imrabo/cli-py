# Placeholder for security logic (token handling)
import secrets
from pathlib import Path

from imrabo.internal import paths

def generate_token(length: int = 32) -> str:
    return secrets.token_hex(length)

def save_token(token: str, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
    with open(path, "w") as f:
        f.write(token)
    print(f"Token saved to {path}")

def load_token(path: Path) -> str | None:
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

if __name__ == "__main__":
    test_token = generate_token()
    print(f"Generated token: {test_token}")
    token_file_path = Path(paths.get_runtime_token_file())
    save_token(test_token, token_file_path)
    loaded_token = load_token(token_file_path)
    print(f"Loaded token: {loaded_token}")
