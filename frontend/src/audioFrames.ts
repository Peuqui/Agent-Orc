// The frames a TTS-Suite service answers with (see its docs/INTERFACE.md): the length of the
// header (uint32, big endian), the header as UTF-8 JSON, then the body of `bytes` bytes. They arrive
// in chunks of any size, so a frame may be cut anywhere.

export interface FrameHeader {
  kind: 'audio' | 'summary' | 'error'
  bytes: number
  /** Audio: who spoke it (`engine@host`). */
  engine?: string
  media_type?: string
  /** Audio: a marker that only holds the stream open; there is nothing to play. */
  keepalive?: boolean
  /** Audio: a marker for silence of this many ms between two paragraphs; there is nothing to play. */
  pause_ms?: number
}

export interface Frame {
  header: FrameHeader
  body: Uint8Array
}

const LENGTH_BYTES = 4

export class FrameReader {
  private buffer = new Uint8Array(0)

  /** The frames that the data so far completes (those that came before, with this chunk). */
  push(chunk: Uint8Array): Frame[] {
    const joined = new Uint8Array(this.buffer.length + chunk.length)
    joined.set(this.buffer)
    joined.set(chunk, this.buffer.length)
    this.buffer = joined
    const frames: Frame[] = []
    for (;;) {
      const frame = this.take()
      if (frame === null) return frames
      frames.push(frame)
    }
  }

  /** Whether a frame is cut off: the stream ended in the middle of one. */
  get incomplete(): boolean {
    return this.buffer.length > 0
  }

  private take(): Frame | null {
    if (this.buffer.length < LENGTH_BYTES) return null
    const view = new DataView(this.buffer.buffer, this.buffer.byteOffset, this.buffer.byteLength)
    const headerLength = view.getUint32(0)
    const bodyStart = LENGTH_BYTES + headerLength
    if (this.buffer.length < bodyStart) return null
    const header = JSON.parse(new TextDecoder().decode(this.buffer.subarray(LENGTH_BYTES, bodyStart))) as FrameHeader
    const end = bodyStart + header.bytes
    if (this.buffer.length < end) return null
    const body = this.buffer.slice(bodyStart, end)
    this.buffer = this.buffer.slice(end)
    return { header, body }
  }
}
