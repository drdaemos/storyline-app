import { describe, it, expect, beforeEach } from 'vitest'
import { useChatHighlight } from './useChatHighlight.ts'

describe('useChatHighlight', () => {
  let highlight: (text: string) => string

  beforeEach(() => {
    const { highlight: highlightFn } = useChatHighlight()
    highlight = highlightFn
  })

  describe('mixed content', () => {
    it('should correctly highlight mixed narration, dialogue, and actions', () => {
      const input = `Georgie's apartment glowed under the dimmed lights. She was wearing a robe, clinging to her 5'10" frame, and walking towards Josh.

"I invited you here for a reason...", she confesses. *Her skin is trembling with hesitation. City's nightlife humming faintly through the windows*

'I see...', a whisper responded from his side.`
      const output = highlight(input)

      expect(output).toContain(`<span class="text-default">Georgie's apartment glowed`)
      expect(output).toContain(`<span class="text-highlighted">"I invited you here for a reason..."</span>`)
      expect(output).toContain(`<span class="text-highlighted">'I see...'</span>`)
      expect(output).toContain('<br /><br />')
    })
  })

  describe('narration text', () => {
    it('should wrap plain text in narration span', () => {
      const input = 'The sun was setting over the hills.'
      const output = highlight(input)

      expect(output).toContain('class="text-default"')
      expect(output).toContain('The sun was setting over the hills.')
    })

    it('should handle empty string', () => {
      const output = highlight('')
      expect(output).toBe('')
    })
  })

  describe('dialogue', () => {
    it('should highlight quoted text as dialogue', () => {
      const input = '"Hello, how are you?"'
      const output = highlight(input)

      expect(output).toContain('class="text-highlighted')
      expect(output).toContain('Hello, how are you?')
    })

    it('should handle escaped quotes in dialogue', () => {
      const input = '"She said \\"hello\\" to me."'
      const output = highlight(input)

      expect(output).toContain('class="text-highlighted')
      expect(output).toContain('She said')
      expect(output).toContain('hello')
      expect(output).toContain('to me.')
    })
  })

  describe('physical actions', () => {
    it('should highlight text in asterisks as physical action', () => {
      const input = '*waves hand*'
      const output = highlight(input)

      expect(output).toContain('class="italic text-muted"')
      expect(output).toContain('waves hand')
    })
  })

  describe('whitespace', () => {
    it('should handle text with multiple spaces', () => {
      const input = 'Hello  world'
      const output = highlight(input)

      expect(output).toContain('Hello  world')
    })
  })
})
