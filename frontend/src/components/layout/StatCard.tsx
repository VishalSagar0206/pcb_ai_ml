import type { ReactNode } from 'react'
import { motion } from 'framer-motion'

interface Props {
  label: string
  value: ReactNode
  icon?: ReactNode
  accent?: string
  delay?: number
  sub?: string
}

export default function StatCard({ label, value, icon, accent = '#35e6c3', delay = 0, sub }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      className="glass-panel relative overflow-hidden rounded-xl p-4"
    >
      <div
        className="pointer-events-none absolute -right-4 -top-4 h-20 w-20 rounded-full opacity-20 blur-2xl"
        style={{ backgroundColor: accent }}
      />
      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-1.5 text-2xl font-bold text-slate-50">{value}</p>
          {sub && <p className="mt-0.5 text-[11px] text-slate-500">{sub}</p>}
        </div>
        {icon && (
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: `${accent}22`, color: accent }}
          >
            {icon}
          </div>
        )}
      </div>
    </motion.div>
  )
}
