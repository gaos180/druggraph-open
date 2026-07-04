/**
 * NotebookSvgDefs — filtros SVG globales del tema cuaderno.
 *
 * Montar una sola vez (en App). Define los filtros "dibujado a mano" reutilizables
 * por grafos, doodles y el canvas de Cytoscape:
 *   - handdrawn-sketch / handdrawn-heavy: desplazan trazos suaves para que tiemblen.
 *   - watercolor-wash: relleno tipo acuarela con bordes irregulares.
 */
export default function NotebookSvgDefs() {
  return (
    <svg className="absolute w-0 h-0 select-none pointer-events-none" aria-hidden>
      <defs>
        <filter id="handdrawn-sketch" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="3" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="3" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="handdrawn-heavy" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="4" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="4.5" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="watercolor-wash" x="-20%" y="-20%" width="140%" height="140%">
          <feTurbulence type="fractalNoise" baseFrequency="0.015" numOctaves="4" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="12" xChannelSelector="R" yChannelSelector="G" />
          <feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.85 0" />
        </filter>
      </defs>
    </svg>
  );
}
