# Nodechat Live Mutations

Status: first iteration of the broader-operator-approvals lane. `/live` now exposes a small allowlist of read-only diagnostics and approval-gated mutations against the Nodehome services. Authoritative scope: [`nodechat-scope.md`](nodechat-scope.md). Routine usage: [`nodechat-terminal.md`](nodechat-terminal.md).

## Surface

### Read-only diagnostics (Observe tier — run immediately)

| Slash command            | Underlying argv                                                  |
|--------------------------|------------------------------------------------------------------|
| `/live ps`               | `docker ps -a`                                                   |
| `/live logs vllm`        | `docker logs --tail 200 vllm-server`                             |
| `/live logs open-webui`  | `docker logs --tail 200 open-webui`                              |
| `/live logs ollama`      | (alias of `/live journal ollama`)                                |
| `/live journal ollama`   | `journalctl -u ollama --no-pager -n 200`                         |
| `/live inspect vllm`     | `docker inspect vllm-server`                                     |
| `/live inspect open-webui` | `docker inspect open-webui`                                    |

Aliases: `vllm` ↔ `vllm-server`, `webui` ↔ `open-webui`.

Each diag run injects a `LIVE_NODE_STATUS` block with command, target (`local` or `ssh:<user@host>`), exit code, executable provenance, and bounded output. Audit event: `live_diag_executed`.

### Mutations (Mutate tier — queue for `/approve`)

| Slash command                  | Underlying argv                            |
|--------------------------------|--------------------------------------------|
| `/live restart vllm-server`    | `docker restart vllm-server`               |
| `/live restart open-webui`     | `docker restart open-webui`                |

`/live restart …` does **not** execute the restart. It queues an approval row (class `live-mutation`) with the resolved argv, prints an `APPROVAL_REQUIRED` block, and writes a `live_mutation_queued` audit event. The restart only runs after `/approve <id>`, which writes a `live_mutation_executed` (or `live_mutation_blocked`) event with exit code, executable, target, and the SHA256 of the captured output.

### Deferred mutations (refused with a pointer)

| Slash command          | Reason                                                                                                |
|------------------------|--------------------------------------------------------------------------------------------------------|
| `/live restart ollama` | Needs `sudo systemctl restart ollama`. Refused until the NOPASSWD sudoers entry below is installed.    |

A refusal prints a `LIVE_MUTATION_REFUSED` block, writes a `live_mutation_refused` audit event, and adds a context block tagged `manual-live-refused` so the chat surface knows the action did not run.

## Hard guardrails

- **No arbitrary container names.** Only `vllm-server` and `open-webui` are reachable via `/live` mutations or container-targeted diag ops.
- **No arbitrary journalctl units.** Only `ollama` is reachable via `/live journal …`.
- **No `--follow` / `-f`.** The diag allowlist is byte-for-byte fixed argv; no streaming options.
- **No shell composition.** Argv is passed directly to `subprocess.run` (or wrapped through `ssh -o BatchMode=yes <target> <shell-quoted command>` when `live_ssh` is set). No `&&`, `||`, `;`, `|`, or redirection.
- **No restart without `/approve`.** `/live restart …` is purely a queue action; the restart runs only when an explicit `/approve <id>` is issued in the same session.
- **Audit queued vs executed separately.** `live_mutation_queued` records the proposed argv at queue time; `live_mutation_executed` (or `live_mutation_blocked`) records the actual outcome at approve time. Both rows include `op`, `argv`, `target`, `approval_id`, and `executable`.

## Targeting (local vs SSH)

Both diag and mutation ops use the same target plumbing as the read-only `/live` checks:

- Default: argv runs locally inside the Nodechat workspace.
- If `NODECHAT_LIVE_SSH` (or `--live-ssh user@host`) is set, the argv is wrapped as `ssh -o BatchMode=yes <user@host> <shell-quoted command>` and executed against the remote node. The `target` field on every audit row records `local` or `ssh:<user@host>` so the trail is unambiguous.

`live_root` is **not** prepended for the new ops — they are system-level commands (`docker`, `journalctl`), not repo-relative scripts. The fixed `health` check still uses `cd ~/nodehome && ./scripts/healthcheck.sh` because it is repo-relative.

## Operator workflow

The intended workflow for a service hiccup:

```text
/live ps                      # what's running
/live logs vllm               # see the recent failure mode
/live inspect vllm            # confirm restart policy / current state
/live restart vllm-server     # queue the restart -- prints APPROVAL_REQUIRED a1
/approve a1                   # actually restart
/live ps                      # verify the container is Up again
```

Every step writes an audit row under `%USERPROFILE%\.nodehome\nodechat\audit\nodechat-audit.jsonl`. `/audit 20` will show the diag → queued → executed chain with op names and argv.

## Future work

### Enabling `/live restart ollama`

Two things need to happen on the homelab node before the deferred entry can be promoted:

1. **Install a narrow NOPASSWD sudoers entry** at `/etc/sudoers.d/nodechat-live`:

   ```sudoers
   # Allow the nodechat operator to restart only the ollama systemd unit
   # without a password. No other systemctl verbs, no other units.
   bmoore_77 ALL=(root) NOPASSWD: /bin/systemctl restart ollama
   ```

   Validate with `sudo -n systemctl restart ollama` from the operator account; the command must succeed without a password prompt and with no other systemctl verbs reachable.

2. **Promote the entry in `LIVE_MUTATION_OPS`:**

   ```python
   "restart ollama": {
       "description": "Restart the ollama systemd service",
       "argv": ["sudo", "-n", "systemctl", "restart", "ollama"],
       "approval_reason": "approved live-mutation: sudo systemctl restart ollama",
   },
   ```

   And remove the corresponding entry from `LIVE_DEFERRED_MUTATIONS`. Add a regression test that asserts `/live restart ollama` queues with the `sudo -n` argv.

Until both are in place, `/live restart ollama` stays in `LIVE_DEFERRED_MUTATIONS` and the refusal path is exercised by the safety suite.

### Adding new mutations

Each new mutation must:

- Be reversible or recoverable (this iteration is restart-only — no deletes, no config writes).
- Have a fixed argv (no templated container names, no shell composition).
- Land with an entry in `LIVE_MUTATION_OPS`, an approval-reason string, an audit-trail test, and a row in this runbook.
- Stay subject to `/approve` — never auto-run.

Anything that would mutate the host filesystem, package state, network configuration, BMC settings, or stored credentials is out of scope for this lane.
