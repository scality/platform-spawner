# SSH Key Configuration

This platform supports SSH key configuration via Pulumi config for secure instance access.

**How it works:** 
- SSH keys are configured in two places:
  1. **Gateway Bastion**: SSH keys are automatically created as Scaleway IAM SSH keys, allowing access to the gateway bastion
  2. **Worker Nodes**: SSH keys are injected into instances via cloud-init as the `artesca-os` user with passwordless sudo
- The gateway bastion automatically refreshes SSH keys from Scaleway IAM on each deployment

## Setup for Local Development

### Single SSH Key

Configure your SSH public key:

```bash
# Set your SSH public key in Pulumi config (encrypted by default)
pulumi config set sshPublicKey "$(cat ~/.ssh/id_ed25519.pub)"
```

### Multiple SSH Keys

Configure multiple SSH keys (comma-separated):

```bash
# Set multiple SSH keys
pulumi config set sshPublicKeys "$(cat ~/.ssh/id_ed25519.pub),$(cat ~/.ssh/id_rsa.pub)"

# Or manually
pulumi config set sshPublicKeys "ssh-ed25519 AAAA...,ssh-rsa AAAA..."
```

You can use both `sshPublicKey` and `sshPublicKeys` together - all keys will be added.

## Setup for CI/CD

In your CI/CD pipeline (GitHub Actions, GitLab CI, etc.):

```bash
# Store SSH public key as an environment variable or secret
pulumi config set sshPublicKey "$SSH_PUBLIC_KEY" --stack your-stack
```

## Verifying Configuration

Check if SSH key is configured:

```bash
pulumi config get sshPublicKey
```

## Accessing Instances

After deployment:

```bash
# For all topologies (gateway bastion architecture)
GATEWAY_IP=$(pulumi stack output gateway_bastion_ip)

# Connect to gateway bastion (username is 'root' or your project username, port 61000)
ssh -p 61000 root@$GATEWAY_IP

# Or use as jump host to access private worker nodes
ssh -J root@${GATEWAY_IP}:61000 artesca-os@<NODE_PRIVATE_IP>

# Direct jump example
GATEWAY_IP=$(pulumi stack output gateway_bastion_ip)
NODE_IP=$(pulumi stack output --json | jq -r '.nodes["node-01"].private_ip')
ssh -J root@${GATEWAY_IP}:61000 artesca-os@$NODE_IP

# Switch to root if needed
sudo su -
```

**Important:** The platform creates an `artesca-os` user on worker nodes (not `root` or `admin`) with:
- Passwordless sudo access
- Member of the `wheel` group
- SSH key authentication enabled
- Multiple SSH keys supported`

**Note:** Gateway bastion SSH access uses Scaleway IAM SSH keys. The platform automatically creates these from your configured SSH keys. The gateway uses `root` or your Scaleway project-specific username for authentication, and connects on port `61000`.

## Security Notes

- SSH keys are stored encrypted in Pulumi config
- Never commit SSH keys to source control
- Use separate SSH keys for different environments (dev/staging/prod)
- In production, consider using SSH certificates or Bastion hosts

## Troubleshooting

If you can't SSH to instances:

1. **Check SSH key is configured:**
   ```bash
   pulumi config get sshPublicKey
   ```

2. **Verify the key was applied:**
   ```bash
   pulumi up --diff
   # Should show sshKeyIds in the instance configuration
   ```

3. **Check gateway bastion is configured:**
   - Gateway bastion feature should be enabled
   - Check with: `pulumi stack output gateway_bastion_ip`
   - Verify in Scaleway console that bastion is enabled on the gateway

4. **Try with verbose SSH:**
   ```bash
   ssh -v artesca-os@$GATEWAY_IP
   ```
   
5. **Gateway bastion access issues:**
   - Verify IAM SSH keys were created: `pulumi stack --show-urns | grep IamSshKey`
   - Check gateway has bastion enabled: `pulumi stack output --json | jq .network.gateway_id`
   - Try connecting with verbose: `ssh -v -p 61000 root@$GATEWAY_IP`
   - Gateway username is typically `root` (not `bastion` or your email)
   - Gateway SSH port is `61000` (not the default `22`)
