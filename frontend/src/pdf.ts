// PDF pages drawn in the browser (pdf.js). The library is large, so it is loaded only when a note
// holds a PDF.
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

export interface PdfDocument {
  pageCount: number
  /** Draws the page onto the canvas, as wide as `width` CSS pixels (sharp on dense screens). */
  drawPage: (canvas: HTMLCanvasElement, pageNumber: number, width: number) => Promise<void>
  destroy: () => Promise<void>
}

export async function loadPdf(url: string): Promise<PdfDocument> {
  const pdfjs = await import('pdfjs-dist')
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl
  const task = pdfjs.getDocument({ url: new URL(url, window.document.baseURI).href })
  const document = await task.promise
  return {
    pageCount: document.numPages,
    async drawPage(canvas, pageNumber, width) {
      const page = await document.getPage(pageNumber)
      const natural = page.getViewport({ scale: 1 })
      const viewport = page.getViewport({ scale: (width / natural.width) * window.devicePixelRatio })
      canvas.width = viewport.width
      canvas.height = viewport.height
      const context = canvas.getContext('2d')
      if (context === null) throw new Error('no canvas context')
      await page.render({ canvasContext: context, canvas, viewport }).promise
    },
    destroy: () => task.destroy(),
  }
}
