# Design Platform Spawner

## Goal

The goal of the Platform Spawner is to provide a flexible and efficient
way to create, manage, and destroy cloud resources using a declarative YAML-based configuration.
This will enable developers to easily define their infrastructure requirements and automate
the provisioning process, reducing the time and effort needed to manage cloud resources.

## Implementation Details

For now we only support AWS EC2 provider but the architecture is designed to be extensible,
allowing for the addition of other cloud providers in the future.
