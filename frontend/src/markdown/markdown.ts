/** Markdown for replies, script and lore: rendered without raw HTML, with optional "fresh ink" blocks. */
import MarkdownIt from 'markdown-it'
import type { Env, MarkdownIt as Markdown, StateCore } from 'markdown-it'

const FRESH_CLASS = 'fresh'

function normalise(text: string): string {
  return text.replace(/\r\n?/g, '\n')
}

/** Give every top-level block that holds text from `freshFrom` on the `fresh` class. */
function markFreshBlocks(state: StateCore, freshFrom: number): void {
  const lineStarts: number[] = [0]
  for (let index = 0; index < state.src.length; index++) {
    if (state.src[index] === '\n') lineStarts.push(index + 1)
  }
  const offsetOfLine = (line: number): number => lineStarts[line] ?? state.src.length
  for (const token of state.tokens) {
    if (token.level !== 0 || token.nesting === -1 || !token.map) continue
    const start = Math.max(offsetOfLine(token.map[0]), freshFrom)
    if (state.src.slice(start, offsetOfLine(token.map[1])).trim() !== '') token.attrJoin('class', FRESH_CLASS)
  }
}

function createRenderer(): Markdown {
  const md = new MarkdownIt({ html: false, linkify: true, breaks: false, typographer: true })

  const defaultLinkOpen =
    md.renderer.rules.link_open ??
    ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))
  md.renderer.rules.link_open = (tokens, index, options, env, self) => {
    const token = tokens[index]
    if (token) {
      token.attrSet('target', '_blank')
      token.attrSet('rel', 'noopener noreferrer')
    }
    return defaultLinkOpen(tokens, index, options, env, self)
  }

  md.core.ruler.push('fresh_ink', (state) => {
    const freshFrom = state.env.freshFrom as number | undefined
    if (freshFrom !== undefined) markFreshBlocks(state, freshFrom)
  })
  return md
}

const renderer = createRenderer()

/**
 * Render Markdown to HTML. Raw HTML in `text` is shown as text. With `freshFrom`, every top-level block that
 * contains text from that offset on gets the `fresh` class.
 */
export function renderMarkdown(text: string, options: { freshFrom?: number | null } = {}): string {
  // `freshFrom` travels to the core rule through the render environment.
  const env: Env = {}
  if (options.freshFrom !== undefined && options.freshFrom !== null) env.freshFrom = options.freshFrom
  return renderer.render(normalise(text), env)
}

/**
 * Where the text added since `baseline` begins in `current`, or null when nothing was added or the
 * old text was changed rather than extended.
 */
export function freshInkStart(baseline: string | null, current: string): number | null {
  if (baseline === null) return null
  const before = normalise(baseline)
  const after = normalise(current)
  if (after.length <= before.length || !after.startsWith(before)) return null
  return before.length
}

const LORE_HEADER = /^﻿?---[ \t]*\n(?:[\s\S]*?\n)?---[ \t]*(?:\n|$)/

/** Drop the leading `---` summary/keywords header of a lore file; text without one is returned unchanged. */
export function stripLoreHeader(text: string): string {
  const normalised = normalise(text)
  const match = LORE_HEADER.exec(normalised)
  if (!match) return text
  return normalised.slice(match[0].length).replace(/^(?:[ \t]*\n)+/, '')
}
