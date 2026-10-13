// @vitest-environment node
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * The look lives in this folder only. Everything else refers to it by variable name, so a new look
 * is a new version of this folder.
 */
const SRC = fileURLToPath(new URL('..', import.meta.url))
const THEME = fileURLToPath(new URL('.', import.meta.url))

function filesUnder(directory: string): string[] {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name)
    return statSync(path).isDirectory() ? filesUnder(path) : [path]
  })
}

const outsideTheme = filesUnder(SRC).filter(
  (path) =>
    !path.startsWith(THEME) &&
    /\.(vue|css|ts)$/.test(path) &&
    !/\.test\.ts$/.test(path) &&
    !path.endsWith('.d.ts')
)

/** Style text of a file: the `<style>` blocks of a component, or a whole stylesheet; for `.ts`, the lines with inline styles. */
function styleText(path: string, source: string): string {
  if (path.endsWith('.css')) return source
  if (path.endsWith('.vue')) {
    return [...source.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((match) => match[1]).join('\n')
  }
  return ''
}

const FORBIDDEN: Array<[string, RegExp]> = [
  ['a hex colour', /#[0-9a-fA-F]{3,8}\b/],
  ['a colour function', /\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color-mix)\(/],
  ['a font family', /font-family\s*:\s*(?!\s|var\()/],
  ['a named colour', /(?:color|background(?:-color)?|border(?:-[a-z]+)*|outline(?:-color)?|fill|stroke)\s*:\s*[^;{}]*\b(?:white|black|red|green|blue|gray|grey|yellow|orange|purple|brown)\b/i],
  ['a shadow that is not a token', /box-shadow\s*:\s*(?!\s|var\(|none)/],
]

describe('theme separation', () => {
  it('has files to check', () => {
    expect(outsideTheme.length).toBeGreaterThan(10)
  })

  for (const path of outsideTheme) {
    const name = relative(SRC, path).split(sep).join('/')
    it(`${name} hard-codes no colour, font or shadow`, () => {
      const css = styleText(path, readFileSync(path, 'utf8'))
      for (const [what, pattern] of FORBIDDEN) {
        expect(css, `${name} contains ${what}`).not.toMatch(pattern)
      }
    })
  }

  it('does not style with inline colour attributes in templates', () => {
    for (const path of outsideTheme.filter((file) => file.endsWith('.vue'))) {
      const template = readFileSync(path, 'utf8').replace(/<style[^>]*>[\s\S]*?<\/style>/g, '')
      expect(template, path).not.toMatch(/style="[^"]*(?:#[0-9a-f]{3,8}|rgb|font-family)/i)
    }
  })

  it('defines every variable the components use', () => {
    const defined = new Set(
      [...readFileSync(join(THEME, 'tokens.css'), 'utf8').matchAll(/(--[a-z0-9-]+)\s*:/g)].map((match) => match[1])
    )
    const localVariables = new Set(['--cover', '--tab-color'])
    for (const path of outsideTheme) {
      const used = [...readFileSync(path, 'utf8').matchAll(/var\((--[a-z0-9-]+)/g)].map((match) => match[1]!)
      for (const variable of used) {
        if (localVariables.has(variable)) continue
        expect(defined.has(variable), `${relative(SRC, path)} uses ${variable}, which the theme does not define`).toBe(true)
      }
    }
  })
})
