import { useMemo, useRef, useState, useCallback, useEffect, type MouseEvent } from 'react'
import type { PCBDesign } from '../../types/pcb'
import type { DRCViolation } from '../../types/diagnosis'
import { severityColor } from '../../lib/format'
import type { ViewMode } from './LayerToggle'

interface Props {
  board: PCBDesign
  violations: DRCViolation[]
  selectedViolationId: string | null
  onSelectViolation: (id: string | null) => void
  activeLayer: ViewMode
}

const MARGIN = 5

/** Interactive SVG canvas rendering the real, absolute-coordinate PCB
 * layout (footprints/pads/tracks/vias/zones) with DRC violations
 * highlighted at their true board locations. Pan via drag, zoom via wheel. */
export default function PCBCanvas({ board, violations, selectedViolationId, onSelectViolation, activeLayer }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [viewBox, setViewBox] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const dragState = useRef<{ startX: number; startY: number; vb: typeof viewBox } | null>(null)
  const [hoveredPad, setHoveredPad] = useState<string | null>(null)

  const width = board.board.width_mm ?? 60
  const height = board.board.height_mm ?? 40

  const baseViewBox = useMemo(
    () => ({ x: -MARGIN, y: -MARGIN, w: width + MARGIN * 2, h: height + MARGIN * 2 }),
    [width, height],
  )
  const vb = viewBox ?? baseViewBox

  const layerVisible = useCallback(
    (layers: string[]) => {
      if (activeLayer === 'all') return true
      return layers.some((l) => l === activeLayer)
    },
    [activeLayer],
  )

  // React's synthetic onWheel handler can't reliably preventDefault() when
  // the browser has registered its own wheel listener as passive (common
  // for touchpad pinch-zoom gestures), which left the page's native scroll/
  // zoom fighting with our custom SVG viewBox zoom. Attaching a real,
  // explicitly non-passive native listener fixes this.
  const latestState = useRef({ viewBox, baseViewBox, width, height })
  latestState.current = { viewBox, baseViewBox, width, height }

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return

    const onWheel = (e: globalThis.WheelEvent) => {
      e.preventDefault()
      const { viewBox: curViewBox, baseViewBox: curBase, width: w, height: h } = latestState.current
      const factor = e.deltaY > 0 ? 1.12 : 1 / 1.12
      const cur = curViewBox ?? curBase
      const newW = clampSize(cur.w * factor, w, h)
      const newH = newW * (cur.h / cur.w)
      const cx = cur.x + cur.w / 2
      const cy = cur.y + cur.h / 2
      setViewBox({ x: cx - newW / 2, y: cy - newH / 2, w: newW, h: newH })
    }

    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  }, [])

  const handleMouseDown = (e: MouseEvent<SVGSVGElement>) => {
    dragState.current = { startX: e.clientX, startY: e.clientY, vb: viewBox ?? baseViewBox }
  }
  const handleMouseMove = (e: MouseEvent<SVGSVGElement>) => {
    if (!dragState.current || !svgRef.current) return
    const rect = svgRef.current.getBoundingClientRect()
    const cur = dragState.current.vb ?? baseViewBox
    const scaleX = cur.w / rect.width
    const scaleY = cur.h / rect.height
    const dx = (e.clientX - dragState.current.startX) * scaleX
    const dy = (e.clientY - dragState.current.startY) * scaleY
    setViewBox({ x: cur.x - dx, y: cur.y - dy, w: cur.w, h: cur.h })
  }
  const handleMouseUp = () => {
    dragState.current = null
  }

  const resetView = () => setViewBox(null)

  const violationsByLocationKey = useMemo(() => {
    const map = new Map<string, DRCViolation[]>()
    for (const v of violations) {
      if (v.location?.x == null || v.location?.y == null) continue
      const key = `${v.location.x},${v.location.y}`
      const list = map.get(key) ?? []
      list.push(v)
      map.set(key, list)
    }
    return map
  }, [violations])

  return (
    <div className="relative h-full w-full">
      <svg
        ref={svgRef}
        viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
        className="h-full w-full cursor-grab bg-board-950 active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        role="img"
        aria-label={`PCB board layout, ${width}×${height}mm, with ${violations.length} DRC violation marker${violations.length === 1 ? '' : 's'}. Drag to pan, scroll to zoom.`}
      >
        <defs>
          <pattern id="pcb-grid" width="5" height="5" patternUnits="userSpaceOnUse">
            <path d="M 5 0 L 0 0 0 5" fill="none" stroke="rgba(53,230,195,0.08)" strokeWidth="0.08" />
          </pattern>
          <filter id="violation-glow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="1.4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="board-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0.6" stdDeviation="1.2" floodColor="#000000" floodOpacity="0.55" />
          </filter>
        </defs>

        {/* Board substrate */}
        <rect
          x={0}
          y={0}
          width={width}
          height={height}
          fill="#0a2e22"
          stroke="#2a6b4f"
          strokeWidth={0.25}
          rx={0.8}
          filter="url(#board-shadow)"
        />
        <rect x={0} y={0} width={width} height={height} fill="url(#pcb-grid)" rx={0.8} />
        <rect
          x={0}
          y={0}
          width={width}
          height={height}
          fill="none"
          stroke="rgba(53,230,195,0.25)"
          strokeWidth={0.15}
          rx={0.8}
        />

        {/* Zones (copper pours) */}
        {board.zones
          .filter((z) => layerVisible([z.layer]))
          .map((z) => (
            <polygon
              key={z.zone_id}
              points={z.polygon.map((p) => `${p.x},${p.y}`).join(' ')}
              fill={z.layer.startsWith('B.') ? 'rgba(217,114,42,0.10)' : 'rgba(79,216,255,0.10)'}
              stroke={z.layer.startsWith('B.') ? 'rgba(217,114,42,0.4)' : 'rgba(79,216,255,0.4)'}
              strokeWidth={0.1}
            />
          ))}

        {/* Tracks */}
        {board.tracks
          .filter((t) => layerVisible([t.layer]))
          .map((t) => (
            <line
              key={t.track_id}
              x1={t.start.x}
              y1={t.start.y}
              x2={t.end.x}
              y2={t.end.y}
              stroke={t.layer.startsWith('B.') ? '#d9722a' : '#4fd8ff'}
              strokeWidth={Math.max(t.width_mm, 0.08)}
              strokeLinecap="round"
              opacity={0.9}
            />
          ))}

        {/* Vias */}
        {activeLayer !== 'Edge.Cuts' &&
          board.vias.map((v) => (
            <circle
              key={v.via_id}
              cx={v.position.x}
              cy={v.position.y}
              r={v.diameter_mm / 2}
              fill="#1a2540"
              stroke="#94a9d1"
            strokeWidth={0.08}
          />
        ))}

        {/* Footprint courtyards + reference labels */}
        {activeLayer !== 'Edge.Cuts' &&
          board.components.map((c) => {
            if (!c.position) return null
            const isTop = (c.side ?? 'top') === 'top'
            if (activeLayer === 'F.Cu' && !isTop) return null
            if (activeLayer === 'B.Cu' && isTop) return null
            const size = estimateComponentSize(c)
            return (
              <g key={c.reference} opacity={0.95}>
                <rect
                  x={c.position.x - size / 2}
                  y={c.position.y - size / 2}
                  width={size}
                  height={size}
                  fill="rgba(38,52,84,0.55)"
                  stroke={isTop ? '#4fd8ff' : '#d9722a'}
                  strokeWidth={0.06}
                  rx={0.2}
                />
                <text
                  x={c.position.x}
                  y={c.position.y - size / 2 - 0.3}
                  fontSize={1.1}
                  fill="#cbd5e8"
                  textAnchor="middle"
                  fontFamily="var(--font-mono)"
                >
                  {c.reference}
                </text>
              </g>
            )
          })}

        {/* Pads */}
        {activeLayer !== 'Edge.Cuts' &&
          board.pads
            .filter((p) => layerVisible(p.layers))
            .map((p) => {
            const key = `${p.component_reference}:${p.pad_number}`
            const isHovered = hoveredPad === key
            return (
              <rect
                key={key}
                x={(p.position?.x ?? 0) - (p.size?.x ?? 0.5) / 2}
                y={(p.position?.y ?? 0) - (p.size?.y ?? 0.5) / 2}
                width={p.size?.x ?? 0.5}
                height={p.size?.y ?? 0.5}
                rx={p.shape === 'circle' ? (p.size?.x ?? 0.5) / 2 : 0.08}
                fill={isHovered ? '#ffd23d' : p.pad_type === 'thru_hole' ? '#ffb27a' : '#f3924a'}
                stroke="#0a0f1e"
                strokeWidth={0.04}
                onMouseEnter={() => setHoveredPad(key)}
                onMouseLeave={() => setHoveredPad(null)}
              >
                <title>
                  {p.component_reference} pad {p.pad_number}
                  {p.net_name ? ` — net ${p.net_name}` : ''}
                </title>
              </rect>
            )
          })}

        {/* DRC violation markers, positioned at real board coordinates */}
        {[...violationsByLocationKey.entries()].map(([key, vs]) => {
          const [x, y] = key.split(',').map(Number)
          const isSelected = vs.some((v) => v.violation_id === selectedViolationId)
          const color = severityColor(vs[0].severity)
          return (
            <g
              key={key}
              className="cursor-pointer"
              onClick={() => onSelectViolation(vs[0].violation_id === selectedViolationId ? null : vs[0].violation_id)}
            >
              <circle
                cx={x}
                cy={y}
                r={isSelected ? 1.6 : 1.1}
                fill="none"
                stroke={color}
                strokeWidth={isSelected ? 0.35 : 0.22}
                filter="url(#violation-glow)"
                className={isSelected ? '' : 'animate-pulse'}
              />
              <circle cx={x} cy={y} r={0.35} fill={color} filter="url(#violation-glow)" />
              <title>
                {vs.map((v) => `[${v.severity.toUpperCase()}] ${v.rule_type}: ${v.message}`).join('\n')}
              </title>
            </g>
          )
        })}
      </svg>

      <div className="absolute bottom-3 left-3 hidden rounded-lg border border-board-600 bg-board-900/80 px-3 py-2 text-[10px] text-slate-400 backdrop-blur-sm sm:block">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <LegendItem colorClass="bg-cyan-glow" label="Top copper / component" />
          <LegendItem colorClass="bg-copper-500" label="Bottom copper / pad" />
          <LegendItem colorClass="bg-board-500" label="Via" shape="circle" />
          <LegendItem colorClass="bg-severity-high" label="DRC violation" shape="ring" />
        </div>
      </div>

      <div className="absolute bottom-3 right-3 flex gap-2">
        <button
          onClick={resetView}
          className="glass-panel rounded-md px-3 py-1.5 text-xs text-slate-200 hover:border-teal-glow/60"
        >
          Reset view
        </button>
      </div>
    </div>
  )
}

function LegendItem({
  colorClass,
  label,
  shape = 'square',
}: {
  colorClass: string
  label: string
  shape?: 'square' | 'circle' | 'ring'
}) {
  return (
    <span className="flex items-center gap-1.5">
      {shape === 'ring' ? (
        <span className="h-2.5 w-2.5 rounded-full border-2 border-severity-high" />
      ) : shape === 'circle' ? (
        <span className={`h-2 w-2 rounded-full ${colorClass}`} />
      ) : (
        <span className={`h-2 w-2 rounded-sm ${colorClass}`} />
      )}
      {label}
    </span>
  )
}

function clampSize(v: number, boardWidth: number, boardHeight: number): number {
  const maxDim = Math.max(boardWidth, boardHeight) * 6
  const minDim = Math.max(boardWidth, boardHeight) * 0.05
  return Math.min(maxDim, Math.max(minDim, v))
}

function estimateComponentSize(c: { reference: string }): number {
  // Best-effort visual sizing heuristic (no footprint bounding-box data
  // available from the parser yet): ICs/connectors get a larger box.
  const ref = c.reference.toUpperCase()
  if (ref.startsWith('U') || ref.startsWith('J') || ref.startsWith('SW')) return 5
  if (ref.startsWith('R') || ref.startsWith('C') || ref.startsWith('L') || ref.startsWith('D')) return 2
  return 3
}
