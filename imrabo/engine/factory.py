from imrabo.engine.base import LLMEngine
from imrabo.engine.llama_binary import LlamaBinaryEngine
from imrabo.engine.llama_cpp import LlamaCppEngine # Still need to import for now, even if deprecated
from pathlib import Path # Import Path

class EngineFactory:
    @staticmethod
    def create(engine_type: str, model_path: Path) -> LLMEngine: # Add model_path
        if engine_type == "llama_binary":
            return LlamaBinaryEngine(model_path=model_path) # Pass model_path
        elif engine_type == "llama_cpp":
            return LlamaCppEngine()
        else:
            raise ValueError(f"Unknown engine type: {engine_type}")
