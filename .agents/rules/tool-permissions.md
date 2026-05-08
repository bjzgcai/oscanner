# Tool Permission Notes

The legacy Claude local settings allowed:
- `curl`
- SSH connectivity checks to the production host using `~/.ssh/wu.pem`

Codex tool permissions are controlled by the active session policy, not by this file. Treat these as project-specific expected operations and only run them when the current session permits it.
