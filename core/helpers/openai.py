from typing import List, Optional
from openai import OpenAI
from core.enums import OpenAIModel
from config.env import (
    OPENAI_API_KEY,
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
)


class OpenAIWrapper:
    """Embedding client for any OpenAI-compatible /embeddings endpoint.

    The model, endpoint and key come from configuration rather than being
    compiled in, so a deployment can embed locally: wikidare points this at
    Ollama serving bge-m3 so that restricted corpora are never sent to a third
    party.

    This class previously hardcoded text-embedding-3-large against
    api.openai.com and configured the SDK's module-level client. Nothing else in
    the codebase used that module-level client, so it is now an explicit
    instance and the endpoint is configurable.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        resolved_key = api_key or EMBEDDING_API_KEY or OPENAI_API_KEY
        if not resolved_key:
            raise Exception(
                "No embedding API key available. Set EMBEDDING_API_KEY (or "
                "OPENAI_API_KEY) even when embedding locally: the OpenAI SDK "
                "refuses to construct a client without one."
            )

        resolved_base = base_url if base_url is not None else EMBEDDING_BASE_URL
        if resolved_base and not resolved_base.endswith("/"):
            # The SDK joins base_url with the request path, so a missing trailing
            # slash silently drops the path segment: "http://host/v1" would send
            # requests to "http://host/embeddings" instead of "/v1/embeddings".
            resolved_base += "/"

        self.embedding_model = (
            model or EMBEDDING_MODEL or OpenAIModel.TEXT_EMBEDDING_3_LARGE.value
        )
        self.base_url = resolved_base
        self._client = OpenAI(api_key=resolved_key, base_url=resolved_base)

    def create_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for given text using OpenAI's API."""
        try:
            response = self._client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"Error generating embedding: {str(e)}")
        
    def create_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in a single request"""
        try:
            response = self._client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise Exception(f"Error generating batch embeddings: {str(e)}")