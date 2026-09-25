# Design Platform Spawner

## Goal

The goal of the Platform Spawner is to provide a flexible and efficient
way to create, manage, and destroy cloud resources using a declarative YAML-based configuration.
This will enable developers to easily define their infrastructure requirements and automate
the provisioning process, reducing the time and effort needed to manage cloud resources.

## Implementation Details

We support the AWS EC2 and the OpenStack providers, both behind the same
`BaseProvider` interface, and the architecture is designed to be extensible,
allowing for the addition of other cloud providers in the future.

The provider is picked by the `provider` configuration key, which keeps a stack
configuration portable from one cloud to another as long as the values it uses
exist on both.

### Provider differences

The interface hides most of the differences, a few of them remain visible from
a stack configuration:

- `instance_image` and `bastion_image` are resolved against the AMIs on AWS and
  against the Glance images on OpenStack. `rocky-9` is an alias on both, known
  on AWS in `eu-north-1` and `us-west-2` only. `rocky-8` is an alias on
  OpenStack alone. Any other value is looked up as it is given. On AWS, a
  value starting with `ami-` is taken as an id instead of a name, which is
  the only handle an image another account shared with us has.
- `instance_image_file` hands an image file over instead, uploaded on OpenStack
  only. AWS can do it, through an S3 bucket, a VM Import task and an account
  wide IAM role, and only from a VHD or a VMDK, which is enough work that the
  provider says it cannot rather than pretending. The image belongs to the
  stack and is uploaded again on every spawn, which is what makes it useful:
  it is handed over when the image itself is under test. The bastion is left
  out of it and keeps running `bastion_image`.
- `instance_flavor` maps to a `t3` instance type on AWS and to an OVH Public
  Cloud flavor on OpenStack, where it also decides the root disk size:

  | Flavor | AWS | OpenStack | OpenStack root disk |
  |--------|-----|-----------|---------------------|
  | small | `t3.small` | `d2-2` | 25 GB HDD |
  | medium | `t3.medium` | `d2-4` | 50 GB NVMe |
  | large | `t3.large` | `b3-8` | 50 GB NVMe |
  | xlarge | `t3.2xlarge` | `b3-32` | 200 GB NVMe |

  Anything outside that table is handed to the cloud as it is, so a flavor of
  its catalog can be asked for by name. Nothing then says how big the root
  disk will be on OpenStack, since the flavor is what decides it.

- `instance_root_disk_size` and `bastion_root_disk_size` are honoured on AWS,
  where the root volume of the AMI is simply resized, and ignored on
  OpenStack, where the instance boots on the local disk the flavor comes with.
  Sizing the root disk freely there would mean booting from a Block Storage
  volume, which the flavor's local disk gets billed on top of rather than
  instead of, so the flavor is the knob to reach for.
- Name resolution comes with the VPC on AWS and has to be handed out on
  OpenStack through `openstack_dns_nameservers`. Neutron otherwise leaves its
  DHCP agent to answer the queries, and whether that agent forwards them
  upstream is the cloud operator's call, which OVH has not made. The instances
  are also given a cloud-init snippet taking ownership of `/etc/resolv.conf`,
  since the images OVH publishes ship a stale one whose resolver is tried
  first and times out on every lookup.

The topology differs in shape for the same reason. A platform is one VPC
holding the three subnets on AWS, because the interfaces of an instance all
have to live in the same VPC, and one network per plane holding a single
subnet on OpenStack. A Neutron network is a broadcast domain where a VPC is a
routing one, so subnets sharing a network would sit on the same wire and
reach each other without ever crossing a router.

Each routed subnet also gets a router of its own rather than sharing one,
since a router carries traffic between everything it is plugged into. With
one router per plane, taking an interface down really does cut the machine
off that plane, which a shared router would quietly work around. The control
plane is routed nowhere and has no router at all.

That is also what `offline` adds and removes: the router of the workload
plane and its interface. The subnet itself never changes, which is what keeps
the switch from touching a single instance. Two things follow from it:

- A gateway address cannot be taken off a subnet while a router still holds
  it, and Pulumi runs its deletions last, so anything that removes the
  gateway as part of the switch deadlocks. The subnet keeps its gateway
  address at all times instead, whether or not a router answers there.
- While offline, the instances keep a default route pointing at an address
  nobody answers, so reaching out times out rather than failing outright. On
  AWS the route is simply absent and the failure is immediate.

> **Note**
> The OpenStack provider has been spawned against OVH Public Cloud, which
> confirmed the networks and their subnets, the security groups, the routers
> and their external gateway, the floating IP, the outbound traffic through
> SNAT, the traffic between instances, the resolvers, both values of
> `offline` and switching between them on a live platform without disturbing
> an instance. Taking an interface down was checked to cut the machine off
> that plane, on both the control and the workload plane.
>
> The extra volumes and the extra networks were confirmed the same way, with
> two volumes and two interfaces of one network on every instance.
>
> Still unconfirmed: the image aliases and every flavor but the one that was
> tried.
