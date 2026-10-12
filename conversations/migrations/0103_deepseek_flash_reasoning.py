"""Declare DeepSeek V4.1 Flash a reasoning model that supports adaptive thinking.

WHY THIS EXISTS -- it corrects a mistake in 0102.

0102 seeded this model with ``is_reasoning=False``, reasoning that a non-reasoning
flag would "take the plain chat path". That was wrong, and it produced a
user-visible failure for the first logged-in user: the model is a reasoning model,
so it spends tokens thinking before answering. With the flag wrong the request hit a
token ceiling (2048 by default) before any answer text existed, and the app reported

    "I couldn't generate a response for that request. Your request is saved
     -- please retry it."

which names no cause, while still displaying a cost for the truncated attempt.

TWO SEPARATE FLAGS, and the second is the one that actually fixes the ceiling:

1. ``is_reasoning`` -- not cosmetic. In ``core/services/custom_llm_service.py``,
   the service the ``custom`` provider uses to reach this model, it selects which
   parameter carries the ceiling:

       if self.is_reasoning:
           params["max_completion_tokens"] = max_tokens    # current OpenAI dialect
       else:
           params["max_tokens"] = max_tokens

   Reasoning models take ``max_completion_tokens``; sending the legacy name is not
   correct.

2. ``supports_adaptive_thinking`` (+ ``default_adaptive_thinking_enabled``) -- the
   frontend grants its larger budget only to models flagged here:

       const usesAdaptiveThinking = selectedEntry?.supportsAdaptiveThinking ?? false
       const defaultMaxTokens = usesAdaptiveThinking
         ? MODEL_CONFIG.adaptiveThinkingMaxTokens    // 32768
         : MODEL_CONFIG.maxTokens                    // 4096

   So setting ``is_reasoning`` alone would still have left every user truncating at
   4096. Both are set, and the default-enabled flag means nobody has to toggle it.

``reasoning_level`` is "cost_unconstrained" because it is honest: the model chooses
its own reasoning depth, so a simple prompt can still consume many tokens.
"cost_predictable" would misdescribe it.

The ceiling itself remains a separate knob (``Conversation.max_tokens`` and the
per-message value the client sends); this migration deliberately does not touch it.
"""

from django.db import migrations

IDENTIFIER = "deepseek-flash"

# Forward values.
FORWARD = {
    "is_reasoning": True,
    "reasoning_level": "cost_unconstrained",
    "supports_adaptive_thinking": True,
    "default_adaptive_thinking_enabled": True,
}

# Values 0102 left behind, restored on reverse.
REVERSE = {
    "is_reasoning": False,
    "reasoning_level": "none",
    "supports_adaptive_thinking": False,
    "default_adaptive_thinking_enabled": False,
}


def _apply(apps, values):
    LLM = apps.get_model("conversations", "LLM")
    qs = LLM.objects.filter(identifier=IDENTIFIER)

    # Assert this is exactly the row intended. A data migration that silently
    # matches nothing is indistinguishable from success -- the same class of bug as
    # a rename matching no occurrences. Refuse to guess.
    count = qs.count()
    if count != 1:
        raise RuntimeError(
            f"expected exactly 1 LLM row with identifier={IDENTIFIER!r}, found {count}. "
            "Check the identifier in 0102_seed_deepseek_flash before proceeding."
        )

    qs.update(**values)


def forwards(apps, schema_editor):
    _apply(apps, FORWARD)


def backwards(apps, schema_editor):
    _apply(apps, REVERSE)


class Migration(migrations.Migration):
    dependencies = [
        ("conversations", "0102_seed_deepseek_flash"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
