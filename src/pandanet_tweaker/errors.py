class PandanetTweakerError(Exception):
    """Base project error."""


class ThemeImportError(PandanetTweakerError):
    """Raised when a theme package cannot be parsed."""


class ConfigurationError(PandanetTweakerError):
    """Raised when required project configuration is incomplete."""


class ExternalToolError(PandanetTweakerError):
    """Raised when an external tool invocation fails."""


class RepackError(PandanetTweakerError):
    """Raised when ASAR replacement cannot be completed."""


# Backward-compatible alias for any existing imports that still use the old name.
PandanetThemeReplacerError = PandanetTweakerError
