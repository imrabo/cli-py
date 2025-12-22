from abc import ABC, abstractmethod

class LLMEngine(ABC):
    @abstractmethod
    def load(self) -> None:
        """
        Loads the language model.
        """
        pass

    @abstractmethod
    def infer(self, prompt: str, stream_cb=None) -> None:
        """
        Generates text based on the prompt, streaming tokens.
        """
        pass

    @abstractmethod
    def unload(self) -> None:
        """
        Unloads the language model to free up resources.
        """
        pass

    @abstractmethod
    def health(self) -> dict:
        """
        Returns the health status of the engine.
        """
        pass
