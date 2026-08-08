# ScaleTail DERP Notes

The current Compose stack uses the DERP server embedded in Headscale-Admin-AE. It no longer deploys a standalone third-party derper. DERP relays end-to-end encrypted packets only when peers cannot establish a direct connection.

## Deployment constraints

- `DERP_DOMAIN` must resolve to the Headscale host and use trusted TLS.
- `DERP_STUN_PORT` defaults to UDP `3478` and must be allowed by the host and upstream firewall.
- Registered-client verification remains enabled. Do not use `insecurefortests` or disable client verification to hide certificate or enrollment failures.
- Never expose the ScaleForge management or client-report Unix sockets to the public network.

## Verification

Run these commands on a ScaleTail node that has completed account-password login:

```bash
scaletail netcheck
scaletail ping <peer ScaleTail IP>
```

See the [root README](../README.md) for account login, private Unix sockets, deployment, and upgrade instructions.
