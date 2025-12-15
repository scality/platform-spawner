"""
Scaleway-specific configuration utilities.

This module provides helpers for validating and processing
Scaleway-specific configuration values.
"""

from typing import List, Dict

# Valid Scaleway instance types (subset of most common types)
SCALEWAY_INSTANCE_TYPES = [
    # Development instances
    "PLAY2-NANO",
    "PLAY2-MICRO",
    "PLAY2-PICO",
    
    # Production instances
    "PRO2-XXS",
    "PRO2-XS",
    "PRO2-S",
    "PRO2-M",
    "PRO2-L",
    
    # General Purpose
    "GP1-XS",
    "GP1-S",
    "GP1-M",
    "GP1-L",
    "GP1-XL",
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

