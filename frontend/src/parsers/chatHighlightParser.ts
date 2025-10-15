import { CstParser, createToken, Lexer } from 'chevrotain'

// === TOKENS ===
const Word = createToken({
  name: 'Word',
  pattern: /[a-zA-Z0-9]+(?:['"][a-zA-Z0-9]+)*/,
  line_breaks: false,
})

const Chevron = createToken({ name: 'Chevron', pattern: /[<>]/ })
const DoubleQuote = createToken({ name: 'DoubleQuote', pattern: /"/ })
const SingleQuote = createToken({ name: 'SingleQuote', pattern: /'/ })
const Asterisk = createToken({ name: 'Asterisk', pattern: /\*/ })

// DON'T SKIP - keep whitespace as tokens
const Whitespace = createToken({
  name: 'Whitespace',
  pattern: /[ \t]+/,
})
const Newline = createToken({
  name: 'Newline',
  pattern: /\n/,
  line_breaks: true,
})

const Punctuation = createToken({
  name: 'Punctuation',
  pattern: /[.,!?;:—–\-()]/,
})

const allTokens = [
  Newline, // Check newline before whitespace
  Whitespace,
  Word,
  DoubleQuote,
  SingleQuote,
  Chevron,
  Asterisk,
  Punctuation,
]

const lexer = new Lexer(allTokens)

// === PARSER ===
class ChatHighlightParser extends CstParser {
  constructor() {
    super(allTokens, {
      recoveryEnabled: true,
      nodeLocationTracking: 'full',
    })
    this.performSelfAnalysis()
  }

  public document = this.RULE('document', () => {
    this.MANY(() => {
      this.SUBRULE(this.segment)
    })
  })

  private segment = this.RULE('segment', () => {
    this.OR([
      { ALT: () => this.SUBRULE(this.doubleDialogue), IGNORE_AMBIGUITIES: true },
      { ALT: () => this.SUBRULE(this.singleDialogue), IGNORE_AMBIGUITIES: true },
      { ALT: () => this.SUBRULE(this.action), IGNORE_AMBIGUITIES: true },
      { ALT: () => this.SUBRULE(this.taggedData) },
      { ALT: () => this.SUBRULE(this.narration) },
      { ALT: () => this.SUBRULE(this.linebreak) },
    ])
  })

  private doubleDialogue = this.RULE('doubleDialogue', () => {
    this.CONSUME(DoubleQuote)
    this.CONSUME(Word)
    this.MANY(() => {
      this.OR([
        { ALT: () => this.CONSUME2(Word) },
        { ALT: () => this.CONSUME(Whitespace) },
        { ALT: () => this.CONSUME(Newline) },
        { ALT: () => this.CONSUME(SingleQuote) },
        { ALT: () => this.CONSUME(Asterisk) },
        { ALT: () => this.CONSUME(Punctuation) },
      ])
    })
    this.CONSUME2(DoubleQuote)
  })

  private singleDialogue = this.RULE('singleDialogue', () => {
    this.CONSUME(SingleQuote)
    this.CONSUME(Word)
    this.MANY(() => {
      this.OR([
        { ALT: () => this.CONSUME2(Word) },
        { ALT: () => this.CONSUME(Whitespace) },
        { ALT: () => this.CONSUME(Newline) },
        { ALT: () => this.CONSUME(DoubleQuote) },
        { ALT: () => this.CONSUME(Asterisk) },
        { ALT: () => this.CONSUME(Punctuation) },
      ])
    })
    this.CONSUME2(SingleQuote)
  })

  private action = this.RULE('action', () => {
    this.CONSUME(Asterisk)
    this.CONSUME(Word)
    this.MANY(() => {
      this.OR([
        { ALT: () => this.CONSUME2(Word) },
        { ALT: () => this.CONSUME(Whitespace) },
        { ALT: () => this.CONSUME(Newline) },
        { ALT: () => this.CONSUME(DoubleQuote) },
        { ALT: () => this.CONSUME(SingleQuote) },
        { ALT: () => this.CONSUME(Punctuation) },
      ])
    })
    this.CONSUME2(Asterisk)
  })

  private tag = this.RULE('tag', () => {
    this.CONSUME(Chevron)
    this.CONSUME(Word)
    this.MANY(() => {
      this.OR([
        { ALT: () => this.CONSUME2(Word) },
        { ALT: () => this.CONSUME(Punctuation) },
      ])
    })
    this.CONSUME2(Chevron)
  })

  private taggedData = this.RULE('taggedData', () => {
    this.SUBRULE(this.tag)
    this.MANY(() => {
      this.OR([
        { ALT: () => this.CONSUME(Word) },
        { ALT: () => this.CONSUME(Whitespace) },
        { ALT: () => this.CONSUME(Newline) },
        { ALT: () => this.CONSUME(DoubleQuote) },
        { ALT: () => this.CONSUME(SingleQuote) },
        { ALT: () => this.CONSUME(Punctuation) },
      ])
    })
    this.SUBRULE2(this.tag)
  })

  private narration = this.RULE('narration', () => {
    this.AT_LEAST_ONE(() => {
      this.OR([
        { ALT: () => this.CONSUME(Word) },
        { ALT: () => this.CONSUME(Whitespace) },
        { ALT: () => this.CONSUME(Punctuation) },
        { ALT: () => this.CONSUME(DoubleQuote) },
        { ALT: () => this.CONSUME(SingleQuote) },
        { ALT: () => this.CONSUME(Asterisk) },
      ])
    })
  })

  private linebreak = this.RULE('linebreak', () => {
    this.AT_LEAST_ONE(() => {
      this.OR([{ ALT: () => this.CONSUME(Newline) }])
    })
  })
}

const parser = new ChatHighlightParser()
export const ChatHighlightVisitor = parser.getBaseCstVisitorConstructor()

export function parseChatMessage(text: string) {
  const lexResult = lexer.tokenize(text)
  parser.input = lexResult.tokens
  const cst = parser.document()

  if (parser.errors.length > 0) {
    console.warn('Parsing errors:', parser.errors)
    // Still returns partial CST with error recovery
  }

  return cst
}
