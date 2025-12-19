"""
Flavor abstraction layer for multi-provider support.

This module provides mappings from abstract flavor names (small, medium, large)
to provider-specific instance types, enabling consistent sizing across clouds.
"""

from typing import Dict, Optional
from core.models import Provider


# Flavor mappings per provider
FLAVOR_MAP: Dict[str, Dict[str, str]] = {
    "scaleway": {
        # Small instances - suitable for bastion hosts, testing
        "small": "PLAY2-NANO",
        "tiny": "PLAY2-PICO",
        
        # Medium instances - suitable for general workloads
        "medium": "PRO2-S",
        "medium-plus": "PRO2-M",
        
        # Large instances - suitable for production workloads
        "large": "PRO2-L",
        "xlarge": "PRO2-XL",
        
        # General purpose instances
        "gp-small": "GP1-XS",
        "gp-medium": "GP1-S",
        "gp-large": "GP1-M",
        "gp-xlarge": "GP1-L",
    },
    "aws": {
        # Small instances - suitable for bastion hosts, testing
        "small": "t3.small",
        "tiny": "t3.micro",
        
        # Medium instances - suitable for general workloads
        "medium": "t3.medium",
        "medium-plus": "t3.large",
        
        # Large instances - suitable for production workloads
        "large": "t3.xlarge",
        "xlarge": "t3.2xlarge",
        
        # General purpose instances
        "gp-small": "m5.large",
        "gp-medium": "m5.xlarge",
        "gp-large": "m5.2xlarge",
        "gp-xlarge": "m5.4xlarge",
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
        >>> get_instance_type(Provider.SCALEWAY, "small")
        'PLAY2-NANO'
        
        >>> get_instance_type(Provider.AWS, "medium")
        't3.medium'
        
        >>> get_instance_type(Provider.SCALEWAY, "PRO2-XXS")
        'PRO2-XXS'  # Pass-through for exact instance types
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
        ['small', 'tiny', 'medium', 'medium-plus', 'large', ...]
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
        >>> validate_flavor(Provider.SCALEWAY, "small")
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
        >>> get_flavor_info(Provider.SCALEWAY, "medium")
        {'abstract_flavor': 'medium', 'instance_type': 'PRO2-S', 'is_exact': False}
        
        >>> get_flavor_info(Provider.SCALEWAY, "PRO2-XXS")
        {'abstract_flavor': None, 'instance_type': 'PRO2-XXS', 'is_exact': True}
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

