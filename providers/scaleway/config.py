"""
Scaleway-specific configuration utilities.

This module provides helpers for validating and processing
Scaleway-specific configuration values.
"""

from typing import List

# Valid Scaleway instance types — Gen3 ranges (available in all zones)
SCALEWAY_INSTANCE_TYPES = [
    # BASIC3 — shared vCPUs, development / CI / bastions
    "BASIC3-X2C-4G",
    "BASIC3-X2C-8G",
    "BASIC3-X4C-8G",
    "BASIC3-X4C-16G",
    "BASIC3-X8C-16G",
    "BASIC3-X8C-32G",
    "BASIC3-X16C-32G",
    "BASIC3-X16C-64G",

    # STANDARD3 — dedicated vCPUs, balanced production
    "STANDARD3-X2C-8G",
    "STANDARD3-X4C-16G",
    "STANDARD3-X8C-32G",
    "STANDARD3-X16C-64G",
    "STANDARD3-X32C-128G",
    "STANDARD3-X48C-192G",

    # COMPUTE3 — dedicated vCPUs, compute-optimised
    "COMPUTE3-X2C-4G",
    "COMPUTE3-X4C-8G",
    "COMPUTE3-X8C-16G",
    "COMPUTE3-X16C-32G",
    "COMPUTE3-X32C-64G",
    "COMPUTE3-X48C-96G",
    "COMPUTE3-X64C-128G",
    "COMPUTE3-X96C-192G",
]

# Valid Scaleway regions
SCALEWAY_REGIONS = [
    "fr-par",  # Paris, France
    "nl-ams",  # Amsterdam, Netherlands
    "pl-waw",  # Warsaw, Poland
]

# Valid Scaleway zones
SCALEWAY_ZONES = [
    "fr-par-1",
    "fr-par-2",
    "fr-par-3",
    "nl-ams-1",
    "nl-ams-2",
    "pl-waw-1",
    "pl-waw-2",
]

# Gateway types
SCALEWAY_GATEWAY_TYPES = [
    "VPC-GW-S",   # Small gateway
    "VPC-GW-M",   # Medium gateway
    "VPC-GW-L",   # Large gateway
]


def validate_instance_type(instance_type: str) -> bool:
    """
    Validate that the instance type is supported by Scaleway.
    
    Args:
        instance_type: Instance type string
        
    Returns:
        True if valid, False otherwise
    """
    return instance_type in SCALEWAY_INSTANCE_TYPES


def validate_region(region: str) -> bool:
    """
    Validate that the region is a valid Scaleway region.
    
    Args:
        region: Region string
        
    Returns:
        True if valid, False otherwise
    """
    return region in SCALEWAY_REGIONS


def validate_zone(zone: str) -> bool:
    """
    Validate that the zone is a valid Scaleway zone.
    
    Args:
        zone: Zone string
        
    Returns:
        True if valid, False otherwise
    """
    return zone in SCALEWAY_ZONES


def get_zones_for_region(region: str) -> List[str]:
    """
    Get available zones for a region.
    
    Args:
        region: Region name
        
    Returns:
        List of zone names
    """
    zone_map = {
        "fr-par": ["fr-par-1", "fr-par-2", "fr-par-3"],
        "nl-ams": ["nl-ams-1", "nl-ams-2"],
        "pl-waw": ["pl-waw-1", "pl-waw-2"],
    }
    return zone_map.get(region, [])


def get_region_from_zone(zone: str) -> str:
    """
    Extract the region from a zone name.
    
    Args:
        zone: Zone name (e.g., "fr-par-1")
        
    Returns:
        Region name (e.g., "fr-par")
    """
    # Zone format is always "region-#"
    parts = zone.rsplit("-", 1)
    return parts[0] if parts else zone

