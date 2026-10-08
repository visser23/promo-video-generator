# Optional Mirage Tesseract tools

[Mirage Tesseract](https://github.com/mirage-hq/Tesseract) is a separate creative CLI with agent skills for video editing, motion graphics, static design and browser editors. It is not the Tesseract OCR package. Use it when a brief benefits from native footage editing or an editable `.tsrct` document. The HTML/Chrome/ffmpeg pipeline remains the default and needs none of these tools.

## Integration boundary

This repository supports Tesseract through optional setup and agent guidance only. There is no runtime adapter, automatic installer or npm dependency. The public upstream repository contains skills, references and a browser player; the native CLI is distributed as release ZIPs. Its native project scripting has no DOM or CSS, so it cannot directly run `index.html`, `scene.js`, `window.seek(t)` or `PV.*`. Do not replace `tools/render.js` or `tools/build.sh` with it.

Choose one of these approaches:

- Use Tesseract separately to prepare local images or footage, then store those assets in `projects/<name>/assets/`. Validate them with the existing scene and still-review workflow. Video playback must be explicitly synchronised to `seek(t)`; dropping an autoplay video into a scene does not preserve determinism.
- For a native Tesseract production, retain the editable document in `projects/<name>/` and exports/previews in `out/<name>/`. Use its own preview, filmstrip and export commands, not this repository's HTML renderer. Copy the agreed timing from the brief or `cues.json` deliberately: Tesseract does not read our cues automatically. Document the selected workflow and commands at handoff.

There is no supported lossless conversion of this repository's HTML scenes to `.tsrct`. Upstream's separately versioned [Tesseract Converter](https://github.com/mirage-hq/Tesseract-Converter) targets other editing formats; it is not installed here. The web runtime is for building a Tesseract browser editor, not a drop-in replacement for our renderer.

## Version and installation

The reference release is **v0.3.1**, the latest non-prerelease inspected on **8 October 2026**. Its motion/video skills pin CLI **0.3.1** in `references/cli-version.txt`. Install matching skills and CLI from that tag, not an unpinned latest bundle. On upgrade, read the new skills' version pin and re-check their installation and compatibility guidance together.

1. Review the upstream [terms](https://github.com/mirage-hq/Tesseract/blob/v0.3.1/TERMS.md) before downloading or using it. Tesseract is subject to Mirage's terms, not this repository's MIT licence. Those terms restrict competing products/services and require a separate written agreement for commercial use by or on behalf of businesses with annual revenue of at least US$1,000,000. Do not bundle it into this toolkit or a hosted rendering service on the assumption that public downloads grant those rights.
2. Obtain the skills you need from [tag v0.3.1](https://github.com/mirage-hq/Tesseract/tree/v0.3.1/skills), or install the matching release plugin according to your agent's plugin instructions. Choose skills or the plugin, not both. Skills contain instructions, not the native renderer. Read the selected `SKILL.md` and its version-matched references before authoring.
3. Follow the [pinned installation guide](https://github.com/mirage-hq/Tesseract/blob/v0.3.1/skills/tesseract-video/references/installation.md). Look for the installed command below, then `tsrct` on PATH, and run `--version`. The command is **`tsrct`**, not `tesseract`.
4. If missing or mismatched, select the platform CLI ZIP and its matching `.sha256` from [release v0.3.1](https://github.com/mirage-hq/Tesseract/releases/tag/v0.3.1). Verify the checksum before extraction, then run the bundled `install.sh` (macOS/Linux) or `install.ps1` (Windows). Check the installed absolute path with `--version` and use that path for subsequent commands. Do not bypass OS security checks.

| Host | CLI ZIP suffix | Default installed command |
| --- | --- | --- |
| Apple Silicon macOS | `darwin-arm64` | `~/Library/Application Support/Tesseract/bin/tsrct` |
| Intel macOS | `darwin-x86_64` | `~/Library/Application Support/Tesseract/bin/tsrct` |
| Linux x86_64, glibc 2.35+ | `linux-x86_64` | `${XDG_DATA_HOME:-$HOME/.local/share}/Tesseract/bin/tsrct` |
| Windows 10+, x86_64 | `windows-x86_64` | `%LOCALAPPDATA%\Tesseract\bin\tsrct.cmd` |

ZIP names are `tesseract-0.3.1-<suffix>.zip`. On macOS check `uname -m`; under Rosetta check `sysctl -in sysctl.proc_translated` and choose arm64 when it returns 1. The bundled installer checks the minimum OS version and architecture. Linux requires host libraries and a compatible Vulkan driver; a loader alone is insufficient. Linux ARM is not supported by this release. See the installation guide for the exact dependencies.

The CLI does not require Node, Rust or Homebrew. Leave `package.json` and `package-lock.json` alone: `npm install` and `npm run doctor` cover only the existing pipeline. Tesseract being absent is not a missing dependency for this repo.

## Verify an optional installation

Before native authoring, run the resolved command with `--version`, `project --help` and `export --help`. Confirm version 0.3.1 and read [local operation](https://github.com/mirage-hq/Tesseract/blob/v0.3.1/skills/tesseract-motion/references/local-operation.md) for supported commands and schemas. Do not invent project JSON fields or edit the `.tsrct` archive directly.

A macOS check, after installation:

```bash
"$HOME/Library/Application Support/Tesseract/bin/tsrct" --version
"$HOME/Library/Application Support/Tesseract/bin/tsrct" project --help
"$HOME/Library/Application Support/Tesseract/bin/tsrct" export --help
```

CLI usage telemetry is enabled by default for some commands. Respect existing preferences; `tsrct telemetry status` checks them and `tsrct telemetry disable` opts out. See [telemetry details](https://github.com/mirage-hq/Tesseract/blob/v0.3.1/skills/tesseract-motion/references/telemetry.md). Do not enable it on the user's behalf. This is separate from the existing pipeline's no-network-at-render-time rule; an offline Tesseract workflow needs telemetry disabled and all media/fonts packaged locally.

Verify rendering with a small preview/export on the actual host. `--version` alone does not establish GPU or encoder compatibility. Linux does not bundle an H.264 encoder; select an external FFmpeg explicitly:

```bash
# Replace tsrct with its resolved absolute path and use a real native project.
tsrct export --project projects/my-native/project.tsrct \
  --output out/my-native/finished.mp4 --fps 60 \
  --encoder-backend external-ffmpeg-command --ffmpeg-path /absolute/path/to/ffmpeg
```

Create the output directory first. Native export defaults to 1080p30, not this toolkit's usual 1080p60. Match the intended dimensions, frame rate and timing explicitly, probe the encoded output with `ffprobe`, and inspect extracted frames and audio. Native preview/export does not inherit our four-sub-frame motion blur or our determinism tests. Upstream documents transparent ProRes exports on macOS; transparent overlays require solo export and alpha verification. Report any renderer, encoder or platform failure rather than silently reducing fidelity or claiming the HTML smoke test verifies Tesseract.
