import React from "react";

/**
 * ChemicalDoodle — adorno molecular SVG (anillo hexagonal + sustituyentes) con trazo
 * "dibujado a mano". Decorativo, para dar el toque de cuaderno de química a las fichas
 * de fármaco. La estructura real desde SMILES la calcula RDKit en el backend.
 */
export default function ChemicalDoodle({ size = 72, seed = 0 }: { size?: number; seed?: number }) {
  // Pequeña variación determinista por 'seed' para que no todas se vean idénticas.
  const rot = (seed % 6) * 12;
  return (
    <svg width={size} height={size} viewBox="0 0 60 60" className="shrink-0" filter="url(#handdrawn-sketch)">
      <g transform={`translate(30 30) rotate(${rot}) translate(-30 -30)`} stroke="#2b251d" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round">
        {/* Anillo bencénico */}
        <polygon points="30,12 44,20 44,36 30,44 16,36 16,20" />
        {/* Dobles enlaces interiores */}
        <line x1="32" y1="16" x2="41" y2="21" opacity="0.7" />
        <line x1="41" y1="23" x2="41" y2="33" opacity="0.7" />
        <line x1="19" y1="23" x2="19" y2="33" opacity="0.7" />
        {/* Sustituyentes */}
        <line x1="30" y1="12" x2="30" y2="3" />
        <circle cx="30" cy="3" r="2.5" fill="#a7f3d0" opacity="0.8" />
        <line x1="44" y1="36" x2="52" y2="41" />
        <circle cx="52" cy="41" r="2.5" fill="#93c5fd" opacity="0.8" />
        <line x1="16" y1="36" x2="8" y2="41" />
      </g>
    </svg>
  );
}
