"""
Package that provides various cloud providers.

All implementing the BaseProvider interface.
"""

import pulumi

from providers import aws, base

UNKNOWN_PROVIDER = "Unknown provider {name!r}, must be one of: {known}."

_PROVIDERS: dict[str, type[base.BaseProvider]] = {
    aws.AWSProvider.provider_name: aws.AWSProvider,
}


def get_provider() -> base.BaseProvider:
    """Instantiate the provider selected by the `provider` configuration key."""
    name = pulumi.Config().require("provider")
    try:
        provider_class = _PROVIDERS[name]
    except KeyError:
        message = UNKNOWN_PROVIDER.format(name=name, known=", ".join(sorted(_PROVIDERS)))
        raise ValueError(message) from None

    return provider_class()
