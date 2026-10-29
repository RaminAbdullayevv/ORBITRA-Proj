import type { RocketBlock } from '../lib/rocketSystem'
import { stateName } from '../lib/labels'
import './rocket-system-diagram.css'

const positions = [
  { x: 18, y: 55, sx: 215, sy: 93, ex: 335, ey: 100 },
  { x: 18, y: 174, sx: 215, sy: 212, ex: 335, ey: 190 },
  { x: 18, y: 293, sx: 215, sy: 331, ex: 335, ey: 250 },
  { x: 545, y: 55, sx: 545, sy: 93, ex: 425, ey: 151 },
  { x: 545, y: 174, sx: 545, sy: 212, ex: 425, ey: 270 },
  { x: 545, y: 293, sx: 545, sy: 331, ex: 425, ey: 320 },
]

export function RocketSystemDiagram({ blocks }: { blocks: RocketBlock[] }) {
  return <div className="rocket-diagram" aria-label="Virtual raket bort sistemlərinin etibarlı telemetriyaya əsaslanan texniki sxemi">
    <svg className="rocket-diagram-desktop" viewBox="0 0 760 420" role="img" aria-label="Altı virtual raket bloku və canlı vəziyyət əlaqələri">
      <defs><pattern id="rocket-grid" width="25" height="25" patternUnits="userSpaceOnUse"><path d="M25 0H0V25" fill="none" stroke="#2d383e" strokeWidth=".8" /></pattern></defs>
      <rect width="760" height="420" fill="url(#rocket-grid)" />
      <path d="M380 19V395M239 210H521" stroke="#415057" strokeWidth="1" strokeDasharray="4 8" />
      <path d="M380 32C352 61 339 88 335 112V315L305 350H455L425 315V112C421 88 408 61 380 32Z" fill="#242e34" stroke="#8798a0" strokeWidth="2" />
      <path d="M335 125H425M335 185H425M335 245H425M335 305H425" stroke="#54666d" strokeWidth="1" />
      <path d="M335 283L296 336L305 350M425 283L464 336L455 350" fill="none" stroke="#8798a0" strokeWidth="2" />
      <circle cx="380" cy="106" r="15" fill="#303f43" stroke="#9cb4b6" strokeWidth="1.5" />
      <path d="M363 190h34m-34 8h34m-34 8h34" stroke="#9cb4b6" strokeWidth="2" />
      <text x="380" y="389" textAnchor="middle" className="rocket-axis-label">ORBITRA · VİRTUAL BORT MODELİ</text>
      {blocks.map((block, index) => { const p = positions[index]; return <g key={block.id} className={`rocket-callout rocket-${block.status.toLowerCase()}`}>
        <path d={`M${p.sx} ${p.sy} L${p.ex} ${p.ey}`} className="rocket-connector" />
        <circle cx={p.ex} cy={p.ey} r="4" className="rocket-node" />
        <rect x={p.x} y={p.y} width="197" height="76" rx="6" className="rocket-callout-bg" />
        <rect x={p.x} y={p.y} width="3" height="76" rx="1" className="rocket-accent" />
        <text x={p.x + 14} y={p.y + 21} className="rocket-callout-name">{block.name}</text>
        <text x={p.x + 14} y={p.y + 44} className="rocket-callout-reading">{block.reading}</text>
        <text x={p.x + 14} y={p.y + 63} className="rocket-callout-status">{stateName(block.status)}</text>
      </g> })}
    </svg>
    <svg className="rocket-diagram-mobile" viewBox="0 0 240 245" role="img" aria-label="Virtual raket sistemi silueti">
      <path d="M120 12C94 37 84 56 84 86V186L61 213H179L156 186V86C156 56 146 37 120 12Z" fill="#263138" stroke="#9aadb2" strokeWidth="2" />
      <path d="M84 105H156M84 153H156M84 185H156M84 173L53 217M156 173L187 217" stroke="#748b91" strokeWidth="1.5" fill="none" />
      <circle cx="120" cy="78" r="13" fill="#35484b" stroke="#b0c5bf" />
    </svg>
    <div className="rocket-mobile-cards">{blocks.map(block => <div key={block.id} className={`rocket-mobile-card rocket-${block.status.toLowerCase()}`}>
      <strong>{block.name}</strong><span>{block.reading}</span><small>{stateName(block.status)} · {block.note}</small>
    </div>)}</div>
  </div>
}
