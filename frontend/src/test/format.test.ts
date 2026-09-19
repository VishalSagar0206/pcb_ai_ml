import { describe, it, expect } from 'vitest'
import {
  SEVERITY_ORDER,
  SEVERITY_COLOR,
  SEVERITY_LABEL,
  severityColor,
  ruleTypeLabel,
  formatMs,
  formatPercent,
  clamp,
} from '../lib/format'

describe('severityColor', () => {
  it('returns the mapped color for each known severity', () => {
    for (const severity of SEVERITY_ORDER) {
      expect(severityColor(severity)).toBe(SEVERITY_COLOR[severity])
    }
  })

  it('falls back to the medium color for null/undefined/unknown input', () => {
    expect(severityColor(null)).toBe(SEVERITY_COLOR.medium)
    expect(severityColor(undefined)).toBe(SEVERITY_COLOR.medium)
    expect(severityColor('not-a-real-severity')).toBe(SEVERITY_COLOR.medium)
  })
})

describe('SEVERITY_LABEL', () => {
  it('has a human-readable label for every severity in SEVERITY_ORDER', () => {
    for (const severity of SEVERITY_ORDER) {
      expect(SEVERITY_LABEL[severity]).toBeTruthy()
    }
  })
})

describe('ruleTypeLabel', () => {
  it('converts a snake_case rule type into Title Case', () => {
    expect(ruleTypeLabel('short_circuit')).toBe('Short Circuit')
    expect(ruleTypeLabel('clearance')).toBe('Clearance')
    expect(ruleTypeLabel('annular_ring_violation')).toBe('Annular Ring Violation')
  })

  it('handles a single-word rule type', () => {
    expect(ruleTypeLabel('other')).toBe('Other')
  })
})

describe('formatMs', () => {
  it('renders sub-second durations in milliseconds', () => {
    expect(formatMs(0)).toBe('0ms')
    expect(formatMs(999)).toBe('999ms')
  })

  it('renders durations of 1s or more in seconds with one decimal', () => {
    expect(formatMs(1000)).toBe('1.0s')
    expect(formatMs(38400)).toBe('38.4s')
  })

  it('renders an em dash for null/undefined', () => {
    expect(formatMs(null)).toBe('—')
    expect(formatMs(undefined)).toBe('—')
  })
})

describe('formatPercent', () => {
  it('renders a fraction as a rounded whole-number percentage', () => {
    expect(formatPercent(0)).toBe('0%')
    expect(formatPercent(0.5)).toBe('50%')
    expect(formatPercent(0.734)).toBe('73%')
    expect(formatPercent(1)).toBe('100%')
  })

  it('renders an em dash for null/undefined', () => {
    expect(formatPercent(null)).toBe('—')
    expect(formatPercent(undefined)).toBe('—')
  })
})

describe('clamp', () => {
  it('returns the value unchanged when within bounds', () => {
    expect(clamp(5, 0, 10)).toBe(5)
  })

  it('clamps to the minimum when below range', () => {
    expect(clamp(-5, 0, 10)).toBe(0)
  })

  it('clamps to the maximum when above range', () => {
    expect(clamp(50, 0, 10)).toBe(10)
  })
})
