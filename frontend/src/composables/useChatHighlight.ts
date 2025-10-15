import { ChatHighlightVisitor, parseChatMessage } from '@/parsers/chatHighlightParser.ts'

export function useChatHighlight() {
  const highlight = (text: string) => {
    const cst = parseChatMessage(text)
    const highlighter = new ChatHighlighter()
    return highlighter.visit(cst).join('')
  }

  return {
    highlight,
  }
}

class ChatHighlighter extends ChatHighlightVisitor {
  constructor() {
    super()
    this.validateVisitor()
  }

  document(ctx: any) {
    return ctx.segment?.flatMap((s: any) => this.visit(s)) || []
  }

  segment(ctx: any) {
    if (ctx.doubleDialogue) return this.visit(ctx.doubleDialogue)
    if (ctx.singleDialogue) return this.visit(ctx.singleDialogue)
    if (ctx.action) return this.visit(ctx.action)
    if (ctx.narration) return this.visit(ctx.narration)
    if (ctx.linebreak) return this.visit(ctx.linebreak)
    if (ctx.taggedData) return this.visit(ctx.taggedData)
  }

  doubleDialogue(ctx: any) {
    const content = this.extractContent(ctx)
    return `<span class="text-highlighted">${content}</span>`
  }

  singleDialogue(ctx: any) {
    const content = this.extractContent(ctx)
    return `<span class="text-highlighted">${content}</span>`
  }

  action(ctx: any) {
    const content = this.extractContent(ctx)
    return `<span class="italic text-muted">${content}</span>`
  }

  narration(ctx: any) {
    const content = this.extractContent(ctx)
    return `<span class="text-default">${content}</span>`
  }

  linebreak(_ctx: any) {
    return `<br /><br />`
  }

  tag(_ctx: any) {
    return ``
  }

  taggedData(ctx: any) {
    const content = this.extractContent(ctx)
    console.log(ctx, content)
    return `<p class="text-dimmed"><span>📄</span>&nbsp;&nbsp;<span class="blur-xs hover:blur-none cursor-pointer">${content}</span></p>`
  }

  private extractContent(ctx: any): string {
    // Flatten all token arrays and preserve order
    const tokens: any[] = []

    for (const key of Object.keys(ctx)) {
      const value = ctx[key]
      if (Array.isArray(value)) {
        tokens.push(...value)
      }
    }

    // Sort by position to maintain original order
    tokens.sort((a, b) => {
      if (a.startOffset !== b.startOffset) {
        return a.startOffset - b.startOffset
      }
      return 0
    })

    return tokens.map((t) => t.image).join('')
  }
}
