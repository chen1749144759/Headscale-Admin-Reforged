# ScaleForge Documentation

This historical translation has been retired for security reasons. Its former registration flow and client commands do not match the current account-and-password architecture.

The authoritative documentation is the [root README](../README.md). It covers architecture, login, private Unix sockets, CAPTCHA, DNS, signed OTA updates, database migrations, deployment, and upgrades.

New clients sign in with `scaletail login --username ...`. Automation must use a `0600` password file through `--password-file`.
