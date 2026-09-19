// Mirrors src/pcb_ai/schemas/pcb.py

export interface Point {
  x: number
  y: number
}

export interface BoardInfo {
  board_id: string
  title?: string | null
  revision?: string | null
  layers: string[]
  thickness_mm?: number | null
  width_mm?: number | null
  height_mm?: number | null
  origin?: Point | null
}

export interface LayerInfo {
  id: number
  name: string
  type: string
}

export interface Pad {
  component_reference: string
  pad_number: string
  pad_type?: string | null
  shape?: string | null
  position?: Point | null
  size?: { x: number; y: number } | null
  drill_mm?: number | null
  layers: string[]
  net_id?: number | null
  net_name?: string | null
  uuid?: string | null
}

export interface ComponentProperty {
  key: string
  value: string
}

export interface PCBComponent {
  reference: string
  value?: string | null
  footprint?: string | null
  library_id?: string | null
  position?: Point | null
  rotation_deg?: number | null
  side?: string | null
  properties: ComponentProperty[]
  pads: string[]
  uuid?: string | null
}

export interface Net {
  net_id: number
  net_name: string
  connected_pads: string[]
  connected_components: string[]
}

export interface Track {
  track_id: string
  layer: string
  start: Point
  end: Point
  width_mm: number
  net_id?: number | null
  net_name?: string | null
}

export interface Via {
  via_id: string
  position: Point
  diameter_mm: number
  drill_mm: number
  layers: string[]
  net_id?: number | null
  net_name?: string | null
}

export interface Zone {
  zone_id: string
  layer: string
  net_id?: number | null
  net_name?: string | null
  clearance_mm?: number | null
  polygon: Point[]
}

export interface DesignRule {
  rule_name: string
  rule_type: string
  value?: number | null
  unit?: string | null
}

export interface PCBDesign {
  schema_version: string
  board: BoardInfo
  layers: LayerInfo[]
  components: PCBComponent[]
  footprints: unknown[]
  pads: Pad[]
  nets: Net[]
  tracks: Track[]
  vias: Via[]
  zones: Zone[]
  rules: DesignRule[]
  source_file?: string | null
}
