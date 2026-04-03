#!/usr/bin/env python3
"""Restore Pulumi stack config from downloaded files or imported state.

Usage:
    PULUMI_CONFIG_PASSPHRASE='' python3 scripts/restore_config.py <download-dir>

    <download-dir>  Directory containing the downloaded S3 files
                    (stack_config.yaml, stack_output.json, stack_export.json).
                    Defaults to current directory.

The script must be run from the project root (where Pulumi.yaml lives).

It tries three sources in order:
  1. stack_config.yaml   — the Pulumi config file exported by CI (best source)
  2. stack_output.json   — stack outputs contain a 'config' dict + network info
  3. Imported state      — reads config from stack resource outputs (last resort)
"""
import json
import subprocess
import os
import sys
import shutil


# Keys that are computed/read-only — not settable as config
SKIP_KEYS = {"instance_type", "bastion_instance_type", "provider", "region", "zone"}
# Type hints for pulumi config set
INT_KEYS = {"instance_count", "instance_root_disk_size", "bastion_root_disk_size"}
BOOL_KEYS = {"offline", "disable_auto_stop", "authorized_icmp", "ssh_private_key_create"}
# Keys whose values are lists/objects and must be set as JSON strings
JSON_KEYS = {
    "authorized_cidrs", "authorized_tcp_ports", "authorized_udp_ports",
    "custom_routes", "extra_volumes", "extra_private_networks",
    "ssh_public_keys",
}


def _set_config_keys(stack: str, config: dict) -> int:
    """Run 'pulumi config set' for each key in config. Returns count of keys set."""
    cmds = []
    for key, value in config.items():
        if key in SKIP_KEYS:
            continue

        if key in JSON_KEYS:
            if not value:
                continue
            cmds.append(["pulumi", "config", "set", key, json.dumps(value)])
        elif key in INT_KEYS:
            cmds.append(["pulumi", "config", "set", "--type", "int", key, str(value)])
        elif key in BOOL_KEYS:
            cmds.append(["pulumi", "config", "set", "--type", "bool", key, str(value).lower()])
        else:
            if value == "" or value is None:
                continue
            cmds.append(["pulumi", "config", "set", key, str(value)])

    print(f"Restoring {len(cmds)} config keys for stack '{stack}'...")
    for cmd in cmds:
        label = " ".join(cmd[2:])
        print(f"  {label}")
        subprocess.run(cmd, check=True)

    return len(cmds)


def _extract_extra_networks(stack_output: dict) -> list:
    """Extract extra_private_networks from stack_output.json network info."""
    nets = stack_output.get("network", {}).get("extra_networks", {})
    result = []
    for suffix, net_info in nets.items():
        if isinstance(net_info, dict) and "subnet" in net_info:
            result.append({"suffix": suffix, "subnet": net_info["subnet"]})
    return result


def _extract_extra_volumes(stack_output: dict) -> list:
    """Infer extra_volumes config from node volume data in stack_output.json.

    Examines the first node's volumes, groups by suffix pattern, and
    reconstructs the extra_volumes config entries.
    Volume names follow: {product}-node-NN-{suffix} or {product}-node-NN-{suffix}-NN
    """
    nodes = stack_output.get("nodes", {})
    if not nodes:
        return []

    # Use the first node's volumes as reference
    first_node = next(iter(nodes.values()))
    volumes = first_node.get("volumes", [])
    if not volumes:
        return []

    # Group volumes by base suffix (strip trailing -NN index)
    # e.g. "product-node-01-data-01" -> suffix="data", "product-node-01-service" -> suffix="service"
    node_name = first_node.get("name", "")
    prefix = f"{node_name}-" if node_name else ""

    groups: dict[str, dict] = {}  # suffix -> {"size": int, "count": int}
    for vol in volumes:
        vol_name = vol.get("name", "")
        size_gb = vol.get("size_gb", 0)

        # Strip the node name prefix to get the suffix part
        if prefix and vol_name.startswith(prefix):
            remainder = vol_name[len(prefix):]
        else:
            continue

        # Strip trailing -NN index if present (e.g. "data-01" -> "data")
        parts = remainder.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            base_suffix = parts[0]
        else:
            base_suffix = remainder

        if base_suffix in groups:
            groups[base_suffix]["count"] += 1
        else:
            groups[base_suffix] = {"suffix": base_suffix, "size": size_gb, "count": 1}

    return list(groups.values())


def _extract_project_id_from_export(source_dir: str, filename: str = "stack_export.json") -> str | None:
    """Extract project_id from the provider resource in stack_export.json."""
    filepath = os.path.join(source_dir, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath) as f:
        state = json.load(f)
    resources = state.get("deployment", {}).get("resources", [])
    for res in resources:
        if res.get("type") == "pulumi:providers:scaleway":
            return (
                res.get("outputs", {}).get("projectId")
                or res.get("inputs", {}).get("projectId")
            )
    return None


def _find_project_root() -> str:
    """Find the directory containing Pulumi.yaml (project root)."""
    # Start from cwd and walk up
    path = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(path, "Pulumi.yaml")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    # Fallback: ask pulumi for the project root via about
    return os.getcwd()


def restore_from_config_yaml(stack: str, source_dir: str, project_root: str) -> bool:
    """Copy stack_config.yaml to Pulumi.<stack>.yaml in the project root."""
    src = os.path.join(source_dir, "stack_config.yaml")
    if not os.path.exists(src):
        return False

    dest = os.path.join(project_root, f"Pulumi.{stack}.yaml")
    shutil.copy2(src, dest)
    print(f"Restored config from {src} -> {dest}")
    return True


def restore_from_stack_output(stack: str, source_dir: str) -> bool:
    """Recover config from stack_output.json. Returns True on success."""
    filepath = os.path.join(source_dir, "stack_output.json")
    if not os.path.exists(filepath):
        return False

    with open(filepath) as f:
        stack_output = json.load(f)

    config = stack_output.get("config", {})
    if not config:
        print("WARNING: No 'config' key in stack_output.json.")
        return False

    # Supplement missing keys from other sections of stack_output.json
    # (for stacks created before the full config export was added)
    if "project_id" not in config or not config["project_id"]:
        pid = _extract_project_id_from_export(source_dir)
        if pid:
            config["project_id"] = pid

    if "extra_private_networks" not in config or not config["extra_private_networks"]:
        extra_nets = _extract_extra_networks(stack_output)
        if extra_nets:
            config["extra_private_networks"] = extra_nets

    if "extra_volumes" not in config or not config["extra_volumes"]:
        extra_vols = _extract_extra_volumes(stack_output)
        if extra_vols:
            config["extra_volumes"] = extra_vols

    count = _set_config_keys(stack, config)
    if count:
        print(f"\nDone. Verify with: pulumi config")
    return count > 0


def restore_from_state(stack: str) -> bool:
    """Recover config from imported stack state outputs (last resort)."""
    raw = subprocess.check_output(
        ["pulumi", "stack", "export", "--show-secrets"], text=True
    )
    state = json.loads(raw)
    resources = state.get("deployment", {}).get("resources", [])
    if not resources:
        print("ERROR: No resources in state. Did you run 'pulumi stack import'?")
        return False

    stack_outputs = resources[0].get("outputs", {})
    config = stack_outputs.get("config", {})
    if not config:
        print("WARNING: No 'config' in stack outputs — state may be from an older version.")
        return False

    count = _set_config_keys(stack, config)
    if count:
        print(f"\nDone. Verify with: pulumi config")
    return count > 0


def main():
    # Determine source directory (arg or cwd)
    if len(sys.argv) > 1:
        source_dir = os.path.abspath(sys.argv[1])
    else:
        source_dir = os.getcwd()

    if not os.path.isdir(source_dir):
        print(f"ERROR: {source_dir} is not a directory")
        sys.exit(1)

    project_root = _find_project_root()
    if not os.path.exists(os.path.join(project_root, "Pulumi.yaml")):
        print(f"ERROR: Cannot find Pulumi.yaml. Run this from the project root.")
        sys.exit(1)

    stack = subprocess.check_output(
        ["pulumi", "stack", "--show-name"], text=True
    ).strip()

    print(f"Stack: {stack}")
    print(f"Source: {source_dir}")
    print(f"Project root: {project_root}")
    print()

    # 1. Prefer the config YAML file (complete and authoritative)
    if restore_from_config_yaml(stack, source_dir, project_root):
        return

    # 2. Try stack_output.json (always uploaded by CI, contains config dict)
    print("stack_config.yaml not found, trying stack_output.json...")
    if restore_from_stack_output(stack, source_dir):
        return

    # 3. Last resort: extract from imported state
    print("stack_output.json not found or empty, falling back to imported state...")
    if not restore_from_state(stack):
        print("\nFailed to restore config. Download files from S3:")
        print(f"  aws s3 cp s3://<bucket>/<project>/<stack>/stack_config.yaml stack_config.yaml \\")
        print(f"    --endpoint-url <s3_endpoint>")
        sys.exit(1)


if __name__ == "__main__":
    main()
