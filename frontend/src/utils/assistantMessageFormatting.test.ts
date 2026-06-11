import { describe, expect, it } from 'vitest'
import {
  hasPendingSpecialXmlTag,
  renderAssistantMessageHtml,
  renderPlainTextHtml,
} from './assistantMessageFormatting'

describe('assistantMessageFormatting', () => {
  it('renders plain text safely and converts line breaks', () => {
    const result = renderPlainTextHtml('<script>alert(1)</script>\nnext')
    expect(result).toBe('&lt;script&gt;alert(1)&lt;/script&gt;<br>next')
  })

  it('renders basic markdown-like assistant formatting', () => {
    const result = renderAssistantMessageHtml('**Bold** *italics* `code`')
    expect(result).toContain('<strong>Bold</strong>')
    expect(result).toContain('<em>italics</em>')
    expect(result).toContain('<code')
    expect(result).toContain('code')
  })

  it('keeps unmatched markup markers as literal text', () => {
    const result = renderAssistantMessageHtml('**unfinished')
    expect(result).toBe('**unfinished')
  })

  it('detects pending special update tags and ignores completed tags', () => {
    expect(hasPendingSpecialXmlTag('<character_update>{', ['character_update'])).toBe(true)
    expect(
      hasPendingSpecialXmlTag(
        '<character_update>{\"name\":\"A\"}</character_update>',
        ['character_update']
      )
    ).toBe(false)
  })
})
