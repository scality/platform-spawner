"""
Default configuration values for different providers and topologies.
"""

from typing import Dict, Any

# Default instance types per provider (for worker nodes)
# Note: Bastion always uses small machines (e.g., PLAY2-NANO for Scaleway)
DEFAULT_INSTANCE_TYPES: Dict[str, Dict[str, str]] = {
    "scaleway": {
        "development": "PLAY2-NANO",
        "production": "PRO2-S",  # Default for worker nodes
        "bastion": "PLAY2-NANO",  # Always small machine for SSH access
    },
    "aws": {
        "development": "t3.micro",
        "production": "t3.medium",
    },
    "ovh": {
        "development": "d2-2",
        "production": "b2-7",
    }
}

# Default regions per provider
DEFAULT_REGIONS: Dict[str, str] = {
    "scaleway": "fr-par",
    "aws": "us-east-1",
    "ovh": "GRA",
}

# Default zones per provider
DEFAULT_ZONES: Dict[str, str] = {
    "scaleway": "fr-par-1",
    "aws": "us-east-1a",
    "ovh": "GRA1",
}

# SSH port for bastion access
DEFAULT_SSH_PORT = 22

# Default private network CIDR
DEFAULT_PRIVATE_SUBNET = "192.168.10.0/24"

# Default DNS local name for private network
DEFAULT_DNS_LOCAL_NAME = "cluster.local"

