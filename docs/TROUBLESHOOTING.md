# Troubleshooting

## The SSH files are gone

A spawn writes the `ssh_config`, the `known_hosts` and, when it generated one,
the SSH key, where it ran. Another machine, or the same one after a clean up,
has nothing left to reach the platform with. Write them out of the stack:

```bash
uv run tools/get_ssh_config.py
```

Everything it needs is in the stack. The addresses and the users are exported,
and so is the key a spawn generated, as a secret. Nothing deployed is read or
touched, so this works just as well on a platform someone else spawned.

A platform running on a key of your own is reported as such. That key is yours
to point at.
