"""
Factory for creating provider-specific cluster implementations.

This module implements the factory pattern to instantiate the appropriate
cluster implementation based on the configured cloud provider.
"""

from typing import TYPE_CHECKING
from .models import ClusterConfig, Provider
from .interfaces import ClusterInterface

if TYPE_CHECKING:
    # Avoid circular imports during type checking
    pass


def create_cluster(config: ClusterConfig) -> ClusterInterface:
    """
    Factory function to create a cluster implementation for the specified provider.
    
    This function routes to the appropriate provider-specific implementation
    based on the provider specified in the configuration.
    
    Args:
        config: Cluster configuration including provider information
        
    Returns:
        Provider-specific implementation of ClusterInterface
        
    Raises:
        ValueError: If the provider is not supported or not yet implemented
        
    Example:
        >>> from core.models import ClusterConfig, Provider
        >>> config = ClusterConfig(
        ...     worker_count=3,
        ...     provider=Provider.SCALEWAY,
        ...     region="fr-par",
        ...     zone="fr-par-1",
        ...     project_id="12345"
        ... )
        >>> cluster = create_cluster(config)
        >>> outputs = cluster.deploy()
    """
    
    if config.provider == Provider.SCALEWAY:
        from providers.scaleway.cluster import ScalewayCluster
        return ScalewayCluster(config)
    
    elif config.provider == Provider.AWS:
        raise NotImplementedError(
            "AWS provider is not yet implemented. "
            "To add AWS support, create providers/aws/cluster.py "
            "implementing ClusterInterface."
        )
    
    else:
        raise ValueError(
            f"Unknown provider: {config.provider}. "
            f"Supported providers: {[p.value for p in Provider]}"
        )


def list_supported_providers() -> list[str]:
    """
    Get a list of currently implemented providers.
    
    Returns:
        List of provider names that have implementations
    """
    return [Provider.SCALEWAY.value]


def list_planned_providers() -> list[str]:
    """
    Get a list of providers planned but not yet implemented.
    
    Returns:
        List of provider names that are planned
    """
    return [Provider.AWS.value]

