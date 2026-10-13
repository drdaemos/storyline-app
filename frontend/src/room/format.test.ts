import { keywordList, loreTitle, outcomeTone, prettyJson } from './format'

describe('prettyJson', () => {
  it('indents JSON and leaves anything else alone', () => {
    expect(prettyJson('{"a":1}')).toBe('{\n  "a": 1\n}')
    expect(prettyJson('not json')).toBe('not json')
    expect(prettyJson('')).toBe('')
  })
})

describe('outcomeTone', () => {
  it('tells pending, done and trouble apart', () => {
    expect(outcomeTone('working')).toBe('pending')
    expect(outcomeTone('success')).toBe('done')
    expect(outcomeTone('retry')).toBe('trouble')
    expect(outcomeTone('interrupted')).toBe('trouble')
    expect(outcomeTone('error')).toBe('trouble')
  })
})

describe('loreTitle', () => {
  it('drops the extension', () => {
    expect(loreTitle('ines.md')).toBe('ines')
    expect(loreTitle('notes')).toBe('notes')
  })
})

describe('keywordList', () => {
  it('accepts a list, a comma separated string, or nothing', () => {
    expect(keywordList(['a', ' b '])).toEqual(['a', 'b'])
    expect(keywordList('a, b,, c')).toEqual(['a', 'b', 'c'])
    expect(keywordList(null)).toEqual([])
  })
})
