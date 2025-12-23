# IMRABO CLI Contract v1

This document specifies the official, versioned contract for the `imrabo` command-line interface. All behavior described herein is considered stable and can be relied upon by users and external tooling.

**Version:** 1.0
**Date:** 2025-12-23

---

## 1. Guiding Principles

- **Stability Over Features:** This contract prioritizes a stable, predictable CLI over the rapid addition of new top-level commands or flag behaviors.
- **No Breaking Changes:** Command names, their arguments, and their output formats will not change in a backward-incompatible way within a major version.
- **Extensibility via Subcommands:** New functionality will be added through new subcommands, not by altering existing ones.
- **CLI as a Protocol:** The CLI is the user-facing protocol for interacting with the IMRABO runtime. It should not contain complex business logic, which belongs in the kernel.

---

## 2. Global Flags

These flags are available for all commands.

- `--help`: Show help message and exit.

---

## 3. Command Grammar

### 3.1 `imrabo start`

- **Purpose:** Starts the IMRABO runtime daemon as a background process.
- **Arguments:** None.
- **Behavior:**
    - Checks if the runtime is already active. If so, reports it and exits.
    - If not, it spawns the daemon process.
    - It waits for a confirmation that the daemon's API is healthy before exiting.
    - Exits with a status code of `0` on success and `1` on failure.
- **Output:**
    - On success: "imrabo runtime started successfully."
    - If already running: "imrabo runtime is already running."
    - On failure: "Error: Failed to start imrabo runtime."

### 3.2 `imrabo stop`

- **Purpose:** Stops the IMRABO runtime daemon.
- **Arguments:** None.
- **Behavior:**
    - Attempts a graceful shutdown by calling the daemon's shutdown API.
    - If the API is unreachable or fails, it falls back to terminating the process via its saved PID.
    - Exits with `0` on success, `1` on failure.
- **Output:**
    - On success: "imrabo runtime stopped successfully."
    - On failure: "Error: Failed to stop imrabo runtime."

### 3.3 `imrabo status`

- **Purpose:** Checks the status of the runtime daemon and the loaded model.
- **Arguments:** None.
- **Behavior:**
    - Contacts the daemon's `/status` endpoint.
    - Displays the runtime status, PID, and information about the currently loaded model engine.
- **Output:** A formatted table or JSON object containing status information.

### 3.4 `imrabo run <prompt>`

- **Purpose:** Executes a prompt against the currently configured model in the runtime.
- **Arguments:**
    - `prompt`: (Required) The text prompt to execute.
- **Behavior:**
    - Sends the prompt to the daemon's `/run` endpoint.
    - Streams the token-based response from the server and prints it to standard output in real-time.
- **Output:** A stream of text tokens.

### 3.5 `imrabo install`

- **Purpose:** Downloads and installs a new model from the official registry.
- **Arguments:** None (interactive).
- **Behavior:**
    - Prompts the user to select a model and variant from the available registry.
    - Downloads the model files, verifies their checksums, and places them in the local model store.
- **Output:** Interactive prompts and progress indicators.

### 3.6 `imrabo version`

- **Purpose:** Displays the version of the IMRABO CLI.
- **Arguments:** None.
- **Output:** The version string (e.g., "imrabo version 1.0.0").

### 3.7 `imrabo doctor`

- **Purpose:** Runs a series of checks to diagnose potential problems with the installation.
- **Arguments:** None.
- **Output:** A series of check descriptions and their pass/fail status.
