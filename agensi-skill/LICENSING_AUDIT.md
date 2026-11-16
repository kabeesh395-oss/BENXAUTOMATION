# BENXAUTOMATION licensing and resale-readiness audit

**Audit date:** 2026-11-16  
**Scope:** Repository metadata and the proposed Agensi workflow-skill listing. This is a technical/documentation audit, not legal advice or proof of ownership.

## Findings

### 1. Repository-wide licence declaration is incomplete — BLOCKER

- `README.md` describes the project as open source, displays an MIT badge pointing to `LICENSE`, and states that original code and character designs are MIT-licensed.
- `pyproject.toml` declares `license = {text = "MIT"}` and lists the author as `BENX Team`.
- The root `LICENSE` file does not exist on `main` (GitHub contents lookup returned 404).
- No root `NOTICE` file was found.
- The GitHub repository therefore does not currently provide the actual MIT grant text that its README badge and package metadata imply.

**Action:** Do not add an MIT licence or claim that the complete application is MIT-licensed until the actual copyright holder(s) and authority to license all included original code are confirmed. If the project is not intended to be open source, revise the README badge/claims and package metadata instead.

### 2. Asset manifest is useful metadata, not ownership evidence — BLOCKER

- `assets/license_manifest.yaml` labels several assets as CC0, original, or creator-owned and marks commercial terms as verified.
- `assets/mascot/rig_manifest.json` and `character_spec.json` label the BENX character as `original_creator_owned`.
- These files are self-authored declarations. The repository alone does not establish who created each asset, whether any generated asset used third-party inputs, or whether the person who committed it had authority to grant commercial rights.
- The manifest contains mixed descriptions: some entries say `license: original` while their terms reference CC0 1.0; those labels should be normalized and supported by source/provenance records.

**Action:** Keep a provenance record for each distributed asset: creator, creation/source date, source or generation method, applicable provider terms, licence, and any required attribution. Remove or quarantine assets whose rights cannot be verified.

### 3. Third-party dependency licence inventory is missing — BLOCKER for bundling/reselling the app

- `pyproject.toml` and `requirements.txt` declare Python dependencies including Pydantic, PyYAML, Requests, edge-tts, Pillow, NumPy, FastAPI, Uvicorn, Starlette, yt-dlp, python-dotenv, and httpx.
- The repository does not include a generated third-party licence inventory or consolidated notices in the files inspected.
- A dependency declaration is not itself a licence audit. Transitive dependencies and any bundled fonts, icons, templates, binaries, or media also need review.

**Action:** Generate a dependency licence report from a pinned, reproducible environment; inspect direct and transitive licences; add required notices/attributions; and separately review any assets or code copied into the repository.

### 4. Agensi skill package has a narrower distribution scope

- The proposed skill package is a written workflow guide and small preflight script. It explicitly says it does not bundle the BENXAUTOMATION engine, media assets, FFmpeg, or dependencies.
- It nevertheless instructs the buyer's agent to operate an existing BENXAUTOMATION checkout/package. The listing currently says the buyer needs a separate, licensed installation.
- Selling the workflow guide alone does not grant buyers rights to copy, install, modify, or redistribute the underlying application.

**Action:** Do not submit the paid listing until the buyer prerequisites and legal relationship to the underlying application are clear. Test the skill in a real Agensi agent and verify its tool/permission behaviour before listing.

## Decision

**Not ready for paid publication.** No licence file has been added, no ownership has been presumed, and no files on `main` have been changed by this audit.

## Safe next steps

1. Identify the actual copyright holder(s) of the original code and character/assets.
2. Confirm whether the holder intends to grant an open-source licence and which licence is appropriate.
3. Resolve third-party code and asset obligations with a reproducible inventory.
4. Correct README/package metadata and add licence/notice files only after the rights and intended terms are confirmed.
5. Re-run CI and validate the Agensi package against its current submission requirements.
