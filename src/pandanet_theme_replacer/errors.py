class PandanetThemeReplacerError(Exception):
    """Base project error."""


class ThemeImportError(PandanetThemeReplacerError):
    """Raised when a theme package cannot be parsed."""


class ConfigurationError(PandanetThemeReplacerError):
    """Raised when required project configuration is incomplete."""


class ExternalToolError(PandanetThemeReplacerError):
    """Raised when an external tool invocation fails."""


class RepackError(PandanetThemeReplacerError):
    """Raised when ASAR replacement cannot be completed."""
