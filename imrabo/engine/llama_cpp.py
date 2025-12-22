import os
from typing import Iterator

# Make sure llama_cpp-python is installed as per Phase 1
from llama_cpp import Llama

from imrabo.engine.base import LLMEngine

class LlamaCppEngine(LLMEngine):
    def __init__(self):
        self.llm = None

    def load(self, model_path: str):
        if self.llm is not None:
            self.unload() # Ensure any previously loaded model is unloaded

        print(f"Loading Llama.cpp model from: {model_path}")
        try:
            n_ctx = int(os.environ.get("IMRABO_CTX", 4096))
            n_threads = int(os.environ.get("IMRABO_THREADS", os.cpu_count() - 1 if os.cpu_count() > 1 else 1))
            verbose = os.environ.get("IMRABO_VERBOSE", "False").lower() == "true"

            self.llm = Llama(
                model_path=str(model_path),
                n_ctx=n_ctx,
                n_threads=n_threads,
                verbose=verbose,
            )
            print("Llama.cpp model loaded successfully.")
        except Exception as e:
            print(f"Error loading Llama.cpp model: {e}")
            self.llm = None
            raise

    def generate(self, prompt: str) -> Iterator[str]:
        if self.llm is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Default parameters from the plan, can be made configurable later
        for chunk in self.llm(
            prompt,
            max_tokens=512,
            stream=True,
            temperature=0.7,
        ):
            # Check if 'choices' and 'text' exist in the chunk
            if "choices" in chunk and len(chunk["choices"]) > 0 and "text" in chunk["choices"][0]:
                yield chunk["choices"][0]["text"]
            else:
                # Handle cases where chunk might not contain expected data
                # For example, during stop tokens, it might just be {'content': ''}
                pass # Or log a warning

    def unload(self):
        if self.llm is not None:
            print("Unloading Llama.cpp model.")
            # Explicitly delete the Llama instance to free resources
            del self.llm
            self.llm = None