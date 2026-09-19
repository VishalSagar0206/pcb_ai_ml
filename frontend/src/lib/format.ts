import type { Severity } from '../types/diagnosis'

export const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low', 'info']

export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: '#ff3b5c',
  high: '#ff8a3d',
  medium: '#ffd23d',
  low: '#7cd6ff',
  info: '#9aa8c7',
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
}

export function severityColor(severity: string | null | undefined): string {
  return SEVERITY_COLOR[(severity as Severity) ?? 'medium'] ?? SEVERITY_COLOR.medium
}

export function ruleTypeLabel(ruleType: string): string {
  return ruleType
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${Math.round(value * 100)}%`
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}
