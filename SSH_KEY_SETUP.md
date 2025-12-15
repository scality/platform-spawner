# SSH Key Configuration

This platform supports SSH key configuration via Pulumi config for secure instance access.

**How it works:** When you configure SSH keys, they're automatically injected into instances via cloud-init as the `artesca-os` user with passwordless sudo. This approach works consistently across all cloud providers and doesn't require provider-specific IAM APIs.

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
# For single-node topology
PUBLIC_IP=$(pulumi stack output public_ip)
ssh artesca-os@$PUBLIC_IP

# For 3-node/6-node topology (bastion architecture)
BASTION_IP=$(pulumi stack output bastion_public_ip)
ssh artesca-os@$BASTION_IP

# From bastion, access internal nodes via private IPs
ssh artesca-os@<BOOTSTRAP_PRIVATE_IP>
ssh artesca-os@<NODE_PRIVATE_IP>

# Switch to root if needed
sudo su -
```

**Important:** The platform creates an `artesca-os` user (not `root` or `admin`) with:
- Passwordless sudo access
- Member of the `wheel` group
- SSH key authentication enabled
- Multiple SSH keys supported

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

3. **Check security group allows SSH:**
   - Port 22 should be open in the security group
   - Check with: `pulumi stack output`

4. **Try with verbose SSH:**
   ```bash
   ssh -v root@$PUBLIC_IP
   ```
