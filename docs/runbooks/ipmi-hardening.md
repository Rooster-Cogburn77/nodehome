# IPMI / BMC Hardening — Scope and Execution Plan

**Status:** IN PROGRESS — Phase 1 password rotation and recovery-doc update complete; cert hygiene, VBAT/clock follow-up, and network phases pending.
**Authored:** 2026-05-10 (Session 16 close-out)
**Companion runbook:** `docs/runbooks/ipmi-recovery.md` (the recovery counterpart; this doc is the proactive hardening counterpart).

## Why this exists

The BMC on this build (Supermicro H12SSL-i v2.0, ASPEED AST2500, firmware `01.05.02`) currently sits in a deliberately-soft posture acceptable for bring-up but unacceptable for any LAN exposure:

- The **factory default ADMIN password** was recorded in `docs/archives/SESSION_LOG_2026-04.md:57` and is therefore **in repo git history forever**. Anyone with read access to the historical repo can recover it. **Rotated out as the live credential on 2026-05-17** (see Phase 1 below); the value in the archive is no longer the live BMC password, but a `git history` rewrite to scrub it would be invasive and is not in scope.
- The **BMC web UI uses the AST2500 self-signed cert** with a generic CN, so browsers warn on every connect and there's no way to detect a MITM if the BMC ever sat on a network with hostile traffic.
- The **dedicated IPMI ethernet port is unpatched** (`IP Address: 0.0.0.0`; source reported as `DHCP Address` on 2026-05-18). The BMC is currently only reachable via the in-band USB virtual NIC path (host side `169.254.3.1/24`, BMC side `169.254.3.254`), which is fine for bring-up but not true out-of-band — if the host OS is wedged hard enough, the in-band path can be wedged with it.

The rack-mount + final deployment phase is gated on completing this hardening. The temporary pigtail rule on GPU 3 also keeps the box moved-once-permanently, so the BMC patch happens together with the rack-mount as one event, not two.

## Open decisions / remaining gates

The remaining open decisions mainly affect Phases 2 and 3. The password-manager decision for Phase 1 is resolved, but it stays listed here so the recovery dependency is visible.

1. **Home network gear.** Consumer ISP router? UniFi gateway? pfSense / OPNsense? OpenWRT? The answer determines whether VLAN trunking + inter-VLAN ACLs are even possible on the existing router, or whether you need to add a small firewall device in front of the rack.
2. **Managed switch.** Already own one? If not, the standard cheap-and-good answer is a TP-Link TL-SG108E v6 (~$35-50, 8-port smart-managed gigabit, 802.1Q VLANs, web UI). Anything that supports tagged 802.1Q VLANs works.
3. **Where the new BMC ADMIN credential will live.** **Resolved 2026-05-17: KeePassXC vault entry `Nodehome - Supermicro H12SSL-i BMC`.** Recovery doc references the entry, not the secret.
4. **Fallback posture if the home router cannot do VLANs.** Either (a) add a small firewall device to handle VLANs and routing for the rack ($100-200 for a Protectli / GL.iNet / mini-PC running OPNsense), or (b) accept flat-LAN posture with Phase 1 hardening as the only security boundary and skip Phases 2 and 3 for now. Both are valid. The right answer depends on how much you intend to expose this box outside the home LAN over the next year.

## Phases

### Phase 1 — Password rotation + cert hygiene (no LAN dependency)

**Runs entirely over the in-band BMC path** (`ipmitool` via the USB virtual NIC at `169.254.3.1`). No new hardware. No router changes. Highest value-per-effort piece — do this first regardless of how the network decisions land.

Steps:

1. **[done 2026-05-17]** Decide the password manager destination. **Chosen: KeePassXC** with the vault file at `C:\Users\bmoor\nodehomevault\KP1_Personal.kdbx`, synced between the Windows workstation (`Yoga`) and homelab via Syncthing into `~/NodehomeVault`.
2. **[done 2026-05-17]** Generate a strong replacement password using the KeePassXC password generator. **Hard constraint discovered in practice: IPMI 2.0 caps the password length at 20 bytes; a prior `Password is too long (> 20 bytes)` failure was a >20-byte attempt.** Use **17 to 20 ASCII printable characters** — at least 17 so the BMC chooses the 20-byte (extended) path, at most 20 so it doesn't exceed the spec. ASCII only; UTF-8 multi-byte characters inflate byte count beyond character count and will break length validation. Save the entry to KeePassXC first; the prior value is retained automatically in the entry's Password History as a fallback.
3. **[done 2026-05-17]** Rotate via the in-band BMC system interface. ADMIN is user ID `2` on Supermicro AST2500 (verify with `sudo ipmitool user list 1` first). **The trailing `20` is mandatory** — without it `ipmitool` defaults to the 16-byte (IPMI 1.5) `Set User Password` command and a longer password is rejected. Drive the cleartext through a local shell variable populated by `read -rs` — that way `~/.bash_history` records `"$NEWPW"` (the variable reference), not the actual password. **Do not paste the literal password inline between single quotes** — that *does* land in history. `unset` the variable immediately after:
   ```bash
   sudo -v                                                       # cache sudo creds so the read doesn't time out
   IFS= read -rs NEWPW                                           # silent read; paste password, press Enter
   sudo ipmitool user set password 2 "$NEWPW" 20
   rc=$?
   unset NEWPW
   echo "rotation_exit=$rc"
   ```
   Success looks like `Set User Password command successful (user 2)` and `rotation_exit=0`. The actual block run on 2026-05-17 also wrapped this with local length (17-20 bytes) and ASCII-printable validation before calling `ipmitool`, so a typo or bad paste cannot reach the BMC and burn a `Bad Password Threshold` attempt.
4. **[done 2026-05-17]** Verify the new password by authenticating via RMCP+ on the BMC USB-NIC (`169.254.3.254` on this build) using cipher suite 3. **Do not pass the password on the command line with `-P`** — it leaks into shell history and to other users via `ps`. Use the `-f` password-file pattern with restrictive `umask`, populate the file from a `read -rs` variable (same reason as step 3), and force exactly one auth attempt with `-R 1 -N 5`. The BMC `Bad Password Threshold` is `3` with `Attempt Count Reset Int. 300`, so default ipmitool retries can exhaust the lockout budget on a single command:
   ```bash
   umask 077
   IFS= read -rs VPW                                             # silent read; paste same new password, press Enter
   printf '%s' "$VPW" > /tmp/bmcpw
   unset VPW
   sudo ipmitool -I lanplus -H 169.254.3.254 -U ADMIN -C 3 -R 1 -N 5 -f /tmp/bmcpw mc info
   vrc=$?
   shred -u /tmp/bmcpw 2>/dev/null || rm -f /tmp/bmcpw
   echo "verify_exit=$vrc"
   ```
   `verify_exit=0` plus a real `mc info` response confirms the new password works under authenticated RMCP+. The KCS in-band bypass path cannot fake this — KCS does not validate the IPMI user password, so a successful `mc info` over `-I lanplus -C 3` is real proof, not a free pass.
5. **[done 2026-05-17]** Update `docs/runbooks/ipmi-recovery.md`: replace the inline factory password value with a pointer to the KeePass entry, date the rotation, and record the rotation method and verification IP. **Do not rewrite git history** — the old factory value was already in earlier revisions and is no longer the live credential, so a history rewrite would be busy-work, not a security fix.
6. **[blocked / inspected 2026-05-18]** Replace the BMC HTTPS certificate with a certificate/private-key pair matching the final BMC hostname or static IP. The web UI is reachable today through the USB-NIC tunnel (`https://169.254.3.254/`), and `Configuration -> Network -> SSL Certificates` exposes upload fields for `New SSL Certificate` and `New Private Key` only; no CSR or self-signed generator was visible. Do not upload yet: the final hostname/static IP is undecided, the BMC clock is wrong, and `VBAT` is failed. Use unencrypted PEM, RSA 2048, when ready.
7. **Quirk to watch:** AST2500 firmware is picky about cert format — needs unencrypted PEM, RSA 2048 (not 4096; some firmware revs reject ECDSA). If upload fails, regenerate at 2048.

**Cost:** $0. **Time:** steps 1-5 actual = ~30 min (2026-05-17); cert upload adds ~15 min after hostname/static-IP and clock/battery posture are settled. **Outcome of steps 1-5 (completed 2026-05-17):** factory password is no longer the live credential; live credential lives only in the KeePassXC vault entry `Nodehome - Supermicro H12SSL-i BMC`; rotation verified by authenticated RMCP+ login (`-I lanplus -C 3`) against `169.254.3.254`. Cert hygiene remains pending.

#### 2026-05-18 BMC UI inspection findings

Observed over the USB-NIC web UI tunnel and host-side `ipmitool`; these are live posture notes, not planned target state:

- Dashboard/web reachability: BMC web UI is reachable over the USB-NIC tunnel. Dashboard showed BMC firmware `01.05.02`, BIOS `3.3`, BMC MAC `90:5A:08:7B:71:6D`, and server IP `0.0.0.0`. `curl -k -I --connect-timeout 5 https://169.254.3.254/` returned `HTTP/1.1 403 Forbidden`, which is enough to prove HTTPS service reachability; HEAD is forbidden but the service is alive.
- `Configuration -> BMC Settings -> Date and Time`: NTP is off, timezone is UTC, NTP servers are `localhost` and `127.0.0.1`, and the UI displayed `2025-04-01T00:46:16Z`. Treat BMC SEL timestamps as unreliable until the BMC clock and battery state are fixed.
- `Configuration -> Network -> Network`: IPv4 is on with DHCP selected, but IP and subnet remain `0.0.0.0`; gateway is `192.168.1.1`. IPv6 auto configuration is on. Hostname is blank, VLAN is off, and the LAN interface radio showed `Failover` selected.
- `Configuration -> Network -> SSL Certificates`: current cert validity reports `Sep 4 00:00:00 2024 GMT` through `Sep 4 00:00:00 2034 GMT`. The page exposes upload controls for a cert file and private key file (`.pem` / `.cert`) and no visible CSR or self-signed generator. Final upload should wait for the chosen hostname/static IP and clock/battery cleanup.
- `Configuration -> Network -> Port`: enabled TCP ports are IKVM `5900`, SSH `22`, Web `80`, Web SSL `443`, and Virtual Media `623`; enabled UDP port is IPMI LAN `623`. SNMP UDP `161` is already disabled.
- `Configuration -> Network -> IP Access Control`: IP Access Control is `OFF`.
- Sensor follow-up: BMC Sensor Readings showed `VBAT` = `Battery Failed`. Host confirmation matched: `sudo ipmitool sensor get VBAT` reported `States Asserted: Battery [Failed]`, and `sudo ipmitool sdr elist | grep -i -E 'VBAT|Battery'` returned `VBAT ... Failed`. Treat this as a likely CMOS/RTC battery replacement candidate before the next chassis-open event.

### Phase 2 — Network plumbing for management VLAN (gated on decisions #1, #2, #4)

Only meaningful if the home router supports VLANs or you've added a firewall device that does.

Steps (specifics depend on actual gear):

1. Acquire managed switch if not already owned.
2. Pick a management VLAN ID (`10` is conventional) and subnet (`192.168.10.0/24`).
3. Configure switch:
   - BMC port: untagged on VLAN 10 (so the BMC sees a regular ethernet port).
   - Uplink to router: tagged on VLAN 10 (and tagged on whatever the main LAN VLAN is, if the router does proper trunking).
   - Other rack ports: stay on the default LAN.
4. Configure router/firewall:
   - VLAN 10 interface, no DHCP (BMC will be static).
   - Default ACL: deny VLAN 10 ↔ general LAN.
   - Allow rule: specific workstation IP(s) → VLAN 10 inbound on management ports only:
     - HTTPS `443` (BMC web UI)
     - IPMI `623/udp` (`ipmitool` LAN+ command channel)
     - KVM `5900` (HTML5 KVM console)
     - Virtual media `623`, `5120`, `5123` (varies by AST2500 firmware — check current ports in BMC settings)
   - No inbound from VLAN 10 to general LAN.

**Cost:** $35-50 for the switch, $0-200 for router gear depending on the answer to decision #1. **Time:** 2-4 hours including testing the ACLs. **Outcome:** isolated network plane the BMC can sit on without exposing to the general LAN.

### Phase 3 — BMC static IP + cable patch (gated on Phase 2)

Steps:

1. Configure BMC static IP via in-band:
   ```
   sudo ipmitool lan set 1 ipsrc static
   sudo ipmitool lan set 1 ipaddr 192.168.10.x  # outside DHCP range
   sudo ipmitool lan set 1 netmask 255.255.255.0
   sudo ipmitool lan set 1 defgw ipaddr 192.168.10.1
   sudo ipmitool lan print 1  # verify
   ```
2. Patch dedicated IPMI ethernet port → switch port configured for management VLAN (untagged).
3. Verify reachability from the allowlisted workstation: web UI loads at `https://192.168.10.x`, `ipmitool -I lanplus -H 192.168.10.x -U ADMIN -P <newpass> chassis status` returns.
4. Verify isolation: from a host on the general LAN that is **not** allowlisted, the BMC must be unreachable on all ports.

**Cost:** ~$5 for a Cat 6 patch cable. **Time:** 15 min if Phase 2 is solid; potentially hours if there's a switch or ACL misconfig.

### Phase 4 — Internal CA (defer)

Optional. Self-signed-with-correct-hostname from Phase 1 step 6 is fine for a homelab management plane. The "really proper" version is standing up an internal CA (`smallstep step-ca` is the clean modern choice) and issuing a real signed cert for the BMC. Workstations trust the CA root once, BMC web UI loads with no warning thereafter.

**Worth doing once you have more than one device on the management VLAN** (second node, switch web UI, future homelab services). For one BMC, the value-per-effort is poor. Skip for now; revisit when the management plane has 3+ devices.

## Recovery runbook sync

`docs/runbooks/ipmi-recovery.md` was updated on 2026-05-17 as part of Phase 1 step 5.

Current posture:

- Recovery doc references the KeePassXC entry, not the rotated value.
- The old factory value is treated as historical/compromised and no longer live.
- BMC recovery now requires access to the KeePassXC vault entry `Nodehome - Supermicro H12SSL-i BMC`.

Future Phase 2/3 changes should update `docs/runbooks/ipmi-recovery.md` again when the BMC gets a routable static IP, dedicated LAN patch, and cert posture.

## Success criteria

The hardening is "done" when:

1. **[done 2026-05-17]** Factory sticker password is no longer the live ADMIN credential. New credential is in a password manager (KeePassXC vault entry `Nodehome - Supermicro H12SSL-i BMC`), not in git. Verified via authenticated RMCP+ login against `169.254.3.254` using cipher suite 3.
2. **[blocked / inspected 2026-05-18]** BMC web UI presents a cert that at least correctly identifies the BMC's hostname/IP. The web UI is reachable today over the USB-NIC tunnel, but final cert upload is gated on the target hostname/static IP and BMC clock/battery cleanup.
3. **[pending]** Dedicated IPMI port has a static IP on a network the BMC has been deliberately placed on. Gated on Phase 2 (managed switch + management VLAN).
4. **[pending]** From any host not on the management plane, the BMC is unreachable on all ports. Gated on Phase 2.
5. **[pending]** From the allowlisted workstation, the BMC is reachable for power control, KVM, and sensor monitoring. Gated on Phase 3.
6. **[done 2026-05-17]** `docs/runbooks/ipmi-recovery.md` is updated to match the new posture (KeePass-pointer for the live credential, rotation method and verification IP recorded).

If decision #4 lands as "accept flat-LAN posture" (i.e., skip Phases 2 and 3 for now), success criteria #3, #4, and #5 are deferred and the BMC stays on the in-band USB-NIC path until the home network gets a VLAN-capable router or firewall in front of it.
