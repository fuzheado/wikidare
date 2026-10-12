"""Pre-flight check for the configured embedding provider.

The embedder used to be hardcoded to OpenAI's ``text-embedding-3-large`` at 3072
dimensions. It is now configurable (see ``config/env.py``), which means three
things can disagree with each other:

1. ``EMBEDDING_DIMENSION`` -- what this deployment *says* the vectors are
2. the model's real output size -- what the provider *actually returns*
3. the dimensionality the existing Weaviate collection was *created with*

A mismatch between 1 and 2 fails every insert. A mismatch between 2 and 3 fails
every search, and does so at query time rather than at startup, which is the
worst place to discover it. This command checks them up front and exits non-zero
on any problem, so it can be used as a gate in a deployment script.

Run it whenever ``EMBEDDING_MODEL``, ``EMBEDDING_BASE_URL`` or
``EMBEDDING_DIMENSION`` changes, and **before the first ingest** -- a collection's
dimensionality is fixed by the first vector written to it, so a mistake here
means re-embedding a corpus rather than editing a setting.

    python manage.py check_embeddings
    python manage.py check_embeddings --skip-vector-store   # embedder only
"""

import sys

from django.core.management.base import BaseCommand

from config.env import EMBEDDING_API_KEY, EMBEDDING_BASE_URL, EMBEDDING_MODEL
from core.config.processing import VECTOR_DIMENSION

# Deliberately short and content-free: this is a dimension probe, not a
# retrieval-quality test, and it must be cheap enough to run on every deploy.
PROBE_TEXT = "wikidare embedding dimension probe"


class Command(BaseCommand):
    help = (
        "Verify that the configured embedding model, the configured dimension, "
        "the library catalogue and the vector store all agree."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-vector-store",
            action="store_true",
            help="Skip the Weaviate check (useful when the vector store is down).",
        )

    # -- helpers ------------------------------------------------------------

    def _fail(self, failures, message):
        self.stdout.write(self.style.ERROR(f"  FAIL  {message}"))
        failures.append(message)

    def _ok(self, message):
        self.stdout.write(self.style.SUCCESS(f"  ok    {message}"))

    def _note(self, message):
        self.stdout.write(f"  ..    {message}")

    def _stored_vector_dimension(self, collection):
        """Dimensionality of a vector already in the collection, or None.

        Measured from a real object rather than read from the schema: Weaviate
        does not declare a dimensionality for a ``vectorizer: none`` collection
        until it has seen a vector, and relying on a schema field that may or may
        not be exposed is how you get a check that silently passes.

        Note the defensive shape handling -- ``obj.vector`` is a dict keyed by
        vector name in weaviate-client 4.x but a plain list in some code paths,
        and the rest of this codebase hedges the same way.
        """
        response = collection.query.fetch_objects(limit=1, include_vector=True)
        if not response.objects:
            return None
        vector = response.objects[0].vector
        if isinstance(vector, dict):
            vector = vector.get("default")
        if not vector:
            return None
        return len(vector)

    # -- main ---------------------------------------------------------------

    def handle(self, *args, **options):
        failures = []

        self.stdout.write("\n=== embedding configuration ===")
        self.stdout.write(f"  EMBEDDING_MODEL      : {EMBEDDING_MODEL}")
        self.stdout.write(
            f"  EMBEDDING_BASE_URL   : {EMBEDDING_BASE_URL or '(SDK default = api.openai.com)'}"
        )
        # Never print the key itself, only where it came from. Diagnostically
        # that is the useful part anyway.
        if EMBEDDING_API_KEY:
            self.stdout.write("  EMBEDDING_API_KEY    : set (EMBEDDING_API_KEY)")
        else:
            self.stdout.write("  EMBEDDING_API_KEY    : unset (falling back to OPENAI_API_KEY)")
        self.stdout.write(f"  EMBEDDING_DIMENSION  : {VECTOR_DIMENSION}")
        self.stdout.write(
            "  note                 : EMBEDDING_API_KEY may be any non-empty value "
            "for a\n                         local server; the OpenAI SDK refuses to "
            "build a client\n                         without one, but it is never sent."
        )

        # ---- 1. does the provider return the dimension we claim? ----------
        self.stdout.write("\n=== embedder probe ===")
        probe_dimension = None
        try:
            from core.helpers.openai import OpenAIWrapper

            client = OpenAIWrapper()
            vector = client.create_embeddings(PROBE_TEXT)
            probe_dimension = len(vector)
            self._ok(
                f"{client.embedding_model} returned {probe_dimension} dimensions "
                f"(base_url={client.base_url or 'default'})"
            )
        except Exception as exc:  # noqa: BLE001 - report, do not traceback
            self._fail(failures, f"could not obtain an embedding: {exc}")

        if probe_dimension is not None:
            if probe_dimension == VECTOR_DIMENSION:
                self._ok(f"provider output matches EMBEDDING_DIMENSION ({VECTOR_DIMENSION})")
            else:
                self._fail(
                    failures,
                    f"DIMENSION MISMATCH: the model returns {probe_dimension} but "
                    f"EMBEDDING_DIMENSION is {VECTOR_DIMENSION}.\n"
                    f"         Either set EMBEDDING_DIMENSION={probe_dimension}, or "
                    f"point EMBEDDING_MODEL at a model that returns "
                    f"{VECTOR_DIMENSION}.\n"
                    f"         Note: EMBEDDING_MODEL is '{EMBEDDING_MODEL}' -- if you "
                    f"set EMBEDDING_BASE_URL,\n"
                    f"         confirm that endpoint is actually serving that model "
                    f"name.",
                )

            # ---- 2. does the library catalogue agree? ---------------------
            # Catalogue rows carry their own `dims` (a database field with a
            # default), so they can drift from configuration after a change.
            #
            # The model is resolved by LOOKING FOR THE FIELD, not by importing a
            # name. Upstream renamed this class (`SharedLibrary` at the base this
            # fork is pinned to, `Library` later), and importing the wrong name
            # raised ImportError -- which an earlier version of this file caught
            # and reported as a NOTE, so the check never ran while the summary
            # still said "all checks passed". A check that cannot run is a
            # FAILURE, not a note. Resolving by field also survives future
            # renames.
            self.stdout.write("\n=== library catalogue ===")
            try:
                from django.apps import apps as django_apps

                model = next(
                    (
                        m
                        for m in django_apps.get_models()
                        if m._meta.app_label == "libraries"
                        and any(f.name == "dims" for f in m._meta.get_fields())
                    ),
                    None,
                )
                if model is None:
                    self._fail(
                        failures,
                        "no model in the 'libraries' app carries a 'dims' field, so "
                        "the catalogue check could not run",
                    )
                else:
                    self._note(f"catalogue model: {model.__name__}")
                    mismatched = list(model.objects.exclude(dims=VECTOR_DIMENSION))
                    total = model.objects.count()
                    if not total:
                        self._ok(
                            "no catalogue entries yet -- nothing to reconcile"
                        )
                    elif mismatched:
                        for lib in mismatched:
                            ident = (
                                getattr(lib, "slug", None)
                                or getattr(lib, "name", None)
                                or lib.pk
                            )
                            self._fail(
                                failures,
                                f"catalogue entry '{ident}' records dims={lib.dims}, "
                                f"expected {VECTOR_DIMENSION} -- its corpus must be "
                                f"re-embedded",
                            )
                    else:
                        self._ok(
                            f"all {total} catalogue record(s) record "
                            f"dims={VECTOR_DIMENSION}"
                        )
            except Exception as exc:  # noqa: BLE001
                self._fail(
                    failures,
                    f"the library-catalogue check could not run: {exc}",
                )

        # ---- 3. does the vector store agree? ------------------------------
        if options["skip_vector_store"]:
            self.stdout.write("\n=== vector store ===\n  ..    skipped (--skip-vector-store)")
        else:
            self.stdout.write("\n=== vector store ===")
            try:
                from core.helpers.weaviate import WeaviateClient

                weaviate_client = WeaviateClient()
                try:
                    collection = weaviate_client.client.collections.get(
                        weaviate_client.collection_name
                    )
                    stored = self._stored_vector_dimension(collection)
                    if stored is None:
                        self._ok(
                            f"collection '{weaviate_client.collection_name}' is empty -- "
                            f"its dimensionality will be fixed by the first vector "
                            f"written ({VECTOR_DIMENSION})"
                        )
                    elif probe_dimension is None:
                        self._note(
                            f"collection '{weaviate_client.collection_name}' holds "
                            f"{stored}-dimensional vectors; cannot compare without a "
                            f"working embedder"
                        )
                    elif stored == probe_dimension:
                        self._ok(
                            f"collection '{weaviate_client.collection_name}' holds "
                            f"{stored}-dimensional vectors, matching the embedder"
                        )
                    else:
                        self._fail(
                            failures,
                            f"DIMENSION MISMATCH: collection "
                            f"'{weaviate_client.collection_name}' holds "
                            f"{stored}-dimensional vectors but the embedder returns "
                            f"{probe_dimension}.\n"
                            f"         Weaviate fixes a collection's dimensionality at "
                            f"creation, so this requires a new collection and a full "
                            f"re-embed -- changing EMBEDDING_DIMENSION alone is not "
                            f"enough.",
                        )
                finally:
                    weaviate_client.close()
            except Exception as exc:  # noqa: BLE001 - a down store is reported, not fatal
                self._note(f"could not inspect the vector store: {exc}")
                self._note(
                    "this is not counted as a failure -- the store may simply not be "
                    "running yet"
                )

        # ---- summary ------------------------------------------------------
        self.stdout.write("\n=== summary ===")
        if failures:
            self.stdout.write(
                self.style.ERROR(
                    f"  {len(failures)} problem(s) found. Do NOT ingest: a mismatch "
                    f"here means re-embedding the corpus later."
                )
            )
            for message in failures:
                self.stdout.write(self.style.ERROR(f"    - {message.splitlines()[0]}"))
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS("  all checks passed"))
