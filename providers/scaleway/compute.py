"""
Scaleway compute implementation.

This module handles instance creation, security groups, and network
attachments for Scaleway infrastructure.
"""

import pulumi
import pulumiverse_scaleway as scaleway
from typing import Any, Dict, List, Optional
from core.interfaces import ComputeInterface
from core.models import ClusterConfig, NodeOutput
from .images import get_os_image


class ScalewayCompute(ComputeInterface):
    """
    Scaleway-specific implementation of compute provisioning.
    
    Handles creation of:
    - Security Groups (firewall rules)
    - Instances (virtual machines)
    - Private NICs (network interfaces for private networks)
    """
    
    def __init__(self, config: ClusterConfig):
        """
        Initialize Scaleway compute provider.
        
        Args:
            config: Cluster configuration
        """
        super().__init__(config)
        self._security_groups: Dict[str, scaleway.instance.SecurityGroup] = {}
        self._instances: Dict[str, scaleway.instance.Server] = {}
        self._nics: Dict[str, scaleway.instance.PrivateNic] = {}
    
    def get_bastion_os_image(self) -> str:
        """
        Get the OS image label for the bastion node.
        
        Since bastion always uses PLAY2-NANO (block-storage-only instance),
        we return the marketplace image label format (e.g., "rockylinux_9")
        rather than a UUID.
        
        Returns:
            Image label in format "os_version" (e.g., "rockylinux_9")
        """
        # Bastion uses PLAY2-NANO which is block-storage-only
        # These instances need the marketplace label format, not UUID
        return f"{self.config.bastion_os_name}_{self.config.bastion_os_version}"
    
    def get_worker_image(self) -> str:
        """
        Get the snapshot/image ID for worker nodes.
        
        If worker_snapshot_id is configured, uses that.
        Otherwise, falls back to the same OS as bastion (marketplace image).
        
        Returns:
            Snapshot/Image ID (UUID) or marketplace image label
        """
        if self.config.worker_snapshot_id:
            return self.config.worker_snapshot_id
        else:
            # Fall back to same OS as bastion
            return f"{self.config.bastion_os_name}_{self.config.bastion_os_version}"
    
    def create_security_group(
        self,
        name: str,
        rules: List[Dict[str, Any]],
        **kwargs
    ) -> scaleway.instance.SecurityGroup:
        """
        Create a Scaleway security group with specified rules.
        
        Security groups in Scaleway are stateful firewalls that
        control inbound and outbound traffic.
        
        Args:
            name: Security group name
            rules: List of rule dictionaries with keys:
                - action: "accept" or "drop"
                - direction: "inbound" or "outbound"
                - protocol: "TCP", "UDP", "ICMP", or "ANY"
                - port: Port number (optional)
                - ip_range: CIDR block (default: "0.0.0.0/0")
            **kwargs: Additional Scaleway SecurityGroup arguments
            
        Returns:
            Scaleway SecurityGroup resource
        """
        inbound_default = kwargs.get("inbound_default_policy", "drop")
        outbound_default = kwargs.get("outbound_default_policy", "accept")
        description = kwargs.get("description", f"Security group for {name}")
        
        # Convert rules to Scaleway format
        inbound_rules = []
        for rule in rules:
            if rule.get("direction", "inbound") == "inbound":
                rule_args = scaleway.instance.SecurityGroupInboundRuleArgs(
                    action=rule.get("action", "accept"),
                    protocol=rule.get("protocol", "TCP"),
                    ip_range=rule.get("ip_range", "0.0.0.0/0"),
                )
                
                # Add port if specified
                if "port" in rule:
                    rule_args.port = rule["port"]
                if "port_range" in rule:
                    rule_args.port_range = rule["port_range"]
                
                inbound_rules.append(rule_args)
        
        sg = scaleway.instance.SecurityGroup(
            f"sg-{name}",
            name=name,
            description=description,
            inbound_default_policy=inbound_default,
            outbound_default_policy=outbound_default,
            inbound_rules=inbound_rules,
            stateful=True,  # Critical: allow return traffic automatically
            project_id=self.config.project_id,
            zone=self.config.zone,
        )
        
        self._security_groups[name] = sg
        return sg
    
    def create_instance(
        self,
        name: str,
        image: str,
        instance_type: str,
        security_group: scaleway.instance.SecurityGroup,
        tags: List[str],
        **kwargs
    ) -> NodeOutput:
        """
        Create a Scaleway instance (virtual machine).
        
        Args:
            name: Instance name
            image: Image ID (UUID)
            instance_type: Instance type (e.g., "PLAY2-NANO")
            security_group: Security group resource
            tags: List of tags
            **kwargs: Additional parameters:
                - user_data: Cloud-init script
                - additional_volume_ids: List of volume IDs to attach
                - create_public_ip: Whether to create and attach a public IP (default: True)
                
        Returns:
            NodeOutput with instance information
        """
        user_data = kwargs.get("user_data")
        additional_volumes = kwargs.get("additional_volume_ids", [])
        
        # Prepare user_data in Scaleway format
        user_data_dict = None
        if user_data:
            user_data_dict = {
                "cloud-init": user_data
            }
        
        # Determine if instance type uses block-storage-only (PLAY2, STARDUST, PRO2 families)
        # These instances MUST NOT have root_volume specified - Scaleway manages it automatically
        # Also, they need image LABELS not UUIDs, as marketplace image UUIDs contain local volume specs
        uses_block_storage_only = (instance_type.startswith("PLAY2-") or 
                                    instance_type.startswith("STARDUST") or
                                    instance_type.startswith("PRO2-"))
        
        # For block-storage-only instances using marketplace images, 
        # use image label instead of UUID (only for bastion nodes with marketplace images)
        # Worker nodes should use the snapshot UUID directly
        server_image = image
        # Note: The 'image' parameter should already be in the correct format
        # (either a UUID for snapshots or a marketplace label for bastion)
        
        # Configure root volume based on instance type
        # CRITICAL: For block-storage-only instances, do NOT specify root_volume at all
        # Any root_volume specification attempts to create local storage, which is not supported
        root_volume = None

        # Only create volume from snapshot for worker nodes (not bastion)
        # Check if image is a UUID (snapshot) vs marketplace label
        is_snapshot = self.config.worker_snapshot_id and image == self.config.worker_snapshot_id
        
        if is_snapshot and uses_block_storage_only:
            # For block-storage instances with snapshots, create a boot volume
            snapshot = scaleway.block.get_snapshot(
                snapshot_id=self.config.worker_snapshot_id,
                zone=self.config.zone,
                project_id=self.config.project_id,
            )
            from_snapshot = scaleway.block.Volume(
                f"vol-{name}",  # Unique name per instance
                name=f"{name}-boot",
                snapshot_id=snapshot.id,
                iops=5000,
                zone=self.config.zone,
                project_id=self.config.project_id,
            )
            root_volume = scaleway.instance.ServerRootVolumeArgs(
                volume_id=from_snapshot.id,
                volume_type="sbs_volume",
            )
        elif not uses_block_storage_only and kwargs.get("root_volume_size_gb"):
            # Only for instances that support local storage (DEV1, GP1, etc.)
            root_volume = scaleway.instance.ServerRootVolumeArgs(
                size_in_gb=kwargs.get("root_volume_size_gb"),
                delete_on_termination=True,
            )
        
        # Create a public IP for the instance if requested
        create_public_ip = kwargs.get("create_public_ip", True)
        public_ip_resource = None
        ip_id = None
        
        if create_public_ip:
            public_ip_resource = scaleway.instance.Ip(
                f"ip-{name}",
                project_id=self.config.project_id,
                zone=self.config.zone,
            )
            ip_id = public_ip_resource.id
        
        # Create the server
        # Note: SSH keys are injected via cloud-init in user_data
        # IMPORTANT: cloud-init (user_data) only runs at instance creation,
        # so changes to user_data will trigger instance replacement
        
        # When using root_volume with volume_id, we cannot specify image
        # When using image, we cannot specify root_volume with volume_id
        server_args = {
            "name": name,
            "type": instance_type,
            "ip_id": ip_id,
            "security_group_id": security_group.id,
            "tags": tags,
            "project_id": self.config.project_id,
            "zone": self.config.zone,
            "user_data": user_data_dict,
            "additional_volume_ids": additional_volumes if additional_volumes else None,
        }
        
        # Either use image OR root_volume with volume_id (mutually exclusive)
        if root_volume and hasattr(root_volume, 'volume_id'):
            # Boot from existing volume (e.g., from snapshot)
            server_args["root_volume"] = root_volume
        else:
            # Boot from image (marketplace or custom)
            server_args["image"] = server_image
            if root_volume:  # root_volume without volume_id (size-based)
                server_args["root_volume"] = root_volume
        
        server = scaleway.instance.Server(
            f"instance-{name}",
            **server_args,
            opts=pulumi.ResourceOptions(
                replace_on_changes=["user_data"],  # Force replacement when user_data changes
                depends_on=[security_group],  # Ensure SG exists before instance
            ),
        )
        
        self._instances[name] = server
        
        # Create NodeOutput
        # Use the public IP address from the IP resource if created
        output = NodeOutput(
            id=server.id,
            name=name,
            public_ip=public_ip_resource.address if public_ip_resource else None,
            resource=server,
        )
        
        return output
    
    def create_volume(
        self,
        name: str,
        size_gb: int,
        **kwargs
    ) -> scaleway.block.Volume:
        """
        Create a block storage volume.
        
        Args:
            name: Volume name
            size_gb: Volume size in GB
            **kwargs: Additional parameters:
                - iops: IOPS limit (default: 5000)
                -
        Returns:
            Block Volume resource
        """
        iops = kwargs.get("iops", 5000)
        
        volume = scaleway.block.Volume(
            f"vol-{name}",
            name=name,
            size_in_gb=size_gb,
            iops=iops,
            zone=self.config.zone,
            project_id=self.config.project_id,
        )
        
        return volume
    
    def attach_to_private_network(
        self,
        instance: scaleway.instance.Server,
        network: Any,
        **kwargs
    ) -> scaleway.instance.PrivateNic:
        """
        Attach an instance to a private network.
        
        Creates a Private NIC (Network Interface Card) that connects
        the instance to the specified private network.
        
        Args:
            instance: Server resource
            network: Private network resource
            **kwargs: Additional parameters
            
        Returns:
            PrivateNic resource
        """
        # Extract instance name from Pulumi resource name
        instance_name = kwargs.get("instance_name", "unknown")
        
        nic = scaleway.instance.PrivateNic(
            f"nic-{instance_name}",
            server_id=instance.id,
            private_network_id=network.id,
            zone=self.config.zone,
        )
        
        self._nics[instance_name] = nic
        return nic
    
    def create_bastion_security_group(self) -> scaleway.instance.SecurityGroup:
        """
        Create a security group for bastion/jump host.
        
        Allows SSH (port 22) from anywhere, drops everything else inbound.
        
        Returns:
            SecurityGroup resource for bastion
        """
        return self.create_security_group(
            name="bastion",
            rules=[
                {
                    "action": "accept",
                    "direction": "inbound",
                    "protocol": "TCP",
                    "port": 22,
                    "ip_range": "0.0.0.0/0",
                }
            ],
            description="Bastion host - SSH access from internet",
            inbound_default_policy="drop",
            outbound_default_policy="accept",
        )
    
    def create_internal_security_group(
        self,
        private_subnet: str = "192.168.10.0/24"
    ) -> scaleway.instance.SecurityGroup:
        """
        Create a security group for internal nodes.
        
        Allows all traffic from the private subnet, drops external traffic.
        
        Args:
            private_subnet: CIDR block of the private network
            
        Returns:
            SecurityGroup resource for internal nodes
        """
        return self.create_security_group(
            name="internal",
            rules=[
                {
                    "action": "accept",
                    "direction": "inbound",
                    "protocol": "ANY",
                    "ip_range": private_subnet,
                }
            ],
            description="Internal nodes - only accessible from private network",
            inbound_default_policy="drop",
            outbound_default_policy="accept",
        )
    
    def create_single_node_security_group(self) -> scaleway.instance.SecurityGroup:
        """
        Create a security group for a single standalone node.
        
        Allows SSH (port 22) from anywhere, can be customized based on needs.
        
        Returns:
            SecurityGroup resource for single node
        """
        return self.create_security_group(
            name="single-node",
            rules=[
                {
                    "action": "accept",
                    "direction": "inbound",
                    "protocol": "TCP",
                    "port": 22,
                    "ip_range": "0.0.0.0/0",
                }
            ],
            description="Single node - SSH access",
            inbound_default_policy="drop",
            outbound_default_policy="accept",
        )
    
    def get_security_group(self, name: str) -> Optional[scaleway.instance.SecurityGroup]:
        """Get a created security group by name."""
        return self._security_groups.get(name)
    
    def get_instance(self, name: str) -> Optional[scaleway.instance.Server]:
        """Get a created instance by name."""
        return self._instances.get(name)
    
    def get_nic(self, name: str) -> Optional[scaleway.instance.PrivateNic]:
        """Get a created NIC by instance name."""
        return self._nics.get(name)

