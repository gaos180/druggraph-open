import React, { useMemo } from 'react';
import { ProcessedGene } from '../../../api/tools';

interface Props {
  genes:         ProcessedGene[];
  fcThreshold:   number;
  pvalThreshold: number;
  useFdr:        boolean;
  width?:        number;
  height?:       number;
}

const PAD = { top: 28, right: 24, bottom: 44, left: 52 };

function clamp(v: number, mn: number, mx: number) { return Math.max(mn, Math.min(mx, v)); }

export default function VolcanoPlot({
  genes, fcThreshold, pvalThreshold, useFdr,
  width = 560, height = 420,
}: Props) {
  const W = width  - PAD.left - PAD.right;
  const H = height - PAD.top  - PAD.bottom;

  const { points, xMin, xMax, yMax } = useMemo(() => {
    const withY = genes
      .filter(g => g.pvalue > 0)
      .map(g => ({
        ...g,
        negLogP: -Math.log10(useFdr ? (g.padj || g.pvalue) : g.pvalue),
      }));

    const fcVals = withY.map(g => g.log2fc);
    const xMin   = Math.min(-4, ...fcVals) - 0.5;
    const xMax   = Math.max( 4, ...fcVals) + 0.5;
    const yMax   = Math.max(5, ...withY.map(g => g.negLogP)) + 0.5;

    return { points: withY, xMin, xMax, yMax };
  }, [genes, useFdr]);

  const toX = (fc: number) => ((fc - xMin) / (xMax - xMin)) * W;
  const toY = (y: number)  => H - (y / yMax) * H;

  const threshY = -Math.log10(pvalThreshold);

  const color = (g: typeof points[0]) => {
    if (g.is_target && g.is_sig) return '#f59e0b';   // amarillo — DEG target
    if (g.is_target)              return '#fcd34d55'; // amarillo tenue — target no sig
    if (!g.is_sig)                return '#e7dfd0';   // gris — no significativo
    if (g.direction === 'up')     return '#f87171';   // rojo — up
    if (g.direction === 'down')   return '#60a5fa';   // azul — down
    return '#78716c';
  };

  const radius = (g: typeof points[0]) => g.is_target ? 5 : 3;

  // Eje X ticks
  const xTicks: number[] = [];
  for (let v = Math.ceil(xMin); v <= Math.floor(xMax); v++) {
    if (v % 2 === 0) xTicks.push(v);
  }

  // Eje Y ticks
  const yTicks: number[] = [];
  for (let v = 0; v <= Math.floor(yMax); v += 2) yTicks.push(v);

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <svg width={width} height={height} style={{ background: '#060d1b', borderRadius: '8px' }}>
        <g transform={`translate(${PAD.left},${PAD.top})`}>

          {/* Líneas de umbral */}
          <line x1={toX(-fcThreshold)} x2={toX(-fcThreshold)} y1={0} y2={H}
            stroke="#d6ccbb" strokeWidth={1} strokeDasharray="4,3" />
          <line x1={toX(fcThreshold)}  x2={toX(fcThreshold)}  y1={0} y2={H}
            stroke="#d6ccbb" strokeWidth={1} strokeDasharray="4,3" />
          <line x1={0} x2={W} y1={toY(threshY)} y2={toY(threshY)}
            stroke="#d6ccbb" strokeWidth={1} strokeDasharray="4,3" />

          {/* Puntos — primero los no-target/no-sig (fondo) */}
          {points
            .filter(g => !g.is_target && !g.is_sig)
            .map((g, i) => (
              <circle key={`bg-${i}`}
                cx={clamp(toX(g.log2fc), 0, W)}
                cy={clamp(toY(g.negLogP), 0, H)}
                r={2} fill={color(g)} opacity={0.5} />
            ))}

          {/* Puntos significativos */}
          {points
            .filter(g => g.is_sig && !g.is_target)
            .map((g, i) => (
              <circle key={`sig-${i}`}
                cx={clamp(toX(g.log2fc), 0, W)}
                cy={clamp(toY(g.negLogP), 0, H)}
                r={3} fill={color(g)} opacity={0.8}>
                <title>{g.symbol} | FC={g.log2fc.toFixed(2)} | p={g.pvalue.toExponential(2)}</title>
              </circle>
            ))}

          {/* Targets (encima de todo) */}
          {points
            .filter(g => g.is_target)
            .map((g, i) => (
              <g key={`tgt-${i}`}>
                <circle
                  cx={clamp(toX(g.log2fc), 0, W)}
                  cy={clamp(toY(g.negLogP), 0, H)}
                  r={radius(g)} fill={color(g)} stroke="#92400e" strokeWidth={1}>
                  <title>{g.symbol} | FC={g.log2fc.toFixed(2)} | p={g.pvalue.toExponential(2)} | {g.rel_type}</title>
                </circle>
                {g.is_sig && (
                  <text
                    x={clamp(toX(g.log2fc) + 6, 0, W - 30)}
                    y={clamp(toY(g.negLogP) - 3, 8, H)}
                    fontSize={9} fill="#fde68a" fontFamily="monospace">
                    {g.symbol}
                  </text>
                )}
              </g>
            ))}

          {/* Eje X */}
          <line x1={0} x2={W} y1={H} y2={H} stroke="#d6ccbb" strokeWidth={1} />
          {xTicks.map(v => (
            <g key={`xt-${v}`}>
              <line x1={toX(v)} x2={toX(v)} y1={H} y2={H + 4} stroke="#a8a29e" strokeWidth={1} />
              <text x={toX(v)} y={H + 16} textAnchor="middle" fontSize={10} fill="#78716c">{v}</text>
            </g>
          ))}
          <text x={W / 2} y={H + 34} textAnchor="middle" fontSize={11} fill="#78716c">
            log₂(Fold Change)
          </text>

          {/* Eje Y */}
          <line x1={0} x2={0} y1={0} y2={H} stroke="#d6ccbb" strokeWidth={1} />
          {yTicks.map(v => (
            <g key={`yt-${v}`}>
              <line x1={-4} x2={0} y1={toY(v)} y2={toY(v)} stroke="#a8a29e" strokeWidth={1} />
              <text x={-8} y={toY(v) + 4} textAnchor="end" fontSize={10} fill="#78716c">{v}</text>
            </g>
          ))}
          <text transform={`translate(-38,${H / 2}) rotate(-90)`}
            textAnchor="middle" fontSize={11} fill="#78716c">
            -{useFdr ? 'log₁₀(FDR)' : 'log₁₀(p-valor)'}
          </text>

        </g>

        {/* Leyenda */}
        {[
          { color: '#f87171',  label: 'DEG Up',   r: 3 },
          { color: '#60a5fa',  label: 'DEG Down',  r: 3 },
          { color: '#f59e0b',  label: 'Target DEG', r: 5 },
          { color: '#e7dfd0',  label: 'No sig.',    r: 3 },
        ].map((l, i) => (
          <g key={l.label} transform={`translate(${PAD.left + 8 + i * 92},${height - 10})`}>
            <circle r={l.r} fill={l.color} stroke={l.color === '#f59e0b' ? '#92400e' : 'none'}
              strokeWidth={1} cy={-3} />
            <text x={l.r + 5} fontSize={9} fill="#78716c" dominantBaseline="middle" y={-3}>
              {l.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
