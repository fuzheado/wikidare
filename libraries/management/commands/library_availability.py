"""Inspect and set availability for shared library catalogue entries.

A ``SharedLibrary`` row is a catalogue entry describing a corpus that lives in a
vector store. Availability is a real field rather than a flag nobody touches, for
two reasons:

* a library's declared dimensionality must match **this** deployment's query
  embedder, or search against it cannot work. ``manage.py check_embeddings``
  fails its gate on an *available* entry that does not match.
* upstream seeds catalogue entries for corpora hosted elsewhere — CMU's external
  Weaviate, embedded with ``text-embedding-3-large`` — which a deployment using
  local embeddings cannot serve.

Marking such an entry unavailable removes it from the catalogue without deleting
the record or pretending the corpus exists here. That is exactly what the field's
own help text means: *"False for 'coming soon' catalog entries."*

    python manage.py library_availability --list
    python manage.py library_availability --unavailable civil-war-pensions
    python manage.py library_availability --available civil-war-pensions
    python manage.py library_availability --unavailable a b c --dry-run

Exit status is non-zero when a requested slug does not exist, so this is usable
as a deployment step.
"""

import sys

from django.core.management.base import BaseCommand, CommandError

from core.config.processing import VECTOR_DIMENSION


class Command(BaseCommand):
    help = (
        "List shared library catalogue entries and set their availability. "
        "Use --unavailable for corpora this deployment does not host."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--list",
            action="store_true",
            help="Show every catalogue entry with its dimension and availability.",
        )
        parser.add_argument(
            "--unavailable",
            nargs="+",
            metavar="SLUG",
            help="Mark these catalogue entries unavailable (removed from the catalogue).",
        )
        parser.add_argument(
            "--available",
            nargs="+",
            metavar="SLUG",
            help="Mark these catalogue entries available again.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    # -- helpers ------------------------------------------------------------

    def _model(self):
        """The catalogue model, found by FIELD rather than by name.

        Upstream renamed this class (``SharedLibrary`` at the base this fork is
        pinned to, ``Library`` later), and importing a fixed name broke the
        dimension gate once already. Looking for the field cannot be broken by a
        rename.
        """
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
            raise CommandError(
                "no model in the 'libraries' app carries a 'dims' field"
            )
        return model

    def _describe(self, entry):
        matches = "yes" if entry.dims == VECTOR_DIMENSION else "NO"
        return (
            f"{entry.slug:<24} {'available' if entry.is_available else 'unavailable':<12} "
            f"dims={str(entry.dims):<6} model={(entry.embedding_model or '(unset)'):<24} "
            f"matches_query_embedder={matches}"
        )

    # -- main ---------------------------------------------------------------

    def handle(self, *args, **options):
        model = self._model()
        entries = list(model.objects.order_by("slug"))

        if not entries:
            self.stdout.write("no catalogue entries exist")
            return

        if options["list"] or not (options["unavailable"] or options["available"]):
            self.stdout.write(f"\n=== catalogue ({len(entries)} entries) ===")
            self.stdout.write(f"this deployment's query embedder produces {VECTOR_DIMENSION} dims\n")
            for entry in entries:
                self.stdout.write("  " + self._describe(entry))
            mismatched = [e for e in entries if e.is_available and e.dims != VECTOR_DIMENSION]
            if mismatched:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n  {len(mismatched)} AVAILABLE entry(ies) do not match this "
                        f"deployment's embedder.\n"
                        f"  'manage.py check_embeddings' fails while that is true, because\n"
                        f"  selecting one would produce a search that cannot work.\n"
                        f"  Fix by marking them unavailable (they are not hosted here), or\n"
                        f"  by importing them with the configured embedder."
                    )
                )
            if not (options["unavailable"] or options["available"]):
                return

        failures = []
        for slug_list, target in (
            (options["unavailable"], False),
            (options["available"], True),
        ):
            if not slug_list:
                continue
            verb = "available" if target else "unavailable"
            for slug in slug_list:
                matches = [e for e in entries if e.slug == slug]
                if not matches:
                    self.stdout.write(
                        self.style.ERROR(f"  FAIL  no catalogue entry with slug '{slug}'")
                    )
                    failures.append(slug)
                    continue
                entry = matches[0]
                if entry.is_available == target:
                    self.stdout.write(f"  ok    '{slug}' is already {verb}")
                    continue
                if options["dry_run"]:
                    self.stdout.write(f"  DRY   would mark '{slug}' {verb}")
                    continue
                entry.is_available = target
                entry.save(update_fields=["is_available", "updated_at"] if
                           any(f.name == "updated_at" for f in entry._meta.get_fields())
                           else ["is_available"])
                self.stdout.write(self.style.SUCCESS(f"  ok    '{slug}' marked {verb}"))
                if target and entry.dims != VECTOR_DIMENSION:
                    self.stdout.write(
                        self.style.WARNING(
                            f"        NOTE '{slug}' records dims={entry.dims} but this "
                            f"deployment embeds {VECTOR_DIMENSION}.\n"
                            f"        'check_embeddings' will now FAIL until that is "
                            f"resolved."
                        )
                    )

        if failures:
            self.stdout.write(
                self.style.ERROR(
                    f"\n{len(failures)} requested slug(s) did not exist: "
                    f"{' '.join(failures)}"
                )
            )
            sys.exit(1)
