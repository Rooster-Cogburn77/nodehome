# IPMI / BMC Recovery Runbook

**Hardware:** Supermicro H12SSL-i v2.0 with ASPEED AST2500 BMC
**BMC firmware version (verified 2026-05-09 via BIOS IPMI tab):** `01.05.02`

This is the out-of-band recovery path for the Sovereign Node. When the host OS is reachable via SSH, you do not need this doc — you log in normally. This doc covers the cases where the host OS is **not** reachable: kernel panic, hung boot, network misconfig, locked-out user, or any scenario where the only way back in is through the BMC.

---

## Quick reference

| Field | Value |
|---|---|
| Board | Supermicro H12SSL-i v2.0 |
| BMC chip | ASPEED AST2500 |
| BMC firmware | `01.05.02` |
| Dedicated IPMI ethernet port | rear I/O panel, separate from `eno1` / `eno2` |
| BMC dedicated NIC MAC | `90:5A:08:7B:71:6D` (verified via `ipmitool lan print 1` on 2026-05-10; supersedes a one-character transcription typo `90:5A:08:78:71:6D` in `docs/archives/SESSION_LOG_2026-04.md:62`) |
| BMC IP address (current) | `0.0.0.0` — dedicated IPMI ethernet **is not yet patched into the rack switch**, so the BMC has no LAN IP. Channel 1 is set to DHCP; once the cable is patched it will pick up an address from the LAN's DHCP server (gateway `192.168.1.1`) |
| BMC IP address (after patch) | **`<TBD — re-run sudo ipmitool lan print 1 after patching the cable, fill in the new IP, ideally also reserve it in the router's DHCP table or set static>`** |
| BMC web UI URL (after patch) | **`https://<BMC_IP>`** (HTTPS, self-signed cert — accept the warning) |
| Default username | `ADMIN` (slot 2, ADMINISTRATOR privilege; verified via `ipmitool user list 1`) |
| Default password | **Rotated 2026-05-17.** Live ADMIN credential is stored only in the user's **KeePassXC** vault at entry `Nodehome - Supermicro H12SSL-i BMC`. Rotation used in-band `ipmitool` on the IPMI 2.0 extended (20-byte) path — `sudo ipmitool user set password 2 <pw> 20` — and was verified by authenticated RMCP+ login (`-I lanplus -C 3`) against the BMC USB-NIC at `169.254.3.254`. The original factory sticker password still exists in earlier revisions of this file and in `docs/archives/SESSION_LOG_2026-04.md:57`, but is **no longer the live credential**. To recover the BMC, open the KeePass entry locally — never paste the new password into chat, never commit it to the repo, and do not re-rotate without first verifying the current credential still authenticates (BMC `Bad Password Threshold` is `3`, lockout interval 300 s). |

---

## How the BMC is currently reachable

As of 2026-05-10, the dedicated IPMI ethernet port is **not yet patched into the rack-side network**. Confirmed empirically: `sudo ipmitool lan print 1` returns `IP Address: 0.0.0.0` and `IP Address Source: DHCP Address`, meaning the BMC is configured to accept a DHCP lease but has no link to negotiate one over.

The host OS does see a BMC USB-NIC virtual interface (`enxbe3af2b6059f` at `169.254.3.1/24`), which is the BMC's USB-attached link-local channel for in-band management. That works for tools running on the host OS itself (and is how `ipmitool lan print 1` is reaching the BMC right now) but is **useless when the host OS is down**, which is exactly when you need IPMI.

**Action item gating real out-of-band recovery:** patch an ethernet cable from the dedicated IPMI port on the rear I/O panel into your data switch. The BMC's dedicated NIC MAC is `90:5a:08:7b:71:6d`; if you want to reserve a stable IP, set up a DHCP reservation against that MAC in your router. After patching, re-run `sudo ipmitool lan print 1` from the host OS, confirm the new IP, and record it in the table above.

## Web UI access (primary path)

Once the BMC is on the LAN:

1. From any machine on the same LAN, open `https://<BMC_IP>` in a browser
2. Accept the self-signed certificate warning (the BMC ships with a self-signed cert; replacing it is a separate hardening item, not in scope for recovery)
3. Log in with `ADMIN` / `<recorded password>`
4. Available functions:
   - **Remote KVM** — full keyboard/video/mouse over the network. See the host's BIOS POST, GRUB menu, kernel boot messages, login prompt. Use this when the OS is hung or you need to enter BIOS
   - **Power Control** — power on / off / cycle / reset the host. Use when the host is hung and physical access is inconvenient
   - **System Event Log (SEL)** — hardware-level events: thermal trips, ECC corrections, voltage anomalies, fan failures
   - **Sensor Readings** — fan speeds, temperatures, voltage rails. Useful for "why did it shut down" forensics
   - **Virtual Media** — mount an ISO from your laptop as a virtual USB drive on the host. Use if the host OS is unbootable and you need to reinstall

## Command-line access (`ipmitool`)

For scripting and quick checks, install `ipmitool` on any LAN-reachable machine:

```bash
sudo apt install -y ipmitool                     # Ubuntu / Debian
brew install ipmitool                             # macOS
```

Common operations against the LAN-reachable BMC:

```bash
# Power state
ipmitool -H <BMC_IP> -U ADMIN -P <password> chassis power status

# Power on / off / cycle (use cycle when host is hung)
ipmitool -H <BMC_IP> -U ADMIN -P <password> chassis power on
ipmitool -H <BMC_IP> -U ADMIN -P <password> chassis power off
ipmitool -H <BMC_IP> -U ADMIN -P <password> chassis power cycle

# Sensor readings
ipmitool -H <BMC_IP> -U ADMIN -P <password> sdr type Temperature
ipmitool -H <BMC_IP> -U ADMIN -P <password> sdr type Fan

# System event log
ipmitool -H <BMC_IP> -U ADMIN -P <password> sel list

# Serial-over-LAN console (text-mode console over the network)
ipmitool -H <BMC_IP> -U ADMIN -P <password> sol activate
```

## Failure scenarios this doc addresses

- **Host OS hangs:** Web UI → Power Control → Reset, OR `ipmitool ... chassis power cycle`
- **Need to enter BIOS but no monitor handy:** Web UI → Remote KVM, hit DEL/F2 during POST
- **Host won't POST:** Web UI → SEL log; check for hardware-level errors. Sensor readings to confirm thermals
- **Need to reinstall OS but the box is in the rack:** Web UI → Virtual Media → mount Ubuntu ISO from your laptop
- **Network misconfig locked you out via SSH:** Web UI → Remote KVM, log in directly
- **Box thermal-shutdowns mysteriously:** Web UI → SEL log, look for thermal trip events; correlate with sensor history

## Failure scenarios this doc does NOT address

- **BMC itself unreachable:** if the BMC is dead or its ethernet is unplugged, recovery requires physical access. Have a monitor + keyboard available.
- **PSU off / no power:** BMC needs PSU standby power to be reachable. If the wall outlet is dead, BMC is also dead.
- **Compromised credentials:** if `ADMIN` is locked out, recovery is via BMC CMOS reset jumper on the motherboard (physical access required).

## Hardening items, separate from this runbook

These are not required for recovery to work but should happen as part of production posture:

- **[done 2026-05-17] Rotate the `ADMIN` password.** Rotated out via in-band `ipmitool` on the IPMI 2.0 20-byte extended path; verified by authenticated RMCP+ login against the BMC USB-NIC at `169.254.3.254` using cipher suite 3. Live credential is now in the user's **KeePassXC** vault at entry `Nodehome - Supermicro H12SSL-i BMC`. The factory sticker value remains in earlier revisions of this file and in `docs/archives/SESSION_LOG_2026-04.md:57` but is no longer the live credential — a `git history` rewrite to scrub the old value would be busy-work, not a security fix. Full procedure (including the `> 20 bytes` failure mode to avoid) is documented in `docs/runbooks/ipmi-hardening.md` Phase 1
- Replace the self-signed BMC web UI certificate with a private-CA-signed one
- Set the BMC ethernet to a static IP (or a DHCP reservation) so the address in this runbook stays accurate
- Disable unused BMC services (Telnet, SNMPv1) via the web UI's Services config
- Optionally: put the BMC on a management VLAN separate from the data LAN
