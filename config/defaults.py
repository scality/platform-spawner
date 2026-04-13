"""
Default configuration values for different providers and topologies.
"""

from typing import Dict

# Default instance types per provider (for worker nodes)
# Note: Bastion always uses small dev-tier machines
DEFAULT_INSTANCE_TYPES: Dict[str, Dict[str, str]] = {
    "scaleway": {
        "development": "BASIC3-X2C-4G",
        "production": "STANDARD3-X8C-32G",
        "bastion": "BASIC3-X2C-4G",
    },
    "aws": {
        "development": "t3.medium",
        "production": "m6i.2xlarge",
        "bastion": "t3.medium",
    },
}

# Default regions per provider
DEFAULT_REGIONS: Dict[str, str] = {
    "scaleway": "fr-par",
    "aws": "us-east-1",
}

# Default zones per provider
DEFAULT_ZONES: Dict[str, str] = {
    "scaleway": "fr-par-2",
    "aws": "us-east-1a",
}

# SSH port for bastion access
DEFAULT_SSH_PORT = 22

# Default private network CIDR
DEFAULT_PRIVATE_SUBNET = "192.168.10.0/24"

# Default DNS local name for private network
DEFAULT_DNS_LOCAL_NAME = "cluster.local"

# Default bastion OS (user-friendly alias + major version, resolved via OS_NAME_ALIASES)
DEFAULT_BASTION_OS_NAME = "rocky"
DEFAULT_BASTION_OS_MAJOR_VERSION = "9"

# Default instance image for worker nodes (Scaleway marketplace label format)
# "rocky" maps to "rockylinux" on Scaleway (see OS_NAME_ALIASES below)
DEFAULT_INSTANCE_IMAGE = f"rockylinux_{DEFAULT_BASTION_OS_MAJOR_VERSION}"


# Default bastion flavor (abstract flavor name, resolved via FLAVOR_MAP in config/flavors.py)
DEFAULT_BASTION_FLAVOR = "dev-xs"

# OS name alias map per provider.
# Maps user-friendly OS family names to provider-specific marketplace label names.
# Used to normalise inputs like "rocky-8" → family "rockylinux", version "8".
OS_NAME_ALIASES: Dict[str, Dict[str, str]] = {
    "scaleway": {
        "rocky": "rockylinux",
        "rocky-linux": "rockylinux",
        "ubuntu": "ubuntu",
        "debian": "debian",
    },
    "aws": {
        "rocky": "rockylinux",
        "rocky-linux": "rockylinux",
        "ubuntu": "ubuntu",
        "debian": "debian",
    },
}

# Default SSH user per OS family name.
# Maps the user-friendly bastion_os_name to the default SSH username for that OS.
DEFAULT_BASTION_USERS: Dict[str, str] = {
    "rocky": "rocky",
    "rocky-linux": "rocky",
    "rockylinux": "rocky",
    "ubuntu": "ubuntu",
    "debian": "admin",
}
