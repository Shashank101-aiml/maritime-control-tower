from typing import List, Optional

try:
    import openai
except ImportError:  # pragma: no cover
    openai = None


class Embeddings:
    def __init__(
        self,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.model = model

        if self.provider == "openai":
            if openai is None:
                raise ImportError(
                    "openai package is required for OpenAI embeddings. "
                    "Install with `pip install openai`."
                )
            if api_key:
                openai.api_key = api_key

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if self.provider == "openai":
            response = openai.Embedding.create(model=self.model, input=texts)
            return [item["embedding"] for item in response["data"]]

        raise NotImplementedError(f"Embedding provider '{self.provider}' is not supported")

    def embed_query(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]