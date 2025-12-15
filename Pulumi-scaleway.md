Strategic Migration and Infrastructure Orchestration: Transitioning from OVH to Scaleway with Pulumi
1. Executive Summary and Strategic Alignment
The digital infrastructure landscape is undergoing a profound shift from manual, hardware-centric management to API-driven, declarative orchestration. For organizations migrating from OVH Public Cloud to Scaleway, this transition represents more than a mere vendor swap; it necessitates a fundamental re-evaluation of how compute, networking, and security resources are provisioned and maintained. This report serves as a comprehensive, expert-level guide for implementing this migration using Pulumi with Python, allowing for powerful abstraction and logic definition.
The request to transition from OVH to Scaleway while adopting Pulumi introduces three distinct layers of technological adaptation: the cloud provider shift, the operating system standardization on Rocky Linux, and the move to a general-purpose programming language (Python) for infrastructure definition. This document analyzes these layers in depth, providing a robust theoretical framework alongside actionable, production-grade implementation tutorials for three specific topologies: a single-node instance, a three-node cluster with a bastion and private networking, and a six-node distributed system.
By leveraging the pulumiverse-scaleway provider, we can abstract the complexities of Scaleway’s underlying API—such as the interplay between Virtual Private Clouds (VPC), Private Networks, and Public Gateways—into coherent, reusable code structures.1
1.1 The Operational Shift: OVH vs. Scaleway
Migrating from OVH requires understanding the mapping of core concepts. OVH often relies on the vRack technology for private networking, which functions as a cross-datacenter VLAN. Scaleway’s equivalent is the VPC Private Network, which offers regional Layer 2 isolation but integrates more tightly with managed services like Public Gateways for NAT (Network Address Translation) and DHCP.2 Where an OVH user might manually configure a failover IP on a specialized bridge interface, a Scaleway user utilizes "Flexible IPs" and managed Gateway Networks to handle routing and masquerading automatically.
1.2 The Infrastructure as Code Paradigm with Python
The choice of Python allows us to leverage standard software engineering practices—functions, loops, and list comprehensions—directly in the infrastructure definition. Unlike HCL (Terraform) or YAML (Ansible), which are declarative but often struggle with complex logic (like iterating to create a 6-node cluster with specific naming conventions), Pulumi allows us to treat infrastructure as software. This capability is critical for the requested 6-node cluster scenario, where defining resources programmatically reduces code duplication and error potential.
2. Architectural Prerequisites and Environment Configuration
Before commencing with code generation, the operational environment must be rigorously prepared. This involves establishing the security context, authentication mechanisms, and the local development toolchain required to interface with the Scaleway API.
2.1 Identity and Access Management (IAM)
The security posture of the infrastructure begins with how Pulumi authenticates with Scaleway. Unlike a GUI interaction where a user logs in via a web browser, Pulumi operates as an automated agent. This requires the generation of API keys with appropriate scopes.
In the Scaleway console, one must navigate to the IAM section to generate an Access Key and a Secret Key. These credentials should never be hardcoded into the Python source files. Instead, they should be injected into the runtime environment via environment variables.
SCW_ACCESS_KEY: The public identifier for the API token.
SCW_SECRET_KEY: The private component used to sign API requests.
SCW_DEFAULT_PROJECT_ID: The UUID of the specific Scaleway Project where resources will be spawned.
2.2 The Pulumi Project Structure
A Pulumi project is the logical container for the infrastructure code. When initializing a new project for this migration using Python, the system generates a Pulumi.yaml file (defining the project metadata), a __main__.py file (the entry point), and a requirements.txt file (managing dependencies).
To support Scaleway, the requirements.txt must declare a dependency on the pulumiverse-scaleway package.
pulumi>=3.0.0
pulumiverse-scaleway>=1.38.0
The version 1.38.0 or later is recommended to ensure support for the latest VPC and Instance features, including the transition from deprecated resources to the newer scaleway.network namespace.2
2.3 The Operating System Strategy: Rocky Linux
The requirement to utilize Rocky Linux necessitates a specific strategy for image selection. Cloud providers frequently update their base images to include security patches. Consequently, the UUID for a "Rocky Linux 9" image changes over time. Hardcoding a specific UUID (e.g., 123e4567-e89b-12d3-a456-426614174000) into the Pulumi code makes the infrastructure brittle.
A robust approach utilizes a dynamic lookup mechanism. Scaleway tags its images with labels such as rockylinux_9. Using the get_marketplace_image function provided by the Pulumi Scaleway provider, the code can query the API at runtime to find the current UUID associated with the rockylinux_9 label.5 This ensures that every deployment utilizes the most up-to-date, secure version of the operating system without manual code intervention.
3. Core Networking Concepts: The Foundation of Connectivity
The transition from a single instance to a 3-node or 6-node cluster introduces the necessity for sophisticated networking. In the Scaleway ecosystem, this is handled through the Virtual Private Cloud (VPC) and Private Networks.
3.1 Virtual Private Cloud (VPC) and Private Networks
A VPC in Scaleway serves as a container for regional network resources. Within a VPC, you create Private Networks. A Private Network functions fundamentally as a Layer 2 VLAN (Virtual Local Area Network) that spans an entire region (e.g., fr-par). This means that an instance in Zone A (fr-par-1) and an instance in Zone B (fr-par-2) can communicate over the Private Network as if they were connected to the same physical switch.2
3.2 Public Gateways and NAT
If a Slave node has no public IP, how does it install updates or reach external APIs? This is resolved using a Public Gateway. The Public Gateway is a managed appliance that attaches to the Private Network and provides Network Address Translation (NAT) and Masquerading services.1
When a Slave node sends traffic destined for the internet (e.g., dnf update), the traffic is routed through the Private Network to the Public Gateway. The Gateway replaces the source IP with its own public IP (Masquerading) and forwards the traffic. This allows the Slave to access the internet outbound without allowing the internet to initiate inbound connections to the Slave.7
3.3 DHCP Management
Scaleway utilizes DHCP to manage IP assignment within the Private Network. The Public Gateway functions as the DHCP server, assigning private IP addresses (e.g., 192.168.10.5) to instances when they boot. This simplifies the configuration of the 6-node cluster, as we do not need to manually calculate and assign IP addresses to each node.8
4. Scenario I: The Single Node Instance Implementation
The first requirement is the deployment of a single Rocky Linux instance. This scenario serves as the "Hello World" of infrastructure provisioning, validating the authentication, image lookup, and basic compute resource definitions.
4.1 Pulumi Implementation (Python): Single Node
The following Python code demonstrates the implementation. It begins by looking up the Rocky Linux image and then defining the resources.

Python


import pulumi
import pulumiverse_scaleway as scaleway

# Identify the Project ID and Zone from configuration
config = pulumi.Config()
project_id = config.require("project_id") # Ensure this is set via `pulumi config set project_id <value>`
zone = "fr-par-1"

# 1. Dynamic Image Lookup: Rocky Linux
# We query the Scaleway Marketplace for the latest 'rockylinux_9' image.
rocky_image = scaleway.get_marketplace_image(
    label="rockylinux_9",
    zone=zone,
)

# 2. Security Group Definition
single_node_sg = scaleway.instance.SecurityGroup("sg-single-node",
    name="sg-rocky-single",
    description="Security group for standalone Rocky Linux instance",
    inbound_default_policy="drop",
    outbound_default_policy="accept",
    inbound_rules=,
    project_id=project_id,
    zone=zone,
)

# 3. Server Provisioning
single_node = scaleway.instance.Server("rocky-single",
    name="rocky-linux-standalone",
    type="PLAY2-NANO", # Cost-effective development instance
    image=rocky_image.id, # Use the ID from the lookup
    security_group_id=single_node_sg.id,
    tags=["env:dev", "os:rocky9"],
    project_id=project_id,
    zone=zone,
)

# 4. Output the IP address
pulumi.export("single_node_public_ip", single_node.public_ip)


5. Scenario II: The Three-Node Cluster (Bootstrap, Bastion, Slave)
The second requirement introduces significant complexity: a 3-node cluster comprising a Bootstrap node, a Bastion node, and a Slave node.
5.1 Architecture: The Bastion Host Pattern
The "Bastion" (or Jump Box) is a critical security pattern. In this architecture, the Bastion Node is the only server with a port (22) open to the general internet. The Bootstrap and Slave nodes reside on the Private Network.
5.2 Pulumi Implementation (Python): 3-Node Cluster
This section creates the shared network infrastructure and the three distinct servers.

Python


import pulumi
import pulumiverse_scaleway as scaleway

zone = "fr-par-1"
#... (Image lookup code from Scenario I)...

# --- Shared Network Resources ---

vpc = scaleway.network.Vpc("cluster-vpc",
    name="rocky-cluster-vpc",
    tags=["stack:cluster-3-node"],
    region="fr-par",
)

private_network = scaleway.network.PrivateNetwork("cluster-pn",
    vpc_id=vpc.id,
    name="cluster-internal-net",
    tags=["internal"],
    region="fr-par",
)

# Public Gateway for NAT (Outbound Internet for Private Nodes)
pg_ip = scaleway.network.PublicGatewayIp("pg-ip")

gateway = scaleway.network.PublicGateway("cluster-gw",
    name="cluster-gateway",
    type="VPC-GW-S",
    ip_id=pg_ip.id,
    bastion_enabled=False, # We are building our own Bastion Node per request
    zone=zone,
)

gateway_network = scaleway.network.GatewayNetwork("gw-net",
    gateway_id=gateway.id,
    private_network_id=private_network.id,
    dhcp=scaleway.network.GatewayNetworkDhcpArgs(
        subnet="192.168.10.0/24", # The internal CIDR
        dns_local_name="cluster.local",
    ),
    enable_masquerade=True, # Crucial: Enables NAT
    cleanup_dhcp=True,
    zone=zone,
)

# --- Security Groups ---

# SG for Bastion: Open to World on Port 22
sg_bastion = scaleway.instance.SecurityGroup("sg-bastion",
    inbound_default_policy="drop",
    outbound_default_policy="accept",
    inbound_rules=,
    zone=zone,
)

# SG for Internal Nodes: Allow Traffic from Private Subnet Only
# Note: Scaleway SGs are stateful.
sg_internal = scaleway.instance.SecurityGroup("sg-internal",
    inbound_default_policy="drop",
    outbound_default_policy="accept",
    inbound_rules=,
    zone=zone,
)

# --- Instance Creation ---

# 1. Bastion Node (Public + Private)
bastion = scaleway.instance.Server("node-bastion",
    name="bastion-node",
    image=rocky_image.id,
    type="PLAY2-NANO",
    security_group_id=sg_bastion.id, # Public SG
    tags=["role:bastion"],
    zone=zone,
)

# Attach Bastion to Private Network
nic_bastion = scaleway.instance.PrivateNic("nic-bastion",
    server_id=bastion.id,
    private_network_id=private_network.id,
    zone=zone,
)

# 2. Bootstrap Node (Private Only)
# We set valid tags and internal SG. 
# Scaleway assigns a public IP by default; strict SG rules effectively nullify it,
# or we can explicitly not use it by ignoring the public IP resource.
bootstrap = scaleway.instance.Server("node-bootstrap",
    name="bootstrap-node",
    image=rocky_image.id,
    type="PLAY2-NANO",
    security_group_id=sg_internal.id, # Internal SG
    tags=["role:bootstrap"],
    zone=zone,
)

nic_bootstrap = scaleway.instance.PrivateNic("nic-bootstrap",
    server_id=bootstrap.id,
    private_network_id=private_network.id,
    zone=zone,
)

# 3. Slave Node (Private Only)
slave = scaleway.instance.Server("node-slave",
    name="slave-node",
    image=rocky_image.id,
    type="PLAY2-NANO",
    security_group_id=sg_internal.id,
    tags=["role:slave"],
    zone=zone,
)

nic_slave = scaleway.instance.PrivateNic("nic-slave",
    server_id=slave.id,
    private_network_id=private_network.id,
    zone=zone,
)


6. Scenario III: The Six-Node Distributed Cluster
The final requirement is a 6-node cluster: 1 Bootstrap, 1 Bastion, and 4 Slaves. This scenario highlights the power of Python loops to automate resource creation.
6.1 Python Implementation: 6-Node Cluster
The networking setup (VPC, Gateway) and the Bastion/Bootstrap setup remain identical to Scenario II. The difference lies in the iteration for the slave nodes.

Python


#... (Include Networking, Bastion, and Bootstrap code from Scenario II)...

# --- Scalable Slave Provisioning ---

SLAVE_COUNT = 4 # Total 4 slaves + 1 bootstrap + 1 bastion = 6 nodes
slave_nodes =
slave_ids =

# Optional: Cloud-init script to authorize the bootstrap node's key
slave_user_data = """#!/bin/bash
#cloud-config
users:
  - default
  - name: automation
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ssh-rsa AAAAB3... (Insert Bootstrap Node's Public Key here)
"""

for i in range(1, SLAVE_COUNT + 1):
    # Format index as '01', '02', etc.
    slave_index = f"{i:02d}"
    node_name = f"slave-{slave_index}"
    
    # Create the Server
    server = scaleway.instance.Server(node_name,
        name=f"rocky-slave-{slave_index}",
        image=rocky_image.id,
        type="PLAY2-NANO",
        security_group_id=sg_internal.id, # Secure Internal SG
        tags=["role:slave", f"index:{slave_index}"],
        user_data={
            "cloud-init": slave_user_data
        },
        zone=zone,
    )

    # Create the Private NIC
    nic = scaleway.instance.PrivateNic(f"nic-{node_name}",
        server_id=server.id,
        private_network_id=private_network.id,
        zone=zone,
    )

    slave_nodes.append(server)
    slave_ids.append(server.id)

# Export the list of Slave IDs
pulumi.export("slave_node_ids", slave_ids)


6.2 Advanced Configuration: Persistence
To ensure data persistence on the bootstrap node (e.g., for a database), use Scaleway Block Storage (SBS) or local Block volumes.

Python


volume = scaleway.instance.Volume("data-vol",
    size_in_gb=50,
    type="b_ssd", # Block SSD
    zone=zone
)

bootstrap_with_volume = scaleway.instance.Server("node-bootstrap-persist",
    #... other properties...
    additional_volume_ids=[volume.id]
)


7. Conclusion
This report has detailed the migration path from OVH to Scaleway using Python and Pulumi. We have successfully addressed the three core requirements:
Single Node: Established the baseline using scaleway.instance.Server.
3-Node Cluster: Introduced the VPC, Private Network, and Public Gateway to create a secure, isolated environment.
6-Node Cluster: Demonstrated the power of Python loops to automate the provisioning of multiple slave nodes, ensuring consistency and scalability.
By adopting this infrastructure-as-code approach, the organization gains a reproducible, self-documenting, and scalable platform that adheres to modern DevOps best practices.
Works cited
scaleway.VpcPublicGatewayPatRule | Pulumi Registry, accessed December 10, 2025, https://www.pulumi.com/registry/packages/scaleway/api-docs/vpcpublicgatewaypatrule/
scaleway.Vpc | Pulumi Registry, accessed December 10, 2025, https://www.pulumi.com/registry/packages/scaleway/api-docs/vpc/
How to create a Private Network | Scaleway Documentation, accessed December 10, 2025, https://www.scaleway.com/en/docs/vpc/how-to/create-private-network/
scaleway.InstanceServer | Pulumi Registry, accessed December 10, 2025, https://www.pulumi.com/registry/packages/scaleway/api-docs/instanceserver/
Compatibility between OS Images and different Flexible IP type combinations - Scaleway, accessed December 10, 2025, https://www.scaleway.com/en/docs/instances/reference-content/compatibility-scw-os-images-flexible-ip/
Public Gateway | Scaleway, accessed December 10, 2025, https://www.scaleway.com/en/public-gateway/
Public connectivity - best practices | Scaleway Documentation, accessed December 10, 2025, https://www.scaleway.com/en/docs/ipam/reference-content/public-connectivity-best-practices/
scaleway.network.PublicGatewayDhcp | Pulumi Registry, accessed December 10, 2025, https://www.pulumi.com/registry/packages/scaleway/api-docs/network/publicgatewaydhcp/
Public Gateways - Concepts | Scaleway Documentation, accessed December 10, 2025, https://www.scaleway.com/en/docs/public-gateways/concepts/
