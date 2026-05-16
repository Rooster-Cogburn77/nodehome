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
| `/live restart ollama`         | `sudo -n /bin/systemctl restart ollama`    |

`/live restart …` does **not** execute the restart. It first validates the target environment. If the mutation cannot run locally (for example, a Windows-local session trying to queue the Linux-only `sudo -n /bin/systemctl restart ollama` argv), Nodechat prints `LIVE_MUTATION_REFUSED`, writes `live_mutation_refused`, and creates no approval row. Valid mutations queue an approval row (class `live-mutation`) with the resolved argv, print an `APPROVAL_REQUIRED` block, and write a `live_mutation_queued` audit event. The restart only runs after `/approve <id>`, which writes a `live_mutation_executed` (or `live_mutation_blocked`) event with exit code, executable, target, and the SHA256 of the captured output.

Host prerequisite for Ollama restart: the homelab operator account has a narrow NOPASSWD sudoers entry for exactly `/bin/systemctl restart ollama`. This was validated from the node with `sudo -n /bin/systemctl restart ollama` returning exit code `0`.

## Hard guardrails

- **No arbitrary container names.** Only `vllm-server` and `open-webui` are reachable via container-targeted diag ops and Docker restart mutations. Ollama restart is a fixed systemd argv, not a templated unit name.
- **No arbitrary journalctl units.** Only `ollama` is reachable via `/live journal …`.
- **No `--follow` / `-f`.** The diag allowlist is byte-for-byte fixed argv; no streaming options.
- **No shell composition.** Argv is passed directly to `subprocess.run` (or wrapped through `ssh -o BatchMode=yes <target> <shell-quoted command>` when `live_ssh` is set). No `&&`, `||`, `;`, `|`, or redirection.
- **No restart without `/approve`.** `/live restart …` is purely a queue action; the restart runs only when an explicit `/approve <id>` is issued in the same session.
- **No invalid local target.** Local mutations must be executable on the local host. Run Nodechat on the homelab for local Linux service mutations, or set `NODECHAT_LIVE_SSH` / `--live-ssh user@host` when starting Nodechat from Windows.
- **Audit queued vs executed separately.** `live_mutation_queued` records the proposed argv at queue time; `live_mutation_executed` (or `live_mutation_blocked`) records the actual outcome at approve time. Both rows include `op`, `argv`, `target`, `approval_id`, and `executable`.

## Targeting (local vs SSH)

Both diag and mutation ops use the same target plumbing as the read-only `/live` checks:

- Default: argv runs locally inside the Nodechat workspace.
- If `NODECHAT_LIVE_SSH` (or `--live-ssh user@host`) is set, the argv is wrapped as `ssh -o BatchMode=yes <user@host> <shell-quoted command>` and executed against the remote node. The `target` field on every audit row records `local` or `ssh:<user@host>` so the trail is unambiguous.

Windows launcher note: the normal Windows Nodechat path talks to the homelab model endpoint, but that does not make live mutations target the homelab. For `/live restart ollama` from Windows, start Nodechat with `--live-ssh bmoore_77@192.168.1.198` or run Nodechat directly on the homelab.

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

Chronological logs are tail-sensitive: `/live logs …` and `/live journal ollama` preserve the newest tail when the live-output cap is hit, so restart events and recent failures stay visible. Non-log diagnostics preserve the head when truncated.

## Future work

### Adding new mutations

Each new mutation must:

- Be reversible or recoverable (this iteration is restart-only — no deletes, no config writes).
- Have a fixed argv (no templated container names, no shell composition).
- Land with an entry in `LIVE_MUTATION_OPS`, an approval-reason string, an audit-trail test, and a row in this runbook.
- Stay subject to `/approve` — never auto-run.

Anything that would mutate the host filesystem, package state, network configuration, BMC settings, or stored credentials is out of scope for this lane.
