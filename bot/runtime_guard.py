"""Keep the retired Python process from taking over the serverless webhook."""
import os


def assert_legacy_runtime_allowed(environ=None):
    settings = os.environ if environ is None else environ
    if settings.get('SU_TECH_ENABLE_LEGACY_BOT') != '1':
        raise RuntimeError(
            'Su-Tech now runs on Telegram Serverless. The Python receiver is '
            'retired and must not overwrite its webhook. See serverless/README.md.'
        )
