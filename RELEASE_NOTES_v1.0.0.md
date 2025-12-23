# `imrabo` v1.0.0 Release Notes

We are proud to announce the release of `imrabo` v1.0.0. This release marks a significant milestone, establishing `imrabo` as a stable, robust, and extensible local-first execution runtime designed for long-term reliability.

## Overview

`imrabo v1.0.0` is the culmination of a foundational architectural refactor, moving the project from an implicit monolithic structure towards an explicit, contract-driven, multi-process design. This release solidifies `imrabo`'s core principles: an invariant core, a stable CLI, and volatile edges (adapters and plugins) for innovation.

This is not merely a new version; it is the establishment of `imrabo` as a trustworthy platform upon which future capabilities will be built, ensuring stability for decades.

## Major Features & Changes

### 1. **Established Invariant Core (The Kernel)**

*   **New `imrabo/kernel/` Module:** Introduction of a dedicated `Kernel` module (`imrabo/kernel/execution.py`) that strictly orchestrates the execution lifecycle.
*   **Frozen Core Contracts:** Defined immutable data contracts (`ExecutionRequest`, `ExecutionResult`, `ArtifactHandle`, `EngineAdapter`, `ArtifactResolver`) in `imrabo/kernel/contracts.py`. These contracts form the stable API of `imrabo`'s core, ensuring predictability for all integrated components.
*   **Decoupled Logic:** The Kernel is now entirely agnostic to specific technologies like FastAPI or `llama.cpp`, interacting solely through abstract interfaces.

### 2. **Refactored Adapters**

*   **Explicit Adapter Pattern:** All interactions with external technologies are now encapsulated within replaceable Adapter modules, adhering to the Kernel's contracts.
*   **FastAPI Adapter (`imrabo/adapters/http/fastapi_server.py`):** The Daemon's HTTP API is now a thin FastAPI adapter, primarily responsible for request/response translation and authentication, delegating all core logic to the Kernel.
*   **`llama.cpp` Adapter (`imrabo/adapters/llama_cpp/process.py`):** The interaction with the external `llama-server.exe` process is now managed by a dedicated `LlamaCppProcessAdapter` that implements the `EngineAdapter` contract.
*   **Filesystem Storage Adapter (`imrabo/adapters/storage_fs.py`):** Model artifact downloading, integrity verification (SHA256), and local storage are handled by an `ArtifactResolver` implementation.
*   **Removal of Obsolete Modules:** The old `imrabo/runtime/` and `imrabo/engine/` directories, which contained tightly coupled logic, have been removed.

### 3. **Stable and Protocol-Oriented CLI**

*   **Frozen CLI Grammar:** The `imrabo` CLI (`imrabo/cli/`) is now treated as a stable protocol. Command names, arguments, and expected outputs are guaranteed to remain consistent, facilitating reliable scripting and automation.
*   **Decoupled Commands:** Individual CLI commands (`install`, `start`, `stop`, `run`, `status`, `doctor`) have been updated to interact with the Daemon strictly through the `RuntimeClient`, further enforcing the separation of concerns.
*   **Simplified `imrabo start`:** The `start` command no longer handles model selection, aligning with the Daemon's role as an orchestrator rather than a direct model loader.

### 4. **Comprehensive Documentation**

*   **MkDocs + Material Theme:** A complete documentation suite is now available, built using MkDocs and the Material theme.
*   **Architecture & Design Principles:** Detailed explanations of `imrabo`'s three-process model, core invariants, and design principles.
*   **Core Contracts Reference:** Explicit documentation for `ExecutionRequest`, `ExecutionResult`, and the Event Model.
*   **CLI Reference:** Authoritative documentation for every CLI command, including usage, examples, and failure modes.
*   **Plugin & Adapter Guides:** Conceptual documentation for extending `imrabo` with new plugins and adapters.
*   **Observability & Debugging:** Guides on how to use `imrabo`'s structured logging and events for diagnostics.
*   **Governance:** Clear policies on invariants, breaking changes, and deprecation.

### 5. **Robust Testing Strategy**

*   **Contract-Driven Testing:** Implementation of a comprehensive test suite (`tests/`) that follows a contract-driven, failure-first philosophy.
*   **Detailed Test Categories:** Exhaustive tests for Kernel contracts, lifecycle, and failure modes; CLI grammar and daemon interaction; Daemon lifecycle, concurrency, and crash recovery; Adapter robustness; and End-to-End scenarios (happy path, degraded, hostile environments).
*   **Backward Compatibility Tests:** Dedicated tests (`tests/backward-compatibility/`) to ensure core data contracts remain compatible across versions.
*   **Failure Injection Utilities:** Introduction of `tests/conftest.py` with fixtures to systematically inject failures and simulate hostile environments.

## Breaking Changes from `v0.x.x` (Pre-refactor state)

This `v1.0.0` release constitutes a **MAJOR** version bump, primarily due to the fundamental architectural shift and the re-establishment of core contracts. While a formal `v0.x.x` API was not explicitly defined, users of any pre-refactor `imrabo` code should be aware of the following:

*   **Module Restructuring:** Significant changes to the `imrabo/runtime/` and `imrabo/engine/` modules. Direct imports from these paths will no longer work.
*   **`imrabo start` CLI Signature:** The `imrabo start` command no longer accepts `--model-id` or `--variant-id` arguments.
*   **Daemon API Changes:** The underlying Daemon API, while still HTTP-based, has been adjusted to align with the new Kernel contracts and adapter architecture.

These changes were necessary to build a truly stable and extensible foundation for `imrabo`.

## Why `v1.0.0` Now?

The decision to release `v1.0.0` signifies that `imrabo`'s core architecture and fundamental contracts are now stable. We believe this release provides a predictable and reliable platform for developers to build upon, with clear boundaries for extension and a strong commitment to long-term compatibility for its core elements.

## Installation & Upgrade

### New Installation

If you are installing `imrabo` for the first time, please follow the [Installation Guide](https://imrabo.github.io/imrabo-cli-py/getting-started/installation/) in the documentation.

### Upgrading from Pre-`v1.0.0`

Given the significant architectural changes, a clean reinstallation is recommended:

1.  Deactivate and remove your old virtual environment.
2.  Follow the [Installation Guide](https://imrabo.github.io/imrabo-cli-py/getting-started/installation/) for `v1.0.0`.

## Future Outlook

`imrabo v1.0.0` lays the groundwork for a rich ecosystem of adapters and plugins. Future development will focus on expanding this ecosystem, enhancing observability, and refining performance, all while strictly adhering to the established core contracts.

We invite you to explore the new documentation, contribute to the project, and leverage `imrabo`'s stability for your local execution needs.

### Publishing to PyPI

Starting with `v1.0.0`, `imrabo` uses GitHub Actions with Trusted Publishing for PyPI deployments. This means that when a release is created and published on GitHub, the package will be automatically built and securely uploaded to PyPI. You do not need to manually run `twine upload`.
