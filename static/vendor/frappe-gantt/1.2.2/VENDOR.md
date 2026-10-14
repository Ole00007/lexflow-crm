# Vendored library — Frappe Gantt 1.2.2

Immutable, vendored copy. **Do not edit these files by hand.** To upgrade, re-download
the npm archive, re-verify the checksums below, and replace the whole directory.

## Source

| Item | Value |
|---|---|
| Package | `frappe-gantt` |
| Version | `1.2.2` |
| Archive (npm) | https://registry.npmjs.org/frappe-gantt/-/frappe-gantt-1.2.2.tgz |
| License | MIT — Copyright (c) 2024 Frappe Technologies Pvt. Ltd. (`license.txt`) |
| Vendored on | 2026-10-14 |
| Extraction | `tar -xzf` of the archive above; three files copied verbatim |

## Checksums (verified locally at vendor time)

Archive SHA-256 — matches the value recorded in
`Frappe-Gantt/LexFlow-Gantt-Plan-v4-2.md` §1:

```
2e8c82de7b5423466cf28e7e6f52c163f34f2e65dedf2b0e2b5ea217529fc2c5  frappe-gantt-1.2.2.tgz
```

Vendored file SHA-256:

```
f5b9de3b618b72e675dfa7f159f2091fcf2055e62826309dfc4604d7ca649e41  frappe-gantt.umd.js
74ccfd2390849e729cda95a358439f003b79b94770ff732713217bc8045e7a69  frappe-gantt.css
f0ee9b1340ea287eacdc522f04f85b80304c2009c237809920ff9cf7684fc4f1  license.txt
```

## Files copied (verbatim from the archive)

| Vendored path | Archive path | Bytes |
|---|---|---|
| `frappe-gantt.umd.js` | `package/dist/frappe-gantt.umd.js` | 48175 |
| `frappe-gantt.css` | `package/dist/frappe-gantt.css` | 6848 |
| `license.txt` | `package/license.txt` | 1095 |

The archive's ES module build (`dist/frappe-gantt.es.js`), `src/` and `package.json` were
deliberately **not** vendored — the LexFlow frontend is plain Flask/Jinja with no bundler,
so only the UMD build (global `Gantt`) and the stylesheet are needed.

## Why vendored and not a CDN

Production CSP (set in `crm/__init__.py::add_security_headers`) is
`script-src 'self' ...; style-src 'self' ...`, which blocks third-party origins. A CDN
URL would be blocked in production and would also violate the plan rule
("Do not use a floating content-delivery-network URL in production").

## Serving

Flask's static folder is `<repo>/static`, so these files are served at:

```
/static/vendor/frappe-gantt/1.2.2/frappe-gantt.umd.js
/static/vendor/frappe-gantt/1.2.2/frappe-gantt.css
```

## Verify a checkout

```bash
shasum -a 256 static/vendor/frappe-gantt/1.2.2/frappe-gantt.umd.js \
              static/vendor/frappe-gantt/1.2.2/frappe-gantt.css \
              static/vendor/frappe-gantt/1.2.2/license.txt
```

## Options relevant to the read-only C view (verified in this exact build)

All three read-only flags exist in 1.2.2 and default to `false`
(`src/defaults.js` → `DEFAULT_OPTIONS`):

| Option | Default | Effect in 1.2.2 |
|---|---|---|
| `readonly` | `false` | Master switch. `draw_resize_handles()`, `update_handle_position()` and `update_progressbar_position()` all return early; bar drag-move is blocked. |
| `readonly_dates` | `false` | Blocks date edits: no resize handles (`!readonly_dates && !fixed_duration`) and no bar drag-move. The progress handle is **not** suppressed by this flag alone. |
| `readonly_progress` | `false` | Suppresses only the circular progress drag handle (`$handle_progress`). |

Layer 1 sets all three to `true` (see `static/js/gantt/gantt_view.js`) so intent is explicit
and no partial code path can re-enable manipulation.

Other defaults worth pinning for this view: `move_dependencies` (default `true` — must be
set to `false`), `popup_on` (`click`), `view_mode` (`Day`), `view_mode_select` (`false` —
set `true` for Layer 2 Day/Week/Month switching), `infinite_padding` (`true` — set `false`
so the timeline scrolls inside its own container at 375 px), `today_button` (`true`).
