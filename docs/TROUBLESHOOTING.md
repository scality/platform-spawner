# Troubleshooting: Import & Re-run a CI Stack Locally

When a CI pipeline fails mid-deploy or you need to troubleshoot a running stack, you can import its state from S3 and operate on it locally.

## Prerequisites

- Pulumi CLI installed
- AWS CLI configured with Scaleway Object Storage credentials
- Access to the `artesca-stacks` S3 bucket
- Scaleway API credentials (access key + secret key)

## Step 1: Configure AWS CLI for Scaleway S3

The Pulumi state is stored in a Scaleway Object Storage bucket. Your `~/.aws/config` may point to a bucket-specific endpoint, but you need the **general** Scaleway S3 endpoint to access `artesca-stacks`.

> **Important:** Always pass `--endpoint-url https://s3.fr-par.scw.cloud` when accessing this bucket, or it will fail with `NoSuchKey`.

Test access:

```bash
aws s3 ls s3://artesca-stacks/ --endpoint-url https://s3.fr-par.scw.cloud
```

You should see:

```
PRE .pulumi/
PRE artesca/
```

## Step 2: List Available Stacks

```bash
aws s3 ls s3://artesca-stacks/.pulumi/stacks/platform-spawner/ \
    --endpoint-url https://s3.fr-par.scw.cloud
```

Example output:

```
2026-02-27 10:32:55     134996 single-node-20438.json
2026-02-27 10:32:55     150489 single-node-20438.json.bak
```

## Step 3: Download the Full Pulumi State

Download all state files to your local Pulumi backend:

```bash
aws s3 cp --recursive \
    s3://artesca-stacks/.pulumi/ ~/.pulumi/ \
    --endpoint-url https://s3.fr-par.scw.cloud
```

Or download only a specific stack:

```bash
aws s3 cp \
    s3://artesca-stacks/.pulumi/stacks/platform-spawner/<STACK_NAME>.json \
    ~/.pulumi/stacks/platform-spawner/<STACK_NAME>.json \
    --endpoint-url https://s3.fr-par.scw.cloud
```

Verify the stacks are visible:

```bash
pulumi stack ls
```

## Step 4: Select the Stack and Initialize Config

```bash
pulumi stack select <STACK_NAME>
```

If the stack doesn't exist locally yet, create it first:

```bash
pulumi stack init <STACK_NAME>
```

### Extract Configuration from State

The CI stack state contains all the configuration values used during deployment. You can extract them with:

```bash
python3 << 'PYEOF'
import json, os

STACK_NAME = "single-node-20438"  # <-- change this
state_file = os.path.expanduser(
    f"~/.pulumi/stacks/platform-spawner/{STACK_NAME}.json"
)

with open(state_file) as f:
    data = json.load(f)

latest = data.get("latest", data.get("checkpoint", {}).get("latest", data))

for r in latest.get("resources", []):
    if r.get("type") == "pulumi:providers:scaleway":
        print(f"ACCESS_KEY: {r['inputs'].get('accessKey')}")
        print(f"SECRET_KEY: {r['inputs'].get('secretKey')}")
        print(f"PROJECT_ID: {r['inputs'].get('projectId')}")
    if r.get("type") == "pulumi:pulumi:Stack":
        config = r.get("outputs", {}).get("config", {})
        for k, v in config.items():
            print(f"CONFIG {k}: {v}")
PYEOF
```

### Set Configuration

Use the extracted values to configure the stack:

```bash
export PULUMI_CONFIG_PASSPHRASE=""   # or your passphrase

# Required: Scaleway credentials
pulumi config set project_id <PROJECT_ID>
pulumi config set --secret scaleway:accessKey <ACCESS_KEY>
pulumi config set --secret scaleway:secretKey <SECRET_KEY>

# Instance config (adapt values from extraction output)
pulumi config set product <PRODUCT_NAME>
pulumi config set instance_count <COUNT>
pulumi config set instance_flavor <FLAVOR>
pulumi config set instance_image <IMAGE>
pulumi config set instance_snapshot <SNAPSHOT_UUID>
pulumi config set instance_root_disk_size <SIZE>

# Bastion config
pulumi config set bastion_flavor <FLAVOR>

# Region
pulumi config set region fr-par
pulumi config set zone fr-par-1

# Lifecycle
pulumi config set disable_auto_stop true

# Extra volumes (if any)
pulumi config set extra_volumes '[{"suffix": "service", "size": 120, "count": 1}, {"suffix": "data", "size": 10, "count": 12}]'

# Extra private networks (if any)
pulumi config set extra_private_networks '[{"suffix": "data", "subnet": "192.168.20.0/24"}]'

# Authorized CIDRs - replace __my_ip__ placeholder with actual CIDRs
pulumi config set --path 'authorized_cidrs[0]' '141.94.181.72/32'
pulumi config set --path 'authorized_cidrs[1]' '84.14.13.200/29'
# ... add more as needed
```

> **Note:** The CI uses `__my_ip__` as a placeholder that gets replaced automatically. When running locally, you must replace it with your actual public IP (e.g., `$(curl -s https://ifconfig.me)/32`).

## Step 5: Refresh State Against Cloud

Before making changes, sync the Pulumi state with actual Scaleway resources. Some resources may have been deleted or modified since the CI ran.

```bash
pulumi refresh --yes
```

This will:
- Remove resources from state that no longer exist in Scaleway
- Update state for resources that drifted from expected configuration
- Report which resources were deleted, updated, or unchanged

## Step 6: Fix Stale Resources (if needed)

If `pulumi refresh` or `pulumi preview` reports errors about missing resources (e.g., `resource ... is not found`), remove them from state:

```bash
pulumi state delete --yes '<RESOURCE_URN>'
```

Common stale resources after a failed CI teardown:
- Bastion server (was being deleted when CI interrupted)
- Private NICs attached to deleted servers
- Gateway resources

## Step 7: Deploy

```bash
# Preview changes first
pulumi preview

# Apply
pulumi up
```

## Step 8: Destroy When Done

```bash
pulumi destroy
pulumi stack rm <STACK_NAME>
```

---

## Import from JSON Export (Alternative)

If you have a Pulumi JSON export file (e.g., from `pulumi stack export`) rather than the S3 backend, the file format may differ.

### Checkpoint vs Deployment Format

The S3 backend stores state in **checkpoint** format (has `checkpoint.latest` wrapper), but `pulumi stack import` expects **deployment** format. Convert it:

```bash
python3 << 'PYEOF'
import json

INPUT = "my-stack-export.json"      # <-- change this
OUTPUT = "my-stack-converted.json"  # <-- output file

with open(INPUT) as f:
    data = json.load(f)

if "checkpoint" in data:
    deployment = data["checkpoint"].get("latest", {})
    output = {"version": data["version"], "deployment": deployment}
elif "deployment" in data:
    output = data  # already in correct format
else:
    raise ValueError("Unrecognized format: expected 'checkpoint' or 'deployment' key")

with open(OUTPUT, "w") as f:
    json.dump(output, f, indent=4)

print(f"Converted: {len(deployment.get('resources', []))} resources")
PYEOF
```

Then import:

```bash
pulumi stack init <STACK_NAME>
pulumi stack import --file my-stack-converted.json
```

> **Note:** Pending operations (e.g., interrupted deletes) are automatically stripped during import.

---

## Quick Reference

| Task | Command |
|------|---------|
| List S3 stacks | `aws s3 ls s3://artesca-stacks/.pulumi/stacks/platform-spawner/ --endpoint-url https://s3.fr-par.scw.cloud` |
| Download all state | `aws s3 cp --recursive s3://artesca-stacks/.pulumi/ ~/.pulumi/ --endpoint-url https://s3.fr-par.scw.cloud` |
| List local stacks | `pulumi stack ls` |
| Sync with cloud | `pulumi refresh --yes` |
| Remove stale resource | `pulumi state delete --yes '<URN>'` |
| Preview changes | `pulumi preview` |
| Deploy | `pulumi up` |
| Tear down | `pulumi destroy` |
| Get your public IP | `curl -s https://ifconfig.me` |
