# Home Assistant (Wizard app)

[Home Assistant](https://www.home-assistant.io), unmodified, set up and run for you on your Wizard; or a link to the Home Assistant you already run. Your Wizard checks and controls your devices.

A [Wizard app](https://www.aiwizards.com/wizard-apps): install it from the Wizard Apps screen, or with the Wizard App Manager on any box running stock [Runtipi](https://runtipi.io).

- `wizard.md`: what the app is and what it gives the agent (spec: wizard.md v0.2).
- `runtipi/`: stock Runtipi `config.json` and `docker-compose.yml`. The engine is the official `ghcr.io/home-assistant/home-assistant` image, pinned by digest, unchanged.
- `mcp/`: the app's front (`front.py` + `tools.py`), inlined into the compose file by `python3 mcp/inline.py`. It creates Home Assistant's owner account on first start, serves the app's page at `/home-assistant/` (with `/smart-home/` kept as a compatibility alias) and the agent's tools at `/mcp` (`home_status`, `home_devices`, `home_device`, `home_control`; box-only), and passes everything else unchanged to Home Assistant.
- `SKILL.md`: the skill the agent loads when this app is installed.

## How it works

1. Install. The app creates Home Assistant's owner account and finishes its first-run steps itself. The password lives only in the app's private volume, and the page shows it under "Home Assistant sign-in" if you ever want the full Home Assistant app.
2. Open the app and connect your devices' brand. Some brands have a sign-in button on the page: tapping it fetches that brand's own Home Assistant integration from the brand's official release (checksum-pinned) onto your box, then you sign in and paste back the address the sign-in ends on (it works from a server that isn't on your home network). Any other brand: tap "Other brands" to open Home Assistant itself.
3. Already run Home Assistant? Pick "My own Home Assistant" and paste its address and a long-lived access token (Profile, Security). The built-in one then sits idle and the agent uses yours.
4. Ask your agent: "start the vacuum", "what's the air quality at home?", "turn off the living room purifier".

## Limits

- Camera video stays in the brand's app when the brand encrypts its streams end to end.
- Unlocking doors, disarming alarms and opening covers need the owner's explicit yes (`confirmed: true`).
- Cloud-connected devices work from a server anywhere. Zigbee, Bluetooth and local-only devices need the box on the home network.
- Brand integrations are downloaded onto your box under their own licences, for your own home use. This repository contains none of them.

## License

Home Assistant is Apache-2.0. The packaging in this repo is Apache-2.0 as well.

## App identity and compatibility

The Wizard app id is `home-assistant`, matching **Home Assistant**.
`renamed_from: [smart-home]` lets the App Manager move existing installs before
updating them (`wam app-rename smart-home home-assistant --dry-run` previews it).
The canonical page and health endpoint are `/home-assistant/` and
`/home-assistant/healthz`; `/smart-home/` and its API/assets remain aliases.
The `smart-home` capability, `/mcp` endpoint and `home_*` tool names stay unchanged.

The Compose services use `home-assistant` and `home-assistant-engine`; the old
service DNS names remain network aliases. The volume key is
`home-assistant-config`, but its physical name **stays** `wizard-smart-home-config`
to retain existing owner accounts, tokens and device connections. Likewise the
OAuth client id `http://smart-home/` must not change: existing refresh tokens are
bound to it. Source URLs still point to the real, unchanged upstream repo.

Checks (Python 3.10+):
```sh
uv run --with pyyaml python -m unittest discover -s tests -v
python3 mcp/inline.py --check
```
The tests use disposable local state and loopback HTTP, never real devices.

Known pre-existing admission issue: current `wam check` rejects the original
fixed named volume under storage rule 15. This prepared rename retains the
physical volume deliberately; removing it would discard access to existing
accounts and devices. Resolve that storage migration separately before release.
The index checker and the identity/HTTP regression tests pass.
