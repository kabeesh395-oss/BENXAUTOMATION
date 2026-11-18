# BENXAUTOMATION workflow map

This reference maps the skill's instructions to the existing CLI. It is not a promise that every optional provider is configured on a buyer's machine.

| User goal | Existing CLI route | Skill safety boundary |
|---|---|---|
| Check CLI availability | `python -m benxautomation.main --help` | No secrets are read |
| Render from a supplied script | `--script ... --format shorts|longform|both --mode render_only` | No AI provider is needed for script generation |
| Generate a repurposing draft | `--workflow repurpose --source ... --draft` | User must confirm source rights first |
| Render approved clips | `--workflow repurpose --apply-manifest ... --mode render_only` | Only user-approved manifest clips |
| Inspect output media | `ffprobe -v error -show_format -show_streams ...` | Report actual metadata, not assumptions |

## Output expectations

- Shorts target: vertical 9:16, normally 1080x1920.
- Long-form target: horizontal 16:9, normally 1920x1080.
- Repurposing workflow can produce a candidate manifest before final rendering.
- The project may produce subtitle files and quality reports depending on workflow and configuration.

## Not included

- YouTube upload or scheduling.
- API key setup, OAuth setup, or account connection.
- Paid voice/media calls.
- Third-party footage rights clearance.
- Mobile rendering or a hosted rendering service.

The CLI's actual help output and runtime checks take precedence over this summary. If a command or option differs in the installed version, stop and explain the mismatch rather than guessing.
