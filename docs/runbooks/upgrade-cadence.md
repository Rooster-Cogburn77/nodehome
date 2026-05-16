# Stack Upgrade Cadence and Version Pinning Policy

**Status:** Active policy, last reviewed 2026-05-16 (Session 24).

Covers the three components on this stack that ship rapidly and require deliberate version management: Ollama, vLLM, and Open WebUI. Plus the underlying llama.cpp which Ollama embeds.

The point of this doc is to avoid two failure modes:
1. **Stale pinning** — running a version far behind upstream because no one re-evaluated whether to upgrade. Misses fixes, security improvements, performance work.
2. **Silent drift on rolling tags** — running a tag like `:main` that floats, so the version in production changes whenever Docker pulls fresh, without an explicit operator decision.

The policy below sets explicit pins where possible and a monthly review cadence to evaluate moves.

---

## Current pins and rolling tags

| Component | Currently pinned/running | Latest upstream as of 2026-05-11 | Status |
|---|---|---|---|
| Ollama (host systemd service) | `v0.23.2` (install-script auto-latest as of 2026-05-09) | `v0.30.0-rc12` shipping | **Behind, deserves review** |
| vLLM (Docker container) | `vllm/vllm-openai:v0.19.1` | v0.20.x, v0.21.x on watch list | Behind, hold for now |
| Open WebUI (Docker container) | `ghcr.io/open-webui/open-webui:v0.9.5` | `v0.9.5` shipped 2026-05-10 | Pinned |
| llama.cpp | Whatever ships in Ollama v0.23.2 | b9103 shipping | N/A — managed by Ollama |

## Policy

### Pin to explicit versions, not rolling tags

For each containerized component, use a specific version tag in the `docker run` / `docker compose` config, not a rolling tag like `:main` or `:latest`. The operator decides when to upgrade; Docker doesn't decide for them on the next image pull.

**Specifically:**
- Open WebUI: pinned to `ghcr.io/open-webui/open-webui:v0.9.5` on 2026-05-16. Use the current reviewed stable tag at the next approved upgrade.
- vLLM: already pinned to `v0.19.1`. Good.
- Ollama: install script auto-pulls latest at install time. No "pin" concept; instead, track which version was installed and evaluate when to re-run the install script.

### Monthly upstream review

On the first of each month, review release notes for:
- **Ollama** — https://github.com/ollama/ollama/releases
- **vLLM** — https://github.com/vllm-project/vllm/releases
- **Open WebUI** — https://github.com/open-webui/open-webui/releases
- **llama.cpp** — only if a specific release is called out by a sweep digest as multi-GPU / CUDA relevant; otherwise managed transitively by Ollama.

For each, ask:
1. Are there security fixes that matter for this deployment?
2. Are there bugfixes that match an issue actually observed on this stack?
3. Are there features that unlock a real workflow on this stack?
4. Are there breaking changes that would require config or behavior changes on this stack?

If yes to any of (1)/(2)/(3) and (4) is manageable, upgrade. Otherwise hold.

### Upgrade triggers between monthly reviews

Upgrade before the next scheduled review if:
- A security advisory is published against the currently-running version (CVE-level severity).
- An observed bug on this stack has a known-fixed-in version upstream.
- A feature this build genuinely needs is in a new release (e.g., Ollama gaining a model format the build wants to run).

Do not upgrade between reviews just because a new version shipped.

### Upgrade procedure (general)

1. Note the current version somewhere reversible. For Docker: `docker inspect <container> | grep Image`. For Ollama: `ollama --version`.
2. Pull the new image / install the new version.
3. Stop the old container; recreate with the new image (preserve the named volume so DB state survives).
4. For Ollama: re-run `curl -fsSL https://ollama.com/install.sh | sh`. The install script handles version transitions.
5. Run `./scripts/healthcheck.sh` to verify the stack came back clean.
6. Run a real workload (Open WebUI chat against both vLLM and Ollama models) to verify Option C still routes.
7. If anything is broken: rollback by re-pulling the previous version tag.
8. Update `docs/CURRENT_STATE.md` to reflect the new version.

## Recorded upgrades

(Add entries here as upgrades land.)

### 2026-05-09 — Ollama installed at v0.23.2
- Install script auto-pulled latest at install time; matches the pin update recorded in Session 13 / CURRENT_STATE.md.

### 2026-05-09 — vLLM pulled v0.19.1
- Deliberate pin choice; running in Docker since Session 14.

### 2026-05-09 — Open WebUI pulled `:main`
- Rolling tag, not version-pinned. Whatever was on `main` at pull time. **Action item: re-pull to `:v0.9.5` and update the tag in the run command** to convert this from drifting-on-rolling-tag to explicitly-pinned.

### 2026-05-16 — Open WebUI pinned to v0.9.5
- Recreated `open-webui` from `ghcr.io/open-webui/open-webui:v0.9.5` with the existing `open-webui:/app/backend/data` volume, port `3000:8080`, `host.docker.internal:host-gateway`, `OLLAMA_BASE_URL=http://host.docker.internal:11434`, and restart policy `unless-stopped`.
- Verified `docker ps` showed the v0.9.5 container healthy, local HTTP probe returned `OPENWEBUI_HTTP_OK`, and browser smoke proved both `vllm.Qwen/Qwen2.5-32B-Instruct-AWQ` and `gemma3:27b` chat paths still work.
- Created post-migration backup at `/home/bmoore_77/open-webui-backups/open-webui-v095-postmigration.tgz` (`979M`). Because v0.9.5 includes database migrations, rollback to the stopped `:main` container should be treated as a recovery action, not a routine flip-back.
- Kept `AIOHTTP_CLIENT_ALLOW_REDIRECTS` unset so the v0.9.5 redirect-based SSRF protection remains active by default.

## Open follow-ups

- [x] Re-pull Open WebUI as `:v0.9.5` (current stable) instead of `:main`. Update the run command in operational notes. Test chat + both Connections survive. **Watch for the `AIOHTTP_CLIENT_ALLOW_REDIRECTS` default change in v0.9.5**; keep redirects blocked unless a real Open WebUI web-fetch workflow requires an exception.
- [ ] Review Ollama v0.30.0 release notes when v0.30.0 stable ships (currently rc12). Major version bump from v0.23.2; evaluate before re-running the install script.
- [ ] Review vLLM v0.20.x / v0.21.x release notes — currently on hold, but worth a fresh look during the next monthly review.
