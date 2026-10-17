import os


def _flag(name, default=False):
    return os.getenv(name, "true" if default else "false").strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(float(raw))
    except ValueError:
        return default


class Settings:
    def __init__(self):
        self.sieve_limit = _int("SIEVE_LIMIT", 1000000)
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "primecheck")
        self.otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        self.tracing_enabled = _flag("TRACING_ENABLED", False)
        self.feature_factor_hint = _flag("FEATURE_FACTOR_HINT", False)
        self.admin_token = os.getenv("ADMIN_TOKEN", "")

    @property
    def max_n(self):
        return self.sieve_limit * self.sieve_limit


settings = Settings()
