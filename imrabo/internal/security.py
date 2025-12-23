# """
# Runtime security primitives.

# Responsibilities:
# - Generate a runtime authentication token (once)
# - Persist the token securely on disk
# - Load the token deterministically for CLI + runtime

# This module MUST be:
# - Side-effect free at import time
# - Deterministic
# - Local-only
# """

# from pathlib import Path
# import secrets
# from typing import Optional

# from imrabo.internal import paths
# from imrabo.internal.logging import get_logger

# logger = get_logger(__name__)

# # ---------------------------------------------------------------------
# # Constants
# # ---------------------------------------------------------------------

# TOKEN_BYTES = 32  # 256-bit token (hex-encoded => 64 chars)


# # ---------------------------------------------------------------------
# # Token generation
# # ---------------------------------------------------------------------

# def generate_token() -> str:
#     """
#     Generate a new cryptographically secure runtime token.

#     This MUST NOT be called implicitly by adapters.
#     Token generation is a lifecycle/bootstrap concern.
#     """
#     token = secrets.token_hex(TOKEN_BYTES)
#     logger.info("Generated new runtime token")
#     return token


# # ---------------------------------------------------------------------
# # Persistence
# # ---------------------------------------------------------------------

# def _get_token_file() -> Path:
#     """
#     Resolve the runtime token file path.
#     """
#     return Path(paths.get_runtime_token_file())


# def save_token(token: str) -> None:
#     """
#     Persist the runtime token to disk.

#     Overwrites any existing token.
#     """
#     token_file = _get_token_file()
#     token_file.parent.mkdir(parents=True, exist_ok=True)

#     token_file.write_text(token, encoding="utf-8")

#     logger.info(
#         "Runtime token saved",
#         path=str(token_file),
#     )


# # ---------------------------------------------------------------------
# # Loading
# # ---------------------------------------------------------------------

# def load_token() -> Optional[str]:
#     """
#     Load the persisted runtime token.

#     Returns:
#         token string if present
#         None if token file does not exist
#     """
#     token_file = _get_token_file()

#     if not token_file.exists():
#         logger.warning("Runtime token file not found", path=str(token_file))
#         return None

#     token = token_file.read_text(encoding="utf-8").strip()

#     if not token:
#         logger.error("Runtime token file is empty", path=str(token_file))
#         return None

#     return token


# # ---------------------------------------------------------------------
# # Bootstrap helper (explicit, optional)
# # ---------------------------------------------------------------------

# def ensure_token() -> str:
#     """
#     Ensure a runtime token exists.

#     This is the ONLY function allowed to generate a token automatically.
#     It should be called from:
#     - `imrabo doctor`
#     - `imrabo init`
#     - first-time install bootstrap

#     It MUST NOT be called implicitly by runtime adapters.
#     """
#     token = load_token()
#     if token:
#         return token

#     token = generate_token()
#     save_token(token)
#     return token


"""
Runtime security primitives.

Responsibilities:
- Generate a runtime authentication token (once)
- Persist the token securely on disk
- Load the token deterministically for CLI + runtime

This module MUST be:
- Side-effect free at import time
- Deterministic
- Local-only
"""

from pathlib import Path
import secrets
from typing import Optional

from imrabo.internal import paths
from imrabo.internal.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

# 256-bit token → 64 hex characters
TOKEN_BYTES = 32


# ---------------------------------------------------------------------
# Token generation (explicit only)
# ---------------------------------------------------------------------

def generate_token() -> str:
    """
    Generate a new cryptographically secure runtime token.

    IMPORTANT:
    - MUST NOT be called implicitly by adapters
    - Token generation is a lifecycle/bootstrap concern
    """
    token = secrets.token_hex(TOKEN_BYTES)
    logger.info("Generated new runtime token")
    return token


# ---------------------------------------------------------------------
# Token file resolution
# ---------------------------------------------------------------------

def _get_token_file() -> Path:
    """
    Resolve the runtime token file path.

    This path is controlled centrally via `imrabo.internal.paths`
    to guarantee CLI + runtime consistency.
    """
    return Path(paths.get_runtime_token_file())


# ---------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------

def save_token(token: str) -> None:
    """
    Persist the runtime token to disk.

    Overwrites any existing token.
    """
    token_file = _get_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)

    token_file.write_text(token, encoding="utf-8")

    logger.info(
        "Runtime token saved",
        path=str(token_file),
    )


# ---------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------

def load_token() -> Optional[str]:
    """
    Load the persisted runtime token.

    Returns:
        token (str) if present and valid
        None if token file does not exist or is invalid
    """
    token_file = _get_token_file()

    if not token_file.exists():
        logger.warning(
            "Runtime token file not found",
            path=str(token_file),
        )
        return None

    token = token_file.read_text(encoding="utf-8").strip()

    if not token:
        logger.error(
            "Runtime token file is empty or invalid",
            path=str(token_file),
        )
        return None

    return token


# ---------------------------------------------------------------------
# Bootstrap helper (explicit, controlled)
# ---------------------------------------------------------------------

def ensure_token() -> str:
    """
    Ensure a runtime token exists.

    This is the ONLY function allowed to automatically generate a token.

    Intended call sites:
    - `imrabo doctor`
    - `imrabo init`
    - first-time install/bootstrap flows

    MUST NOT be called implicitly by:
    - runtime adapters
    - HTTP servers
    - background daemons
    """
    token = load_token()
    if token:
        return token

    token = generate_token()
    save_token(token)
    return token
