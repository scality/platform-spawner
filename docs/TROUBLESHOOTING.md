# Troubleshooting: Import & Re-run a CI Stack Locally

When a CI pipeline fails mid-deploy or you need to troubleshoot a running stack, you can import its state from S3 and operate on it locally.

> **IMPORTANT:** All `pulumi` commands must be run from the **project root**
> (the directory containing `Pulumi.yaml`). The local backend uses `file://./`
> which stores state relative to your working directory. Running commands from
> a subdirectory creates a separate, disconnected `.pulumi/` directory there.

## TL;DR — Quick Import

```bash
cd /path/to/platform-spawner       # MUST be the project root
export PULUMI_CONFIG_PASSPHRASE=''

STACK=hardware-appliance-single-node-3587   # change this
DEST=bucket/artesca/$STACK
mkdir -p "$DEST"

# 1. Download
S3_KEY="artesca-stacks/artesca/$STACK"
aws s3 cp "s3://$S3_KEY/stack_export.json"  "$DEST/stack_export.json"
aws s3 cp "s3://$S3_KEY/stack_output.json"  "$DEST/stack_output.json"
aws s3 cp "s3://$S3_KEY/stack_config.yaml"  "$DEST/stack_config.yaml" 2>/dev/null || true

# 2. Import
pulumi stack init $STACK
pulumi stack import --file $DEST/stack_export.json

# 3. Restore config
python3 scripts/restore_config.py $DEST

# 4. Set credentials & verify
export SCW_ACCESS_KEY='...'
export SCW_SECRET_KEY='...'
export SCW_DEFAULT_PROJECT_ID='...'
pulumi config
pulumi refresh
pulumi preview
```

## Prerequisites

- Pulumi CLI installed
- AWS CLI configured with Scaleway Object Storage credentials
- Access to the Pulumi state S3 bucket
- Scaleway API credentials (access key + secret key)

## Step 1: Configure AWS CLI for Scaleway S3

The Pulumi state is stored in a Scaleway Object Storage bucket. Your `~/.aws/config` may point to a bucket-specific endpoint, but you need the **general** Scaleway S3 endpoint to access the state bucket.

Ensure your `~/.aws/config` contains all required configuration:

```config
[default]
region = fr-par
output = json
services = scw-fr-par

[services scw-fr-par]
s3 =
  endpoint_url = https://s3.fr-par.scw.cloud
  max_concurrent_requests = 100
  max_queue_size = 1000
  multipart_threshold = 50 MB
  # Edit the multipart_chunksize value according to the file sizes that you
  # want to upload. The present configuration allows to upload files up to
  # 10 GB (1000 requests * 10 MB). For example, setting it to 5 GB allows you
  # to upload files up to 5 TB.
  multipart_chunksize = 10 MB

s3api =
  endpoint_url = https://s3.fr-par.scw.cloud
```

> **Important:** If you have the error `NoSuchKey`, pass `--endpoint-url https://s3.fr-par.scw.cloud` when accessing this bucket.

Test access:

```bash
aws s3 ls s3://<BUCKET>/
```

You should see:

```
PRE .pulumi/
PRE <project>/
```

## Step 2: List Available Stacks

```bash
aws s3 ls <BUCKET>
```

## Step 3: Download the Full Pulumi State

Download all state files to your local Pulumi backend:

```bash
aws s3 cp --recursive \
    s3://<BUCKET> ~/bucket/
```

Download the three files for the stack you want to import:

```bash
STACK=<STACK_NAME>
S3_KEY="<BUCKET>/$STACK"

S3_KEY="artesca-stacks/artesca/$STACK"
aws s3 cp "s3://$S3_KEY/stack_export.json"  "$DEST/stack_export.json"
aws s3 cp "s3://$S3_KEY/stack_output.json"  "$DEST/stack_output.json"
aws s3 cp "s3://$S3_KEY/stack_config.yaml"  "$DEST/stack_config.yaml" 2>/dev/null || true
```

The three files:
- **stack_export.json** — full Pulumi resource state (used by `pulumi stack import`)
- **stack_output.json** — stack outputs (network info, SSH config, etc.)
- **stack_config.yaml** — the `Pulumi.<stack>.yaml` config file from CI (may not exist for older stacks)

## Step 4: Import State and Restore Config

> **All commands below must run from the project root (where `Pulumi.yaml` is).**

```bash
cd /path/to/platform-spawner      # project root
export PULUMI_CONFIG_PASSPHRASE=''   # CI uses an empty passphrase
```

### 4a. Create the stack and import state

```bash
pulumi stack init $STACK
pulumi stack import --file $DEST/stack_export.json
```

Validate the import:

```bash
# Resource counts should match
jq '.deployment.resources | length' $DEST/stack_export.json
pulumi stack export --show-secrets | jq '.deployment.resources | length'
```

### 4b. Restore config

The helper script `scripts/restore_config.py` restores the stack config
(`Pulumi.<STACK>.yaml`). Pass the download directory as an argument:

```bash
python3 scripts/restore_config.py $DEST
```

The script tries three sources in order:

```bash
pulumi config rm authorized_cidrs 2>/dev/null || true
MY_IP=$(curl -s https://ifconfig.me)/32
pulumi config set --path 'authorized_cidrs[0]' "$MY_IP"
```

Or to add multiple CIDRs:

```bash
pulumi config rm authorized_cidrs 2>/dev/null || true
pulumi config set --path 'authorized_cidrs[0]' "$(curl -s https://ifconfig.me)/32"
pulumi config set --path 'authorized_cidrs[1]' "<additional_cidr>"
```

3. **Imported state** (last resort) — extracts config from the stack resource
   outputs in the imported state.

### 4c. Set Scaleway credentials

```bash
export SCW_ACCESS_KEY='<ACCESS_KEY>'
export SCW_SECRET_KEY='<SECRET_KEY>'
export SCW_DEFAULT_PROJECT_ID='<PROJECT_ID>'
```

### 4d. Verify config

```bash
pulumi config
```

You should see all required keys populated — including `project_id`,
`instance_count`, `product`, `instance_flavor`, `extra_private_networks`,
and `extra_volumes`.

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
| List S3 stacks | `aws s3 ls s3://<BUCKET>/.pulumi/stacks/platform-spawner/ --endpoint-url https://s3.fr-par.scw.cloud` |
| Download all state | `aws s3 cp --recursive s3://<BUCKET>/.pulumi/ ~/.pulumi/ --endpoint-url https://s3.fr-par.scw.cloud` |
| List local stacks | `pulumi stack ls` |
| Sync with cloud | `pulumi refresh --yes` |
| Remove stale resource | `pulumi state delete --yes '<URN>'` |
| Preview changes | `pulumi preview` |
| Deploy | `pulumi up` |
| Tear down | `pulumi destroy` |
| Get your public IP | `curl -s https://ifconfig.me` |
