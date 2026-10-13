/** Small text helpers for showing protocol values. */

/** Pretty-print a JSON string; anything that is not JSON is returned as it came. */
export function prettyJson(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

export type OutcomeTone = 'pending' | 'done' | 'trouble'

/** How to colour a tool call's outcome: `working` until it returns, then done or trouble. */
export function outcomeTone(outcome: string): OutcomeTone {
  if (outcome === 'working') return 'pending'
  if (/retry|interrupt|error|fail|denied|invalid/i.test(outcome)) return 'trouble'
  return 'done'
}

/** The display name of a lore file: its filename without the extension. */
export function loreTitle(filename: string): string {
  return filename.replace(/\.md$/i, '')
}

/** Keywords arrive as a list or as one string; show them as a list either way. */
export function keywordList(keywords: string[] | string | null | undefined): string[] {
  if (!keywords) return []
  const items = Array.isArray(keywords) ? keywords : keywords.split(',')
  return items.map((keyword) => keyword.trim()).filter(Boolean)
}
