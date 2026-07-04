import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Map as MapIcon, Crosshair } from 'lucide-react';
import { toolsApi, ChemicalSpaceResult, ChemicalSpacePoint, ChemicalSpaceLocateResult } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';

// Paleta cualitativa estable; el cluster -1 (ruido) va en gris.
const PALETTE = ['#2563eb', '#dc2626', '#16a34a', '#9333ea', '#ea580c', '#0891b2', '#db2777', '#65a30d', '#ca8a04', '#4f46e5', '#0d9488', '#be123c'];
const clusterColor = (c: number) => (c < 0 ? '#a8a29e' : PALETTE[c % PALETTE.length]);

const W = 720, H = 520, PAD = 30;

export default function ChemicalSpaceMap() {
  usePageTitle('Mapa de espacio químico');
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<ChemicalSpaceResult | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number; p: ChemicalSpacePoint } | null>(null);

  const [smiles, setSmiles] = useState('');
  const [located, setLocated] = useState<ChemicalSpaceLocateResult | null>(null);
  const [locLoading, setLocLoading] = useState(false);
  const [locError, setLocError] = useState('');

  const load = async () => {
    setLoading(true); setError(''); setData(null); setLocated(null);
    try { const res = await toolsApi.chemicalSpace(); setData(res.data); }
    catch (err: any) { setError(err?.response?.data?.error || err?.message || 'Error al cargar el mapa'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  // Escala de coordenadas del mundo (x,y de UMAP) a píxeles del canvas.
  const scale = useMemo(() => {
    const pts = data?.points || [];
    if (!pts.length) return null;
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const sx = (maxX - minX) || 1, sy = (maxY - minY) || 1;
    return {
      toPx: (x: number, y: number): [number, number] => [
        PAD + ((x - minX) / sx) * (W - 2 * PAD),
        H - PAD - ((y - minY) / sy) * (H - 2 * PAD),
      ],
    };
  }, [data]);

  const draw = () => {
    const canvas = canvasRef.current;
    if (!canvas || !data || !scale) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#faf6ee';
    ctx.fillRect(0, 0, W, H);

    for (const p of data.points) {
      const [px, py] = scale.toPx(p.x, p.y);
      ctx.beginPath();
      ctx.arc(px, py, 3, 0, Math.PI * 2);
      ctx.fillStyle = clusterColor(p.cluster);
      ctx.globalAlpha = 0.75;
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Molécula localizada como estrella destacada.
    if (located?.available) {
      const [px, py] = scale.toPx(located.x, located.y);
      ctx.beginPath();
      ctx.arc(px, py, 8, 0, Math.PI * 2);
      ctx.fillStyle = '#111827';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(px, py, 8, 0, Math.PI * 2);
      ctx.lineWidth = 3;
      ctx.strokeStyle = '#fde047';
      ctx.stroke();
    }
  };

  useEffect(() => { draw(); }, [data, scale, located]);

  const onMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!data || !scale) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = ((e.clientX - rect.left) / rect.width) * W;
    const my = ((e.clientY - rect.top) / rect.height) * H;
    let best: ChemicalSpacePoint | null = null, bestD = 64; // radio² de captura
    for (const p of data.points) {
      const [px, py] = scale.toPx(p.x, p.y);
      const d = (px - mx) ** 2 + (py - my) ** 2;
      if (d < bestD) { bestD = d; best = p; }
    }
    setHover(best ? { x: e.clientX - rect.left, y: e.clientY - rect.top, p: best } : null);
  };

  const locate = async () => {
    const s = smiles.trim();
    if (!s) { setLocError('Ingresa un SMILES'); return; }
    setLocLoading(true); setLocError(''); setLocated(null);
    try { const res = await toolsApi.locateInSpace(s); setLocated(res.data); }
    catch (err: any) { setLocError(err?.response?.data?.error || 'No se pudo ubicar la molécula'); }
    finally { setLocLoading(false); }
  };

  return (
    <div className="max-w-5xl">
      <HandTitle className="text-2xl flex items-center gap-2"><MapIcon className="w-6 h-6 text-amber-800" /> Mapa de Espacio Químico</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">
        Proyección UMAP (2D) de los embeddings ChemBERTa del catálogo, coloreada por cluster (HDBSCAN). Cada punto es un fármaco; moléculas cercanas son químicamente parecidas.
      </p>

      {loading && <div className={cardCls}>Cargando mapa…</div>}
      {error && <div className={`${cardCls} text-red-600 text-[13px]`}>{error}</div>}

      {data && (
        <>
          <div className={`${cardCls} flex gap-3 items-end flex-wrap`}>
            <div className="flex-1 min-w-[240px]">
              <label className="text-[11px] text-stone-500 block mb-1 font-mono">UBICAR UNA MOLÉCULA (SMILES)</label>
              <input className={`${inpCls} w-full`} value={smiles} onChange={e => setSmiles(e.target.value)}
                placeholder="CC(=O)Oc1ccccc1C(=O)O" onKeyDown={e => e.key === 'Enter' && locate()} />
            </div>
            <PencilButton variant="solid" onClick={locate} disabled={locLoading}
              icon={<Crosshair className="w-4 h-4" />}>{locLoading ? 'Ubicando…' : 'Ubicar'}</PencilButton>
            {locError && <span className="text-red-600 text-[13px]">{locError}</span>}
          </div>

          <div className={`${cardCls} relative`}>
            <div className="text-stone-500 text-[11px] font-mono mb-2">
              {data.points.length} fármacos · {data.clusters.filter(c => !c.is_outlier).length} clusters
            </div>
            <canvas ref={canvasRef} width={W} height={H}
              className="w-full h-auto border border-stone-800/10 rounded-lg cursor-crosshair"
              onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
            {hover && (
              <div className="absolute pointer-events-none bg-[#2d2621] text-[#faf6ee] text-[11px] font-mono px-2 py-1 rounded shadow-lg z-10"
                style={{ left: Math.min(hover.x + 12, W - 140), top: hover.y + 12 }}>
                <div className="font-bold">{hover.p.name || hover.p.drugbank_id}</div>
                <div className="opacity-70">{hover.p.drugbank_id} · cluster {hover.p.cluster < 0 ? '—' : hover.p.cluster}</div>
              </div>
            )}
          </div>

          {located?.available && (
            <div className={cardCls}>
              <div className="text-stone-800 font-bold font-hand mb-2">
                Molécula ubicada · cluster {located.cluster < 0 ? 'atípico (outlier)' : located.cluster}
              </div>
              <div className="text-stone-500 text-[11px] font-mono mb-1">VECINOS MÁS CERCANOS (coseno ChemBERTa)</div>
              <div className="flex flex-wrap gap-1.5">
                {located.neighbors.map(n => (
                  <span key={n.drugbank_id} className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full text-[11px] font-mono">
                    {n.name || n.drugbank_id} ({n.score.toFixed(3)})
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className={cardCls}>
            <div className="text-stone-500 text-[11px] font-mono mb-2">CLUSTERS</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {data.clusters.map(c => (
                <div key={c.cluster} className="flex items-center gap-2 text-[12px] font-hand">
                  <span className="w-3 h-3 rounded-full shrink-0" style={{ background: clusterColor(c.cluster) }} />
                  <span className="text-stone-800 font-semibold">
                    {c.is_outlier ? 'Atípicos' : `Cluster ${c.cluster}`} ({c.size})
                  </span>
                  <span className="text-stone-500 truncate">{c.top_types.join(', ')} · {c.examples.slice(0, 2).join(', ')}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
