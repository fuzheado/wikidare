from django.db import migrations

# Rate card from DeepSeek's official pricing page:
#   https://api-docs.deepseek.com/quick_start/pricing
#
# DeepSeek V4.1 Flash (API model id ``deepseek-flash``) is a cheap multimodal
# model -- 1M context, vision, tool calling -- and is this deployment's
# generation model.
#
# It is reached through the CUSTOM provider rather than a built-in one, because
# the endpoint is OpenAI-compatible rather than one of the SDKs DARE ships
# support for. ``base_url`` is what makes that work, and the LLM model's own help
# text says base_url is "required for CUSTOM provider".
#
# PEAK / OFF-PEAK CAVEAT -- read before trusting a cost figure.
# DeepSeek bills by time of day: off-peak is half price, and peak is 01:00-04:00
# and 06:00-10:00 UTC on weekdays (weekends and Chinese public holidays are
# entirely off-peak). A single per-model rate cannot express that schedule, so the
# OFF-PEAK rates are recorded here. Recorded cost will therefore be EXACT outside
# peak windows and UNDERSTATE the real bill by up to 2x during them.
#
# No API key is created here, deliberately. ProviderAPIKey stores an encrypted
# key and is edited in the Django admin, so the credential never passes through a
# migration, a repository, or an agent's transcript.
DEEPSEEK_FLASH = {
    "name": "DeepSeek V4.1 Flash",
    "identifier": "deepseek-flash",
    "provider": "custom",
    "base_url": "https://api.deepseek.com",
    "description": (
        "DeepSeek's fast multimodal model (1M context, vision, tool calling), "
        "reached over an OpenAI-compatible endpoint."
    ),
    "tier": "flash",
    # V4.1 Flash supports both non-thinking and thinking modes and defaults to
    # thinking. Marked non-reasoning so dispatch takes the plain chat path first;
    # flip to True to use thinking mode.
    "is_reasoning": False,
    "supports_vision": True,
    "supports_temperature": True,
    "supports_effort": False,
    "input_token_rate_per_million": "0.15",
    "output_token_rate_per_million": "0.60",
    "cached_input_token_rate_per_million": "0.003",
}


def seed_deepseek_flash(apps, schema_editor):
    LLM = apps.get_model("conversations", "LLM")

    _, created = LLM.objects.get_or_create(
        identifier=DEEPSEEK_FLASH["identifier"],
        defaults={
            key: value for key, value in DEEPSEEK_FLASH.items() if key != "identifier"
        },
    )

    if not created:
        # Keep rates current if the row already exists, without touching
        # operator-editable fields such as base_url, description or is_active.
        LLM.objects.filter(identifier=DEEPSEEK_FLASH["identifier"]).update(
            input_token_rate_per_million=DEEPSEEK_FLASH[
                "input_token_rate_per_million"
            ],
            output_token_rate_per_million=DEEPSEEK_FLASH[
                "output_token_rate_per_million"
            ],
            cached_input_token_rate_per_million=DEEPSEEK_FLASH[
                "cached_input_token_rate_per_million"
            ],
        )


def reverse_seed_deepseek_flash(apps, schema_editor):
    LLM = apps.get_model("conversations", "LLM")
    LLM.objects.filter(identifier=DEEPSEEK_FLASH["identifier"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("conversations", "0101_ensemble_preset"),
    ]

    operations = [
        migrations.RunPython(seed_deepseek_flash, reverse_seed_deepseek_flash),
    ]
