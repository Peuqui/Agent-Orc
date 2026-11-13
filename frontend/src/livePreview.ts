// Markdown edited as it looks (a note): one field, no separate view. Where the cursor is not, the
// marks of the syntax are hidden and their text is shown as it means (a heading large, bold bold, a
// link as a link, a picture as a picture); the lines the cursor is on show the Markdown to edit.
// Without the focus, the whole note is shown so. The text itself stays plain Markdown.
import { ensureSyntaxTree, HighlightStyle, syntaxTree } from '@codemirror/language'
import { type EditorState, type Extension, type Range, StateEffect, StateField } from '@codemirror/state'
import { Decoration, type DecorationSet, EditorView, ViewPlugin, WidgetType } from '@codemirror/view'
import { tags } from '@lezer/highlight'
import { iconMarkup } from './icons'

export interface PreviewActions {
  /** A link or picture tapped: opens it (a tab of its own, the note stays). */
  openLink: (href: string) => void
  /** Code tapped (in a sentence) or its block's button: to the clipboard. */
  copy: (text: string) => void
  /** Markdown of a block drawn as a whole (a table) as safe HTML. */
  renderBlock: (markdown: string) => string
  /** The label of a code block's copy button. */
  copyLabel: string
}

// How long the field waits for the parser on a change; a note is parsed in far less.
const PARSE_BUDGET_MS = 100
const LINK_ATTRIBUTE = 'data-href'
const COPY_CLASS = 'cm-md-copy'

/** A flag of the editor's state, set by an effect. */
function flag() {
  const set = StateEffect.define<boolean>()
  const field = StateField.define<boolean>({
    create: () => false,
    update: (value, transaction) => transaction.effects.reduce((current, effect) => (effect.is(set) ? effect.value : current), value),
  })
  return { set, field }
}
const focused = flag()
// While the mouse button is down, what is shown stays as it is: the editor takes the cursor's place
// from the pointer again when the button comes up, and a line that had shown its marks by then
// (wider, a table taller) put another place under the pointer, a selection instead of a cursor.
const pointerDown = flag()

const pointerTracker = ViewPlugin.fromClass(
  class {
    constructor(readonly view: EditorView) {
      view.dom.ownerDocument.addEventListener('mouseup', this.release)
    }
    // After the editor's own handling of the button coming up, which sets the cursor.
    release = (): void => {
      if (this.view.state.field(pointerDown.field)) setTimeout(() => this.view.dispatch({ effects: pointerDown.set.of(false) }))
    }
    destroy(): void {
      this.view.dom.ownerDocument.removeEventListener('mouseup', this.release)
    }
  },
  {
    eventHandlers: {
      mousedown(event) {
        if (event.button === 0) this.view.dispatch({ effects: pointerDown.set.of(true) })
        return false
      },
    },
  },
)

/** A picture in place of its Markdown; a tap opens it at full size. */
class ImageWidget extends WidgetType {
  constructor(
    readonly source: string,
    readonly alt: string,
    readonly actions: PreviewActions,
  ) {
    super()
  }
  eq(other: ImageWidget): boolean {
    return other.source === this.source && other.alt === this.alt
  }
  toDOM(): HTMLElement {
    const image = document.createElement('img')
    image.className = 'cm-md-image'
    image.src = this.source
    image.alt = this.alt
    // Events in a widget do not reach the editor's handlers (tapHandler): it listens itself.
    image.addEventListener('mousedown', (event) => {
      event.preventDefault()
      this.actions.openLink(this.source)
    })
    return image
  }
}

/** Text in place of a mark: the bullet of a list. */
class SymbolWidget extends WidgetType {
  constructor(
    readonly symbol: string,
    readonly className: string,
  ) {
    super()
  }
  eq(other: SymbolWidget): boolean {
    return other.symbol === this.symbol && other.className === this.className
  }
  toDOM(): HTMLElement {
    const element = document.createElement('span')
    element.className = this.className
    element.textContent = this.symbol
    return element
  }
}

class RuleWidget extends WidgetType {
  eq(): boolean {
    return true
  }
  toDOM(): HTMLElement {
    const rule = document.createElement('hr')
    rule.className = 'cm-md-rule'
    return rule
  }
}

/** The box of a task ("- [ ]"): a tap ticks it in the text. */
class TaskWidget extends WidgetType {
  constructor(
    readonly done: boolean,
    readonly at: number,
  ) {
    super()
  }
  eq(other: TaskWidget): boolean {
    return other.done === this.done && other.at === this.at
  }
  toDOM(view: EditorView): HTMLElement {
    const box = document.createElement('input')
    box.type = 'checkbox'
    box.className = 'cm-md-task'
    box.checked = this.done
    box.addEventListener('mousedown', (event) => {
      event.preventDefault()
      // The letter between the brackets.
      view.dispatch({ changes: { from: this.at + 1, to: this.at + 2, insert: this.done ? ' ' : 'x' } })
    })
    return box
  }
}

class CopyWidget extends WidgetType {
  constructor(
    readonly code: string,
    readonly actions: PreviewActions,
  ) {
    super()
  }
  eq(other: CopyWidget): boolean {
    return other.code === this.code
  }
  toDOM(): HTMLElement {
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'cm-md-copy-block'
    button.title = this.actions.copyLabel
    button.setAttribute('aria-label', this.actions.copyLabel)
    button.innerHTML = iconMarkup('copy')
    button.addEventListener('mousedown', (event) => {
      event.preventDefault()
      this.actions.copy(this.code)
    })
    return button
  }
}

/** A block shown as a whole (a table); a tap on it puts the cursor there, which shows its text. */
class BlockWidget extends WidgetType {
  constructor(
    readonly markdown: string,
    readonly actions: PreviewActions,
  ) {
    super()
  }
  eq(other: BlockWidget): boolean {
    return other.markdown === this.markdown
  }
  toDOM(): HTMLElement {
    const block = document.createElement('div')
    block.className = 'cm-md-block markdown note'
    // renderBlock passes the HTML through DOMPurify.
    block.innerHTML = this.actions.renderBlock(this.markdown)
    return block
  }
  ignoreEvent(): boolean {
    return false
  }
}

const HEADING = /^(?:ATX|Setext)Heading(\d)$/
// Links whose address is their own text: the address gets no mark of its own.
const LINK_PARENTS = new Set(['Link', 'Image', 'Autolink'])

function decorationsOf(state: EditorState, actions: PreviewActions): DecorationSet {
  const doc = state.doc
  const tree = ensureSyntaxTree(state, doc.length, PARSE_BUDGET_MS) ?? syntaxTree(state)
  const hasFocus = state.field(focused.field)
  /** Whether the cursor (a selection) is on one of the lines of the range: then it is edited. */
  const edited = (from: number, to: number): boolean => {
    if (!hasFocus) return false
    const start = doc.lineAt(from).from
    const end = doc.lineAt(to).to
    return state.selection.ranges.some((range) => range.from <= end && range.to >= start)
  }
  const found: Range<Decoration>[] = []
  const hide = (from: number, to: number): void => {
    if (from < to) found.push(Decoration.replace({}).range(from, to))
  }
  /** A mark at the start of a line and the space after it ("# ", "> "). */
  const hideWithSpace = (from: number, to: number): void => hide(from, doc.sliceString(to, to + 1) === ' ' ? to + 1 : to)
  const mark = (from: number, to: number, className: string, attributes?: Record<string, string>): void => {
    if (from < to) found.push(Decoration.mark({ class: className, attributes }).range(from, to))
  }
  const lines = (from: number, to: number, className: (index: number, count: number) => string): void => {
    const first = doc.lineAt(from).number
    const last = doc.lineAt(to).number
    for (let number = first; number <= last; number++) {
      found.push(Decoration.line({ class: className(number - first, last - first + 1) }).range(doc.line(number).from))
    }
  }

  tree.iterate({
    enter: (node) => {
      const shown = !edited(node.from, node.to)
      const heading = HEADING.exec(node.name)
      if (heading) {
        found.push(Decoration.line({ class: `cm-md-h${heading[1]}` }).range(doc.lineAt(node.from).from))
        return
      }
      switch (node.name) {
        case 'HeaderMark':
          if (shown) {
            // Setext: the line of "===" below the heading; ATX: the "#" in front (and any after).
            if (node.node.parent?.name.startsWith('Setext')) hide(node.from, node.to)
            else if (node.from === doc.lineAt(node.from).from) hideWithSpace(node.from, node.to)
            else hide(node.from, node.to)
          }
          return
        case 'Emphasis':
          mark(node.from, node.to, 'cm-md-em')
          return
        case 'StrongEmphasis':
          mark(node.from, node.to, 'cm-md-strong')
          return
        case 'Strikethrough':
          mark(node.from, node.to, 'cm-md-strike')
          return
        case 'EmphasisMark':
        case 'StrikethroughMark':
          if (shown) hide(node.from, node.to)
          return
        case 'InlineCode': {
          const marks = node.node.getChildren('CodeMark')
          const open = marks[0]
          const close = marks[marks.length - 1]
          if (!shown || !open || !close || open === close) {
            mark(node.from, node.to, 'cm-md-code')
            return false
          }
          hide(open.from, open.to)
          mark(open.to, close.from, `cm-md-code ${COPY_CLASS}`)
          hide(close.from, close.to)
          return false
        }
        case 'Link': {
          const linkMarks = node.node.getChildren('LinkMark')
          const url = node.node.getChild('URL')
          // "[text](address)": the text stays, as a link; a reference link only looks like one.
          if (shown && linkMarks.length >= 2 && url) {
            hide(node.from, linkMarks[0]!.to)
            mark(linkMarks[0]!.to, linkMarks[1]!.from, 'cm-md-link', { [LINK_ATTRIBUTE]: doc.sliceString(url.from, url.to) })
            hide(linkMarks[1]!.from, node.to)
          } else mark(node.from, node.to, 'cm-md-link-source')
          return
        }
        case 'Image': {
          const url = node.node.getChild('URL')
          const linkMarks = node.node.getChildren('LinkMark')
          if (!shown || !url || linkMarks.length < 2) {
            mark(node.from, node.to, 'cm-md-link-source')
            return false
          }
          const alt = doc.sliceString(linkMarks[0]!.to, linkMarks[1]!.from)
          found.push(Decoration.replace({ widget: new ImageWidget(doc.sliceString(url.from, url.to), alt, actions) }).range(node.from, node.to))
          return false
        }
        case 'Autolink': {
          const url = node.node.getChild('URL')
          if (shown && url) {
            hide(node.from, url.from)
            mark(url.from, url.to, 'cm-md-link', { [LINK_ATTRIBUTE]: doc.sliceString(url.from, url.to) })
            hide(url.to, node.to)
          }
          return false
        }
        case 'URL':
          // A bare address in the text (the parents above handle their own).
          if (!LINK_PARENTS.has(node.node.parent?.name ?? '') && shown) {
            mark(node.from, node.to, 'cm-md-link', { [LINK_ATTRIBUTE]: doc.sliceString(node.from, node.to) })
          }
          return
        case 'Blockquote':
          lines(node.from, node.to, () => 'cm-md-quote')
          return
        case 'QuoteMark':
          if (!edited(node.from, node.from)) hideWithSpace(node.from, node.to)
          return
        case 'ListMark': {
          if (!shown) return
          const task = node.node.nextSibling?.name === 'Task'
          // A task shows its box only; a bullet becomes a dot; a number stays.
          if (task) hideWithSpace(node.from, node.to)
          else if (node.node.parent?.parent?.name === 'BulletList') {
            found.push(Decoration.replace({ widget: new SymbolWidget('•', 'cm-md-bullet') }).range(node.from, node.to))
          }
          return
        }
        case 'TaskMarker':
          if (shown) {
            const done = doc.sliceString(node.from + 1, node.from + 2).toLowerCase() === 'x'
            found.push(Decoration.replace({ widget: new TaskWidget(done, node.from) }).range(node.from, node.to))
          }
          return
        case 'HorizontalRule':
          if (shown) found.push(Decoration.replace({ widget: new RuleWidget() }).range(node.from, node.to))
          return
        case 'FencedCode':
        case 'CodeBlock': {
          lines(node.from, node.to, (index, count) =>
            ['cm-md-codeblock', index === 0 ? 'cm-md-codeblock-first' : '', index === count - 1 ? 'cm-md-codeblock-last' : ''].join(' '),
          )
          const text = node.node.getChild('CodeText')
          const code = text ? doc.sliceString(text.from, text.to) : ''
          if (node.name === 'FencedCode') {
            const fences = node.node.getChildren('CodeMark')
            if (shown) for (const fence of fences) mark(fence.from, doc.lineAt(fence.from).to, 'cm-md-fence')
          }
          if (code) found.push(Decoration.widget({ widget: new CopyWidget(code.replace(/\n$/, ''), actions), side: 1 }).range(doc.lineAt(node.from).to))
          return false
        }
        case 'Table':
          if (!shown) return false
          found.push(
            Decoration.replace({ widget: new BlockWidget(doc.sliceString(node.from, node.to), actions), block: true }).range(
              doc.lineAt(node.from).from,
              doc.lineAt(node.to).to,
            ),
          )
          return false
      }
    },
  })
  return Decoration.set(found, true)
}

/** A tap on a link or a picture opens it, one on code in a sentence copies it; anything else is
 * left to the editor (it puts the cursor there). */
function tapHandler(actions: PreviewActions): Extension {
  return EditorView.domEventHandlers({
    mousedown(event) {
      if (!(event.target instanceof Element) || event.button !== 0) return false
      const link = event.target.closest(`[${LINK_ATTRIBUTE}]`)
      const code = event.target.closest(`.${COPY_CLASS}`)
      if (link) actions.openLink(link.getAttribute(LINK_ATTRIBUTE) ?? '')
      else if (code) actions.copy(code.textContent ?? '')
      else return false
      event.preventDefault()
      return true
    },
  })
}

/** Colours of code in a code block (in the languages CodeMirror knows); the Markdown itself is
 * styled by the classes above, in style.css. */
export const codeHighlight = HighlightStyle.define([
  { tag: [tags.keyword, tags.operatorKeyword, tags.modifier], color: 'var(--color-accent-300)' },
  { tag: [tags.string, tags.special(tags.string), tags.regexp], color: 'var(--color-highlight-200)' },
  { tag: [tags.comment, tags.meta], color: 'var(--color-muted)', fontStyle: 'italic' },
  { tag: [tags.number, tags.bool, tags.null, tags.atom], color: 'var(--color-info-400)' },
  { tag: [tags.function(tags.variableName), tags.function(tags.propertyName)], color: 'var(--color-code)' },
  { tag: [tags.typeName, tags.className], color: 'var(--color-highlight-300)' },
])

export function livePreview(actions: PreviewActions): Extension {
  const preview = StateField.define<DecorationSet>({
    create: (state) => decorationsOf(state, actions),
    update(value, transaction) {
      if (transaction.state.field(pointerDown.field)) return value.map(transaction.changes)
      const flagged = transaction.effects.some((effect) => effect.is(focused.set) || effect.is(pointerDown.set))
      const reparsed = syntaxTree(transaction.state) !== syntaxTree(transaction.startState)
      if (!transaction.docChanged && !transaction.selection && !flagged && !reparsed) return value
      return decorationsOf(transaction.state, actions)
    },
    provide: (field) => EditorView.decorations.from(field),
  })
  return [
    focused.field,
    pointerDown.field,
    EditorView.focusChangeEffect.of((_state, focusing) => focused.set.of(focusing)),
    preview,
    // First: a tap on a link opens it and is no pointer selection.
    tapHandler(actions),
    pointerTracker,
  ]
}
