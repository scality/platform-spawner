"""
Flavor abstraction layer for multi-provider support.

This module provides mappings from abstract flavor names to provider-specific
instance types, organised by performance tier and size.

Tiers
-----
dev-*   Shared vCPUs, cost-optimised — dev, CI, bastion hosts.
        SCW: BASIC3   |  AWS: t3 (burstable)

std-*   Dedicated vCPUs, balanced compute/memory — general production.
        SCW: STANDARD3  |  AWS: m6i (general purpose)

cpu-*   Dedicated vCPUs, compute-optimised — CPU-intensive workloads.
        SCW: COMPUTE3   |  AWS: c6i (compute optimised)

Sizes within each tier: xs < s < m < l < xl < 2xl (< 3xl < 4xl for cpu).
"""

from typing import Dict
from core.models import Provider


# Flavor mappings per provider
FLAVOR_MAP: Dict[str, Dict[str, str]] = {
    "scaleway": {
        # dev tier — BASIC3, shared vCPUs (development / CI / bastions)
        "dev-xs": "BASIC3-X2C-4G",    # 2 vCPU shared,  4 GB, 350 Mbps
        "dev-s":  "BASIC3-X4C-8G",    # 4 vCPU shared,  8 GB, 700 Mbps
        "dev-m":  "BASIC3-X4C-16G",   # 4 vCPU shared, 16 GB, 700 Mbps
        "dev-l":  "BASIC3-X8C-32G",   # 8 vCPU shared, 32 GB, 1.5 Gbps

        # std tier — STANDARD3, dedicated vCPUs (balanced production)
        "std-xs":  "STANDARD3-X2C-8G",    # 2 vCPU,  8 GB,  500 Mbps
        "std-s":   "STANDARD3-X4C-16G",   # 4 vCPU, 16 GB,   1 Gbps
        "std-m":   "STANDARD3-X8C-32G",   # 8 vCPU, 32 GB,   2 Gbps
        "std-l":   "STANDARD3-X16C-64G",  # 16 vCPU, 64 GB,  4 Gbps
        "std-xl":  "STANDARD3-X32C-128G", # 32 vCPU, 128 GB, 8 Gbps
        "std-2xl": "STANDARD3-X48C-192G", # 48 vCPU, 192 GB, 16 Gbps

        # cpu tier — COMPUTE3, dedicated vCPUs (compute-optimised)
        "cpu-s":   "COMPUTE3-X4C-8G",    # 4 vCPU,  8 GB,   1 Gbps
        "cpu-m":   "COMPUTE3-X8C-16G",   # 8 vCPU, 16 GB,   2 Gbps
        "cpu-l":   "COMPUTE3-X16C-32G",  # 16 vCPU, 32 GB,  4 Gbps
        "cpu-xl":  "COMPUTE3-X32C-64G",  # 32 vCPU, 64 GB,  8 Gbps
        "cpu-2xl": "COMPUTE3-X48C-96G",  # 48 vCPU, 96 GB,  16 Gbps
        "cpu-3xl": "COMPUTE3-X64C-128G", # 64 vCPU, 128 GB, 16 Gbps
        "cpu-4xl": "COMPUTE3-X96C-192G", # 96 vCPU, 192 GB, 16 Gbps
    },
    "aws": {
        # dev tier — t3 burstable (development / CI / bastions)
        "dev-xs": "t3.medium",   # 2 vCPU,  4 GB
        "dev-s":  "t3.large",    # 2 vCPU,  8 GB
        "dev-m":  "t3.xlarge",   # 4 vCPU, 16 GB
        "dev-l":  "t3.2xlarge",  # 8 vCPU, 32 GB

        # std tier — m6i general purpose (balanced production)
        "std-xs":  "m6i.large",    # 2 vCPU,   8 GB
        "std-s":   "m6i.xlarge",   # 4 vCPU,  16 GB
        "std-m":   "m6i.2xlarge",  # 8 vCPU,  32 GB
        "std-l":   "m6i.4xlarge",  # 16 vCPU, 64 GB
        "std-xl":  "m6i.8xlarge",  # 32 vCPU, 128 GB
        "std-2xl": "m6i.12xlarge", # 48 vCPU, 192 GB

        # cpu tier — c6i compute optimised
        "cpu-s":   "c6i.xlarge",   # 4 vCPU,  8 GB
        "cpu-m":   "c6i.2xlarge",  # 8 vCPU, 16 GB
        "cpu-l":   "c6i.4xlarge",  # 16 vCPU, 32 GB
        "cpu-xl":  "c6i.8xlarge",  # 32 vCPU, 64 GB
        "cpu-2xl": "c6i.12xlarge", # 48 vCPU, 96 GB
        "cpu-3xl": "c6i.16xlarge", # 64 vCPU, 128 GB
        "cpu-4xl": "c6i.24xlarge", # 96 vCPU, 192 GB
    },
}


def get_instance_type(provider: Provider, flavor: str) -> str:
    """
    Get the provider-specific instance type for a given flavor.

    If the flavor is not recognized as an abstract flavor, it is returned
    as-is, allowing users to specify exact instance types if needed.

    Args:
        provider: Cloud provider
        flavor: Abstract flavor name (small, medium, large) or exact instance type

    Returns:
        Provider-specific instance type

    Examples:
        >>> get_instance_type(Provider.SCALEWAY, "dev-xs")
        'BASIC3-X2C-4G'

        >>> get_instance_type(Provider.AWS, "std-m")
        'm6i.2xlarge'

        >>> get_instance_type(Provider.SCALEWAY, "COMPUTE3-X8C-16G")
        'COMPUTE3-X8C-16G'  # Pass-through for exact instance types
    """
    provider_key = provider.value

    # Check if provider exists in flavor map
    if provider_key not in FLAVOR_MAP:
        # Provider not in map, return flavor as-is
        return flavor

    provider_flavors = FLAVOR_MAP[provider_key]

    # Check if flavor exists in provider's flavor map
    if flavor in provider_flavors:
        return provider_flavors[flavor]

    # Flavor not found, assume it's an exact instance type and return as-is
    return flavor


def list_available_flavors(provider: Provider) -> list[str]:
    """
    List all available abstract flavors for a provider.

    Args:
        provider: Cloud provider

    Returns:
        List of available flavor names

    Example:
        >>> list_available_flavors(Provider.SCALEWAY)
        ['dev-xs', 'dev-s', 'dev-m', 'dev-l', 'std-xs', 'std-s', ...]
    """
    provider_key = provider.value

    if provider_key not in FLAVOR_MAP:
        return []

    return list(FLAVOR_MAP[provider_key].keys())


def validate_flavor(provider: Provider, flavor: str, allow_exact: bool = True) -> bool:
    """
    Validate that a flavor is available for a provider.

    Args:
        provider: Cloud provider
        flavor: Flavor name to validate
        allow_exact: If True, allows exact instance types (default: True)

    Returns:
        True if flavor is valid, False otherwise

    Example:
        >>> validate_flavor(Provider.SCALEWAY, "dev-xs")
        True

        >>> validate_flavor(Provider.SCALEWAY, "invalid")
        True  # Assumes it's an exact instance type

        >>> validate_flavor(Provider.SCALEWAY, "invalid", allow_exact=False)
        False
    """
    provider_key = provider.value

    if provider_key not in FLAVOR_MAP:
        return allow_exact

    # Check if it's a known abstract flavor
    if flavor in FLAVOR_MAP[provider_key]:
        return True

    # If not a known flavor, return based on allow_exact
    return allow_exact


def get_flavor_info(provider: Provider, flavor: str) -> Dict[str, str]:
    """
    Get information about a flavor.

    Args:
        provider: Cloud provider
        flavor: Flavor name

    Returns:
        Dictionary with flavor information including:
        - abstract_flavor: The abstract flavor name (if recognized)
        - instance_type: The provider-specific instance type
        - is_exact: Whether the flavor was an exact instance type

    Example:
        >>> get_flavor_info(Provider.SCALEWAY, "std-m")
        {'abstract_flavor': 'std-m', 'instance_type': 'STANDARD3-X8C-32G', 'is_exact': False}

        >>> get_flavor_info(Provider.SCALEWAY, "COMPUTE3-X8C-16G")
        {'abstract_flavor': None, 'instance_type': 'COMPUTE3-X8C-16G', 'is_exact': True}
    """
    provider_key = provider.value
    instance_type = get_instance_type(provider, flavor)

    # Check if it's a recognized abstract flavor
    is_abstract = (
        provider_key in FLAVOR_MAP and
        flavor in FLAVOR_MAP[provider_key]
    )

    return {
        "abstract_flavor": flavor if is_abstract else None,
        "instance_type": instance_type,
        "is_exact": not is_abstract,
    }

