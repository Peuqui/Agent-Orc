// The overview of Agent-Orc's icons (src/icons.ts) in docs/icons: an HTML page and a picture of it.
// `npm run icons` writes both; a test checks that the page still shows what icons.ts holds.
import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { ICONS } from '../src/icons.ts'

export const SHEET_DIR = new URL('../../docs/icons/', import.meta.url)
export const SHEET_HTML = new URL('agent-orc-icons.html', SHEET_DIR)
const SHEET_PNG = new URL('agent-orc-icons.png', SHEET_DIR)
// Wide enough for eight columns; tall enough for all rows (Chrome cuts the picture at this height).
const PICTURE_SIZE = '1100,1100'

function svg(path: string, size: number): string {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${path}"/></svg>`
}

/** The page: every icon large (40 px) and small (20 and 16 px), with its name. */
export function iconSheet(icons: Record<string, string>): string {
  const cells = Object.entries(icons)
    .map(
      ([name, path]) =>
        `<div class="cell"><div class="big">${svg(path, 40)}</div><div class="small">${svg(path, 20)}${svg(path, 16)}</div><code>${name}</code></div>`,
    )
    .join('\n')
  return `<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Agent-Orc Icons</title><style>
body{margin:0;padding:24px;background:#0f172a;color:#e2e8f0;font:14px system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px} p{color:#94a3b8;margin:0 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:12px}
.cell{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px 8px;display:flex;flex-direction:column;align-items:center;gap:8px}
.big{color:#f1f5f9}.small{display:flex;gap:10px;align-items:center;color:#f87171}
code{font-size:12px;color:#fbbf24}
</style></head><body><h1>Agent-Orc Icons (${Object.keys(icons).length})</h1>
<p>Erzeugt aus frontend/src/icons.ts (npm run icons): eigene Strich-Icons auf 24×24, stroke-width 2, runde Enden, Farbe = currentColor. Groß 40 px, darunter 20 und 16 px.</p>
<div class="grid">
${cells}
</div></body></html>
`
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  mkdirSync(SHEET_DIR, { recursive: true })
  writeFileSync(SHEET_HTML, iconSheet(ICONS))
  // A profile of its own: with the user's, the call would hand over to a Chrome already open.
  const profile = mkdtempSync(join(tmpdir(), 'icon-sheet-'))
  execFileSync('google-chrome', [
    '--headless=new',
    `--user-data-dir=${profile}`,
    '--hide-scrollbars',
    `--window-size=${PICTURE_SIZE}`,
    `--screenshot=${fileURLToPath(SHEET_PNG)}`,
    SHEET_HTML.href,
  ])
  rmSync(profile, { recursive: true })
}
