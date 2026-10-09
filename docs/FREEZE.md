# FREEZE.md - photographing a logged-in product page without logging in again

A promo about software wants the **real product on screen**. Some pages sit behind a login, and the Cursor browser tab cannot be pixel-screenshotted
reliably under device emulation (tiled / garbled output). The fix: *freeze* the page's DOM into one standalone HTML file, then photograph that file
with headless Chrome like any other asset (`examples/pitchcraft/capture-assets.js` shows the screenshot half).

## Rules first

- Only capture pages you are allowed to capture, with the user's consent. Never keep personal data: the freezer removes avatars / account / settings links by default
  (`opts.mask`), but **look at the result** before using it. Never capture API keys, billing or account pages.
- Frozen files and the screenshots made from them live in `projects/<name>/` (git-ignored). Do not commit them, and do not publish a film that shows another person's data.
- Do not change the user's account state to get a better picture. If you must (e.g. fill a demo form), say so in your final report.

## The tools

| file | does |
| --- | --- |
| `tools/freeze-page.js` | runs inside the page; defines `__pvFreeze(opts)` -> HTML string. Scrolls (optional) so lazy content mounts, inlines CSS, fonts and same-origin images as `data:` URIs, strips scripts / handlers / preloads, removes masked elements |
| `tools/freeze-decode.py` | saves the string when Cursor stored the CDP result in `~/.cursor/browser-logs/` instead of returning it inline |
| `tests/freeze.js` | proves the round trip offline (`node tests/freeze.js`) |

## Workflow (Cursor browser)

1. Open the page in the browser tab and let the user log in. Note the tab's `viewId` (pass it to **every** call - omitting it can target another tab).
2. `browser_cdp` -> `Runtime.evaluate` with `awaitPromise: true`, `returnByValue: true` and
   `expression` = the contents of `tools/freeze-page.js`, then `; __pvFreeze({ scroll: true })`.
   Pages with a strict CSP block `eval`, so paste the file contents as the expression instead of loading it from storage; paste it again on every call (it does not persist).
3. `python3 tools/freeze-decode.py projects/<name>/frozen/<page>.html` writes the newest result.
4. Photograph it headless at `deviceScaleFactor: 2`. Read element rects with `getBoundingClientRect()` for anything a fake cursor or callout must land on.
   Mask whatever still shows personal data in CSS before the screenshot (`visibility:hidden`).
5. Clear anything you changed in the user's tab afterwards (`Emulation.clearDeviceMetricsOverride`, localStorage keys, form state).

## Options

`__pvFreeze({ scroll: true, settleMs: 120, mask: ['css selector', ...] })` - `mask` replaces the default list; pass `[]` to keep everything (then check by hand).

## Limits

Canvas / WebGL contents are not captured (screenshot those live instead); cross-origin images the page cannot read stay remote and will be missing offline; pages that build
their DOM from scripts after interaction freeze in whatever state they were in when you called it.
