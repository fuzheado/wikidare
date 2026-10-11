from django.db import models
from django.utils.translation import gettext_lazy as _

from config.env import EMBEDDING_DIMENSION, EMBEDDING_MODEL

# The query embedder and dimensionality a library must match to be searchable.
# Both come from configuration so that a self-hosted embedder is a deployment
# choice rather than a code change; see config/env.py.
DEFAULT_EMBEDDING_MODEL = EMBEDDING_MODEL
DEFAULT_VECTOR_DIMENSION = EMBEDDING_DIMENSION


class VectorBackend(models.TextChoices):
    """Vector store that physically hosts a shared-library corpus.

    Independent of a user's own ``VectorDBChoice`` preference — a library is
    queried against whichever backend it declares here.
    """

    WEAVIATE = "weaviate", _("Weaviate")
    PINECONE = "pinecone", _("Pinecone")
