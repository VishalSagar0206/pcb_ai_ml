import { describe, it, expect } from 'vitest'
import { validateBoardFile } from '../hooks/useAnalysis'

function makeFile(name: string, sizeBytes: number): File {
  // Construct a File with a controlled byte size without allocating that
  // much real memory: a Blob backed by a single repeated-content array
  // still reports `size` accurately for our validation logic, which only
  // reads `.size`, not the actual bytes.
  const content = sizeBytes > 0 ? new Uint8Array(sizeBytes) : new Uint8Array(0)
  return new File([content], name)
}

describe('validateBoardFile', () => {
  it('rejects files without a .kicad_pcb extension', () => {
    const file = makeFile('board.txt', 100)
    expect(validateBoardFile(file)).toMatch(/doesn't look like a KiCad PCB file/)
  })

  it('rejects files with no extension at all', () => {
    const file = makeFile('board', 100)
    expect(validateBoardFile(file)).toMatch(/doesn't look like a KiCad PCB file/)
  })

  it('accepts the .kicad_pcb extension case-insensitively', () => {
    const file = makeFile('BOARD.KICAD_PCB', 100)
    expect(validateBoardFile(file)).toBeNull()
  })

  it('rejects an empty file', () => {
    const file = makeFile('board.kicad_pcb', 0)
    expect(validateBoardFile(file)).toMatch(/is empty/)
  })

  it('rejects a file over the 20MB limit', () => {
    const file = makeFile('board.kicad_pcb', 21 * 1024 * 1024)
    expect(validateBoardFile(file)).toMatch(/exceeds the 20MB limit/)
  })

  it('accepts a normal-sized, correctly-named file', () => {
    const file = makeFile('board.kicad_pcb', 1024 * 50)
    expect(validateBoardFile(file)).toBeNull()
  })

  it('accepts a file right at the size boundary', () => {
    const file = makeFile('board.kicad_pcb', 20 * 1024 * 1024)
    expect(validateBoardFile(file)).toBeNull()
  })
})
