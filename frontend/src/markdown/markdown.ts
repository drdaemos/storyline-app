/** Markdown for replies, script and lore: rendered with only collapsible-section HTML, with optional "fresh ink" blocks. */
import MarkdownIt from 'markdown-it'
import type { Env, MarkdownIt as Markdown, StateCore, Token } from 'markdown-it'

const FRESH_CLASS = 'fresh'

/** The only raw HTML that renders: collapsible sections, written as bare tags. Anything else is shown as text. */
const ALLOWED_TAG = /^<\/?(?:details|summary)>$/i
const SPLIT_ALLOWED_TAGS = /(<\/?(?:details|summary)>)/i

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

function textToken(state: StateCore, content: string): Token {
  const token = new state.Token('text', '', 0)
  token.content = content
  return token
}

/** Raw HTML shown as text, in a paragraph of its own. */
function plainParagraph(state: StateCore, text: string): Token[] {
  const open = new state.Token('paragraph_open', 'p', 1)
  const inline = new state.Token('inline', '', 0)
  inline.content = text
  inline.children = [textToken(state, text)]
  const close = new state.Token('paragraph_close', 'p', -1)
  return [open, inline, close]
}

function tagToken(state: StateCore, tag: string): Token {
  const token = new state.Token('html_block', '', 0)
  token.content = `${tag.toLowerCase()}\n`
  return token
}

/** Split a raw HTML block around the allowed tags; the text between them is Markdown. */
function expandHtmlBlock(state: StateCore, content: string): Token[] {
  if (!SPLIT_ALLOWED_TAGS.test(content)) return plainParagraph(state, content.trim())
  const tokens: Token[] = []
  let inSummary = false
  for (const piece of content.split(SPLIT_ALLOWED_TAGS)) {
    if (ALLOWED_TAG.test(piece)) {
      inSummary = piece.toLowerCase() === '<summary>'
      tokens.push(tagToken(state, piece))
      continue
    }
    const text = piece.trim()
    if (text === '') continue
    tokens.push(...(inSummary ? state.md.parseInline(text, {}) : state.md.parse(text, {})))
  }
  for (const token of tokens) token.map = null
  return tokens
}

/** Raw HTML is parsed but not trusted: allowed tags stay, everything else becomes text. */
function restrictHtml(state: StateCore): void {
  state.tokens = state.tokens.flatMap((token) => {
    if (token.type === 'html_block') return expandHtmlBlock(state, token.content)
    for (const child of token.children ?? []) {
      if (child.type === 'html_inline' && !ALLOWED_TAG.test(child.content)) child.type = 'text'
    }
    return [token]
  })
}

function createRenderer(breaks: boolean): Markdown {
  const md = new MarkdownIt({ html: true, linkify: true, breaks, typographer: true })

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

  md.core.ruler.after('inline', 'restrict_html', restrictHtml)
  md.core.ruler.push('fresh_ink', (state) => {
    const freshFrom = state.env.freshFrom as number | undefined
    if (freshFrom !== undefined) markFreshBlocks(state, freshFrom)
  })
  return md
}

const renderer = createRenderer(false)
const chatRenderer = createRenderer(true)

/**
 * Render Markdown to HTML. Raw HTML in `text` is shown as text, except `<details>` and `<summary>`. With `freshFrom`, every top-level block that
 * contains text from that offset on gets the `fresh` class. With `chat`, a single line break in `text` stays a line break.
 */
export function renderMarkdown(
  text: string,
  options: { freshFrom?: number | null; chat?: boolean } = {},
): string {
  // `freshFrom` travels to the core rule through the render environment.
  const env: Env = {}
  if (options.freshFrom !== undefined && options.freshFrom !== null) env.freshFrom = options.freshFrom
  return (options.chat ? chatRenderer : renderer).render(normalise(text), env)
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
