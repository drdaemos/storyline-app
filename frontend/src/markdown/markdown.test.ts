import { freshInkStart, renderMarkdown, stripLoreHeader } from './markdown'

describe('renderMarkdown', () => {
  it('renders Markdown', () => {
    const html = renderMarkdown('# Title\n\nSome *emphasis* and a [link](https://example.com).')
    expect(html).toContain('<h1>Title</h1>')
    expect(html).toContain('<em>emphasis</em>')
    expect(html).toContain('href="https://example.com"')
  })

  it('does not let raw HTML through', () => {
    const html = renderMarkdown('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>')
    expect(html).not.toContain('<script')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;script&gt;')
  })

  it('does not make links out of script URLs', () => {
    expect(renderMarkdown('[x](javascript:alert(1))')).not.toContain('href="javascript:')
  })

  it('opens links in a new tab without handing over the opener', () => {
    expect(renderMarkdown('[x](https://example.com)')).toContain('rel="noopener noreferrer"')
  })

  it('marks no block as fresh without a boundary', () => {
    expect(renderMarkdown('One.\n\nTwo.')).not.toContain('fresh')
  })

  it('marks the blocks after the boundary as fresh and leaves the earlier ones', () => {
    const old = 'First paragraph.\n\nSecond paragraph.\n'
    const text = `${old}\nThird paragraph.\n\nFourth paragraph.\n`
    const html = renderMarkdown(text, { freshFrom: freshInkStart(old, text) })
    expect(html).toContain('<p>First paragraph.</p>')
    expect(html).toContain('<p>Second paragraph.</p>')
    expect(html).toContain('<p class="fresh">Third paragraph.</p>')
    expect(html).toContain('<p class="fresh">Fourth paragraph.</p>')
  })

  it('marks a paragraph the writer carried on in', () => {
    const old = 'She went home.'
    const text = 'She went home. The door was open.\n\nNew scene.'
    const html = renderMarkdown(text, { freshFrom: freshInkStart(old, text) })
    expect(html).toContain('<p class="fresh">She went home. The door was open.</p>')
    expect(html).toContain('<p class="fresh">New scene.</p>')
  })

  it('marks other kinds of block too', () => {
    const old = 'Intro.\n'
    const text = `${old}\n- one\n- two\n\n> quoted\n\n---\n`
    const html = renderMarkdown(text, { freshFrom: freshInkStart(old, text) })
    expect(html).toContain('<ul class="fresh">')
    expect(html).toContain('<blockquote class="fresh">')
    expect(html).toContain('<hr class="fresh">')
    expect(html).toContain('<p>Intro.</p>')
  })

  it('counts a Windows line ending as one character', () => {
    const old = 'One.\r\n'
    const text = 'One.\r\n\r\nTwo.'
    const html = renderMarkdown(text, { freshFrom: freshInkStart(old, text) })
    expect(html).toContain('<p>One.</p>')
    expect(html).toContain('<p class="fresh">Two.</p>')
  })
})

describe('freshInkStart', () => {
  it('is where the new text begins when the old text is its start', () => {
    expect(freshInkStart('Hello', 'Hello world')).toBe(5)
  })

  it('is null when there is no baseline', () => {
    expect(freshInkStart(null, 'Hello')).toBeNull()
  })

  it('is null when nothing was added', () => {
    expect(freshInkStart('Hello', 'Hello')).toBeNull()
  })

  it('is null when the old text was edited rather than extended', () => {
    expect(freshInkStart('Hello there', 'Hello world, and more')).toBeNull()
    expect(freshInkStart('A longer old text', 'Short')).toBeNull()
  })

  it('treats the whole text as new when the baseline was empty', () => {
    expect(freshInkStart('', 'Everything is new')).toBe(0)
  })
})

describe('stripLoreHeader', () => {
  it('removes a leading summary and keywords header', () => {
    const text = '---\nsummary: Keeper of the station.\nkeywords: ines, keeper\n---\n\n# Ines\n\nFifty-eight.\n'
    expect(stripLoreHeader(text)).toBe('# Ines\n\nFifty-eight.\n')
  })

  it('handles Windows line endings', () => {
    expect(stripLoreHeader('---\r\nsummary: x\r\n---\r\nBody\r\n')).toBe('Body\n')
  })

  it('handles an empty header', () => {
    expect(stripLoreHeader('---\n---\nBody')).toBe('Body')
  })

  it('leaves text without a header alone', () => {
    const text = '# Ines\n\nShe is tired.\n'
    expect(stripLoreHeader(text)).toBe(text)
  })

  it('leaves a thematic break in the middle of the text alone', () => {
    const text = 'Before\n\n---\n\nAfter'
    expect(stripLoreHeader(text)).toBe(text)
  })

  it('leaves text alone when the header never closes', () => {
    const text = '---\nsummary: unfinished\n\nBody'
    expect(stripLoreHeader(text)).toBe(text)
  })

  it('only removes the first header', () => {
    expect(stripLoreHeader('---\na: 1\n---\nBody\n---\nb: 2\n---\n')).toBe('Body\n---\nb: 2\n---\n')
  })
})
