"""
Scaleway instance type availability checker.

Queries the Scaleway Instance API to determine if a given instance type
is available in a specific zone, enabling multizone fallback logic.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple

import pulumi


SCALEWAY_API_BASE = "https://api.scaleway.com/instance/v1"

# Cache of availability data per zone to avoid redundant API calls
_availability_cache: Dict[str, Dict[str, str]] = {}


def _get_secret_key() -> Optional[str]:
    """Return the Scaleway secret key from the environment."""
    return os.environ.get("SCW_SECRET_KEY")


def _fetch_zone_availability(zone: str, secret_key: str) -> Dict[str, str]:
    """
    Fetch availability for all instance types in a zone.

    Args:
        zone: Scaleway zone (e.g., "fr-par-2")
        secret_key: Scaleway API secret key

    Returns:
        Dict mapping instance type names to their availability status.
        Possible values: "available", "scarce", "shortage"
    """
    if zone in _availability_cache:
        return _availability_cache[zone]

    url = f"{SCALEWAY_API_BASE}/zones/{zone}/products/servers/availability"
    req = urllib.request.Request(
        url,
        headers={
            "X-Auth-Token": secret_key,
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            servers = data.get("servers", {})
            result = {
                name: info.get("availability", "shortage")
                for name, info in servers.items()
            }
            _availability_cache[zone] = result
            return result
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        pulumi.log.warn(
            f"Failed to fetch availability for zone {zone}: {exc}"
        )
        return {}


def is_instance_available(zone: str, instance_type: str) -> Optional[bool]:
    """
    Check whether *instance_type* is available in *zone*.

    Returns:
        True  – available or scarce (can still be provisioned)
        False – shortage or not present in the zone
        None  – could not determine (missing API key / network error)
    """
    secret_key = _get_secret_key()
    if not secret_key:
        pulumi.log.warn(
            "SCW_SECRET_KEY not set – skipping availability check"
        )
        return None

    availability = _fetch_zone_availability(zone, secret_key)
    if not availability:
        return None

    status = availability.get(instance_type)
    if status is None:
        pulumi.log.info(
            f"  {instance_type} not listed in {zone}"
        )
        return False

    available = status in ("available", "scarce")
    pulumi.log.info(
        f"  {instance_type} in {zone}: {status}"
    )
    return available


def resolve_flavors(
    fallback_chain: List[Tuple[str, str]],
) -> Optional[Tuple[str, str]]:
    """
    Walk *fallback_chain* and return the first available (instance_type, zone).

    Each element is a ``(instance_type, zone)`` pair.  The function queries
    the Scaleway availability API for each entry in order and returns the
    first one whose status is ``available`` or ``scarce``.

    Args:
        fallback_chain: Ordered list of ``(instance_type, zone)`` pairs.

    Returns:
        ``(instance_type, zone)`` of the first available option, or
        ``None`` if nothing could be resolved (API unavailable / no key).
    """
    secret_key = _get_secret_key()
    if not secret_key:
        pulumi.log.warn(
            "SCW_SECRET_KEY not set – cannot check availability, "
            "using first option in fallback chain"
        )
        return None

    pulumi.log.info(
        f"Checking availability across {len(fallback_chain)} fallback option(s)…"
    )

    for instance_type, zone in fallback_chain:
        result = is_instance_available(zone, instance_type)
        if result is True:
            pulumi.log.info(
                f"  ✓ Selected {instance_type} in {zone}"
            )
            return instance_type, zone
        # result is False → try next; None → API issue, try next

    pulumi.log.warn("No option in fallback chain is available")
    return None
