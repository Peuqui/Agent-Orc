// A Word document (.docx) as a page, converted in the browser by mammoth. The library is loaded
// only when such a document is opened.
import DOMPurify from 'dompurify'

/** The document's content as HTML, cleaned like every page shown here (pictures come inline). */
export async function docxToHtml(url: string): Promise<string> {
  const [{ default: mammoth }, response] = await Promise.all([import('mammoth'), fetch(url)])
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  const result = await mammoth.convertToHtml({ arrayBuffer: await response.arrayBuffer() })
  return DOMPurify.sanitize(result.value)
}
