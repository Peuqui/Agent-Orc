// A text cut after a whole letter so that it is at most `maxWidth` pixels wide in `font` (the
// letters differ in width, so a count of letters would not do); no ellipsis, the full text is
// shown elsewhere.
const canvas = document.createElement('canvas').getContext('2d')

export function textWidth(text: string, font: string): number {
  if (canvas === null) throw new Error('No canvas to measure text with')
  canvas.font = font
  return canvas.measureText(text).width
}

export function fitLabel(text: string, maxWidth: number, font: string): string {
  let length = text.length
  while (length > 1 && textWidth(text.slice(0, length), font) > maxWidth) length--
  return text.slice(0, length)
}
