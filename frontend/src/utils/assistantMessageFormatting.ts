const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const SPECIAL_TAG_PATTERN = /<\/?([a-z][a-z0-9_]*)>/gi
const DEFAULT_SPECIAL_TAG = /_update$/i

const withLineBreaks = (value: string): string => value.replace(/\r?\n/g, '<br>')

export const renderPlainTextHtml = (rawText: string): string => withLineBreaks(escapeHtml(rawText))

export const renderAssistantMessageHtml = (rawText: string): string => {
  let html = escapeHtml(rawText)

  const codePlaceholders: string[] = []
  html = html.replace(/`([^`\n]+)`/g, (_match, codeText: string) => {
    const token = `__CODE_TOKEN_${codePlaceholders.length}__`
    codePlaceholders.push(
      `<code class="rounded-sm bg-background/80 px-1 py-0.5 font-mono text-[0.92em]">${codeText}</code>`
    )
    return token
  })

  html = html.replace(/\*\*([^\s*](?:[^*\n]*[^\s*])?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^\s*](?:[^*\n]*[^\s*])?)\*/g, '<em>$1</em>')

  html = withLineBreaks(html)

  for (let index = 0; index < codePlaceholders.length; index += 1) {
    html = html.replace(`__CODE_TOKEN_${index}__`, codePlaceholders[index])
  }

  return html
}

export const hasPendingSpecialXmlTag = (
  rawText: string,
  allowedTagNames?: string[]
): boolean => {
  const stack: string[] = []
  const allowedSet = allowedTagNames ? new Set(allowedTagNames.map((name) => name.toLowerCase())) : null

  for (const match of rawText.matchAll(SPECIAL_TAG_PATTERN)) {
    const full = match[0]
    const tagName = (match[1] || '').toLowerCase()

    if (!tagName) {
      continue
    }

    const isAllowed = allowedSet ? allowedSet.has(tagName) : DEFAULT_SPECIAL_TAG.test(tagName)
    if (!isAllowed) {
      continue
    }

    const isClosing = full.startsWith('</')
    if (isClosing) {
      const openIndex = stack.lastIndexOf(tagName)
      if (openIndex >= 0) {
        stack.splice(openIndex, 1)
      }
      continue
    }

    stack.push(tagName)
  }

  return stack.length > 0
}
