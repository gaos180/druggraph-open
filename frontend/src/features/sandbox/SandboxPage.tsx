import React, { useState, useRef, useEffect, useMemo } from 'react';

import {
  sandboxApi,
  SandboxAnalysisResponse,
  SandboxPathwaysResponse,
  TargetSearchResult,
  PropagationResponse,
} from '../../api/sandbox';
import { NotebookLayout, NotebookNavbar } from '../../components/notebook';
import CytoscapeGraph, { CyNode, CyEdge } from '../../components/CytoscapeGraph';
import '../../styles/drugs.css';
import { usePageTitle } from '../../hooks/usePageTitle';
import { downloadCsv, downloadJson } from '../../utils/download';
import * as exp from './sandboxExports';
import { buildEffectGraph, buildPathwayGraph } from './sandboxGraphs';
import { exportBtnStyle } from './components/styles';
import { PropertyBadge, TargetChip, CombinedResultCard } from './components/SimilarityCards';
import SwissTargetPanel from './components/SwissTargetPanel';
import { FunctionalTable, KeggTable, PpiTable } from './components/PathwayTables';
import CtdSection from './components/CtdSection';
import GraphLegend from './components/GraphLegend';
import ReportPanel from '../reports/ReportPanel';
import BioactivitySection from '../drugs/drug-sections/BioactivitySection';
import EmbeddingSimilarityPanel from './components/EmbeddingSimilarityPanel';

const EXAMPLE_COMPOUNDS = [
  { label: 'Aspirina',    smiles: 'CC(=O)Oc1ccccc1C(=O)O' },
  { label: 'Cafeína',     smiles: 'CN1C=NC2=C1C(=O)N(C(=O)N2C)C' },
  { label: 'Ibuprofeno',  smiles: 'CC(C)Cc1ccc(cc1)C(C)C(=O)O' },
  { label: 'Paracetamol', smiles: 'CC(=O)Nc1ccc(O)cc1' },
];

// ── Componente principal ───────────────────────────────────────────────────────

export default function SandboxPage() {
  usePageTitle('Laboratorio Virtual');
  const [smiles, setSmiles]         = useState('');
  const [name, setName]             = useState('');
  const [targetQuery, setTargetQuery]         = useState('');
  const [targetOptions, setTargetOptions]     = useState<TargetSearchResult[]>([]);
  const [selectedTargets, setSelectedTargets] = useState<TargetSearchResult[]>([]);
  const [searchingTargets, setSearchingTargets] = useState(false);
  const [showSwiss, setShowSwiss]   = useState(false);

  const [result, setResult]   = useState<SandboxAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const [pathwayData, setPathwayData]       = useState<SandboxPathwaysResponse | null>(null);
  const [loadingPathways, setLoadingPathways] = useState(false);
  const [pathwayError, setPathwayError]     = useState('');
  const [graphView, setGraphView]           = useState<'effect' | 'pathway'>('effect');

  const [propData, setPropData]       = useState<PropagationResponse | null>(null);
  const [loadingProp, setLoadingProp] = useState(false);
  const [propError, setPropError]     = useState('');
  const [propMode, setPropMode]       = useState<'directed' | 'diffusion'>('directed');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Autocompletado de targets ─────────────────────────────────────────────
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (targetQuery.trim().length < 2) { setTargetOptions([]); return; }
    debounceRef.current = setTimeout(() => {
      setSearchingTargets(true);
      sandboxApi
        .searchTargets(targetQuery.trim())
        .then((res) => setTargetOptions(res.data.results))
        .catch(() => setTargetOptions([]))
        .finally(() => setSearchingTargets(false));
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [targetQuery]);

  const addTarget = (t: TargetSearchResult) => {
    if (selectedTargets.find((s) => s.drugbank_target_id === t.drugbank_target_id)) return;
    if (selectedTargets.length >= 30) return;
    setSelectedTargets([...selectedTargets, t]);
    setTargetQuery('');
    setTargetOptions([]);
  };

  const removeTarget = (id: string) =>
    setSelectedTargets(selectedTargets.filter((t) => t.drugbank_target_id !== id));

  // ── Importar desde SwissTargetPrediction ─────────────────────────────────
  const handleSwissImport = (targets: TargetSearchResult[]) => {
    const toAdd = targets.filter(
      (t) => !selectedTargets.find((s) => s.drugbank_target_id === t.drugbank_target_id),
    );
    setSelectedTargets((prev) => [...prev, ...toAdd].slice(0, 30));
    setShowSwiss(false);
  };

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleAnalyze = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = smiles.trim();
    if (!trimmed) { setError('Ingresa una cadena SMILES.'); return; }
    setLoading(true); setError(''); setResult(null);
    sandboxApi
      .analyze({
        smiles: trimmed,
        name: name.trim() || undefined,
        target_ids: selectedTargets.map((t) => t.drugbank_target_id),
      })
      .then((res) => setResult(res.data))
      .catch((err) => setError(err?.response?.data?.error || 'Error analizando el compuesto.'))
      .finally(() => setLoading(false));
  };

  const handleExample = (ex: (typeof EXAMPLE_COMPOUNDS)[number]) => {
    setSmiles(ex.smiles);
    setName(ex.label);
  };

  const exportResultsCsv  = () => exp.exportResultsCsv(result);
  const exportResultsJson = () => exp.exportResultsJson(result);
  const openHtmlReport    = () => exp.openSandboxReport(result, pathwayData);

  const loadPathways = () => {
    if (!result) return;
    setLoadingPathways(true);
    setPathwayError('');
    const target_ids = result.sandbox.linked_targets;
    const drug_ids   = result.combined.slice(0, 8).map(r => r.drugbank_id);
    sandboxApi.getPathways({ target_ids, drug_ids })
      .then(res => setPathwayData(res.data))
      .catch(e => setPathwayError(e?.response?.data?.error || 'Error cargando rutas.'))
      .finally(() => setLoadingPathways(false));
  };

  const exportGoProcessCsv  = () => exp.exportGoProcessCsv(pathwayData);
  const exportKeggCsv       = () => exp.exportKeggCsv(pathwayData);
  const exportPpiCsv        = () => exp.exportPpiCsv(pathwayData);
  const exportPathwaysJson  = () => exp.exportPathwaysJson(pathwayData);
  const exportCtdSummaryCsv = () => exp.exportCtdSummaryCsv(pathwayData);
  const exportCtdGenesCsv   = () => exp.exportCtdGenesCsv(pathwayData);
  const exportCtdJson       = () => exp.exportCtdJson(pathwayData);

  const loadPropagation = (mode: 'directed' | 'diffusion') => {
    setPropMode(mode);
    const genes = (pathwayData?.targets_used ?? [])
      .map(t => t.gene_name).filter(Boolean);
    const seedBody = genes.length > 0
      ? { genes }
      : { target_ids: result?.sandbox.linked_targets ?? [],
          drug_ids: (result?.combined ?? []).slice(0, 8).map(r => r.drugbank_id) };
    const body = mode === 'directed'
      ? { ...seedBody, mode, seed_sign: -1, max_hops: 3, top_n: 40 }
      : { ...seedBody, mode, top_n: 40 };
    setLoadingProp(true); setPropError(''); setPropData(null);
    sandboxApi.getPropagation(body)
      .then(res => setPropData(res.data))
      .catch(e => setPropError(e?.response?.data?.error || 'Error en la propagación (¿red cargada?).'))
      .finally(() => setLoadingProp(false));
  };
  const exportPropCsv = () => exp.exportPropCsv(propData);

  // ── Grafos de red (memoizados para no relanzar el layout en cada render) ──
  const effectGraph = useMemo(
    () => pathwayData ? buildEffectGraph(result?.sandbox.name || 'Compuesto', pathwayData) : { nodes: [], edges: [] },
    [pathwayData, result?.sandbox.name],
  );
  const pathwayGraph = useMemo(
    () => pathwayData ? buildPathwayGraph(pathwayData) : { nodes: [], edges: [] },
    [pathwayData],
  );

  // Grafo de la cascada dirigida (nodos por estado, aristas con signo)
  const cascadeGraph = useMemo(() => {
    if (!propData || propData.mode !== 'directed' || !propData.edges) return { nodes: [] as CyNode[], edges: [] as CyEdge[] };
    const seedSet = new Set(propData.seeds_used);
    const effBy: Record<string, typeof propData.downstream[number]> = {};
    propData.downstream.forEach(d => { effBy[d.gene] = d; });
    const names = new Set<string>([...propData.seeds_used, ...propData.downstream.map(d => d.gene)]);
    const nodes: CyNode[] = Array.from(names).map(g => {
      if (seedSet.has(g)) return { id: g, label: g, kind: 'seed', weight: 4 };
      const d = effBy[g];
      return {
        id: g, label: g,
        kind: d && (d.sign ?? 0) > 0 ? 'activated' : 'inhibited',
        weight: 1 + Math.min(4, d ? (d.magnitude ?? 4) / 4 : 1),
      };
    });
    const edges: CyEdge[] = propData.edges
      .filter(e => names.has(e.source) && names.has(e.target))
      .map((e, i) => ({ id: `${e.source}-${e.target}-${i}`, source: e.source, target: e.target, sign: e.sign }));
    return { nodes, edges };
  }, [propData]);

  // Contexto resumido: qué afecta y qué posiblemente afecta
  const networkSummary = useMemo(() => {
    if (!pathwayData) return null;
    const directCount   = pathwayData.string_ppi?.direct_genes?.length
      ?? pathwayData.targets_used.filter(t => t.gene_name || t.uniprot_id).length;
    const indirectCount = pathwayData.string_ppi?.neighbors?.length ?? 0;
    const keggCount     = pathwayData.kegg?.pathway_count ?? pathwayData.kegg?.pathways.length ?? 0;
    const topProcess    = pathwayData.go_process[0]?.description ?? null;
    const ctdInteractions = pathwayData.ctd?.summary?.total_interactions ?? 0;
    return { directCount, indirectCount, keggCount, topProcess, ctdInteractions };
  }, [pathwayData]);

  const methodLabels: Record<string, { label: string; color: string }> = {
    gds:              { label: 'GDS Node Similarity', color: '#a855f7' },
    jaccard:          { label: 'Jaccard (proteínas compartidas)', color: '#7dd3fc' },
    jaccard_inferred: { label: 'Jaccard (proteínas inferidas de similitud estructural)', color: '#7dd3fc' },
    structural_only:  { label: 'Solo similitud estructural', color: '#38bdf8' },
    none:             { label: 'Sin coincidencias', color: '#78716c' },
  };

  return (
    <NotebookLayout navbar={<NotebookNavbar />}>
    <div className="drugs-root" style={{ margin: '0 auto', padding: '4px' }}>
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ margin: 0, color: '#1c1917' }}>🧫 Laboratorio Virtual</h2>
        <p style={{ color: '#78716c', fontSize: '0.9rem', margin: '6px 0 0 0' }}>
          Ingresa un compuesto y compáralo contra la red de fármacos por similitud
          estructural y de comportamiento (targets). No se modifica la base de datos.
        </p>
      </div>

      {/* FORMULARIO */}
      <form onSubmit={handleAnalyze} style={{
        background: '#d6ccbb', border: '1px solid #bcae98', borderRadius: '12px',
        padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px',
      }}>
        {/* SMILES */}
        <div>
          <label style={{ display: 'block', color: '#57534e', fontSize: '0.85rem', marginBottom: '6px', fontWeight: 600 }}>
            Estructura SMILES *
          </label>
          <input
            value={smiles}
            onChange={(e) => setSmiles(e.target.value)}
            placeholder="ej. CC(=O)Oc1ccccc1C(=O)O"
            style={{
              width: '100%', background: '#f3ece0', border: '1px solid #bcae98',
              color: '#1c1917', padding: '10px 14px', borderRadius: '8px',
              fontSize: '0.9rem', fontFamily: 'monospace', outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
            <span style={{ color: '#57534e', fontSize: '0.75rem', alignSelf: 'center' }}>Ejemplos:</span>
            {EXAMPLE_COMPOUNDS.map((ex) => (
              <button
                key={ex.label}
                type="button"
                onClick={() => handleExample(ex)}
                style={{
                  background: '#f3ece0', border: '1px solid #bcae98', color: '#0369a1',
                  padding: '4px 10px', borderRadius: '6px', fontSize: '0.75rem', cursor: 'pointer',
                }}
              >{ex.label}</button>
            ))}
          </div>
        </div>

        {/* Nombre */}
        <div>
          <label style={{ display: 'block', color: '#57534e', fontSize: '0.85rem', marginBottom: '6px', fontWeight: 600 }}>
            Nombre del compuesto (opcional)
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ej. Mi compuesto experimental"
            style={{
              width: '100%', background: '#f3ece0', border: '1px solid #bcae98',
              color: '#1c1917', padding: '10px 14px', borderRadius: '8px',
              fontSize: '0.9rem', outline: 'none', boxSizing: 'border-box',
            }}
          />
        </div>

        {/* Targets candidatos */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label style={{ color: '#57534e', fontSize: '0.85rem', fontWeight: 600 }}>
              Targets candidatos (opcional)
            </label>
            <button
              type="button"
              onClick={() => setShowSwiss((v) => !v)}
              style={{
                background: showSwiss ? '#1e4a5f' : '#f3ece0',
                border: '1px solid #bcae98', color: showSwiss ? '#7dd3fc' : '#0284c7',
                padding: '5px 12px', borderRadius: '6px', fontSize: '0.75rem',
                fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px',
              }}
            >
              <span>🔮</span>
              <span>SwissTargetPrediction</span>
              <span style={{ color: '#57534e' }}>{showSwiss ? '▲' : '▼'}</span>
            </button>
          </div>

          <p style={{ color: '#57534e', fontSize: '0.78rem', margin: '0 0 8px 0' }}>
            Busca manualmente proteínas candidatas, o usa SwissTargetPrediction para
            importarlas automáticamente con sus probabilidades.
          </p>

          {/* Panel SwissTargetPrediction */}
          {showSwiss && (
            <div style={{ marginBottom: '10px' }}>
              <SwissTargetPanel
                smiles={smiles}
                onImport={handleSwissImport}
              />
            </div>
          )}

          {/* Chips de targets seleccionados */}
          {selectedTargets.length > 0 && (
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
              {selectedTargets.map((t) => (
                <TargetChip key={t.drugbank_target_id} target={t} onRemove={() => removeTarget(t.drugbank_target_id)} />
              ))}
            </div>
          )}

          {/* Autocompletado manual */}
          <div style={{ position: 'relative' }}>
            <input
              value={targetQuery}
              onChange={(e) => setTargetQuery(e.target.value)}
              placeholder="Buscar proteína, gen o UniProt ID (mín. 2 caracteres)…"
              style={{
                width: '100%', background: '#f3ece0', border: '1px solid #bcae98',
                color: '#1c1917', padding: '10px 14px', borderRadius: '8px',
                fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box',
              }}
            />
            {(targetOptions.length > 0 || searchingTargets) && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0, marginTop: '4px',
                background: '#f3ece0', border: '1px solid #bcae98', borderRadius: '8px',
                maxHeight: '220px', overflowY: 'auto', zIndex: 10,
                boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
              }}>
                {searchingTargets && (
                  <div style={{ padding: '10px 14px', color: '#78716c', fontSize: '0.8rem' }}>Buscando…</div>
                )}
                {targetOptions.map((t) => (
                  <button
                    key={t.drugbank_target_id}
                    type="button"
                    onClick={() => addTarget(t)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      width: '100%', textAlign: 'left', background: 'none', border: 'none',
                      padding: '8px 14px', cursor: 'pointer', color: '#292524', fontSize: '0.85rem',
                      borderBottom: '1px solid #d6ccbb',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#d6ccbb')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                  >
                    <span>{t.name}</span>
                    <span style={{ color: '#57534e', fontSize: '0.72rem', fontFamily: 'monospace' }}>
                      {t.gene_name || t.uniprot_id || t.drugbank_target_id}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {error && (
          <div style={{
            background: '#1a0a0a', border: '1px solid #7f1d1d', color: '#fca5a5',
            padding: '10px 14px', borderRadius: '8px', fontSize: '0.85rem',
          }}>
            ⚠ {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            background: loading ? '#bcae98' : '#2d2621',
            color: '#fff', border: 'none', borderRadius: '8px', padding: '14px',
            fontWeight: 700, fontSize: '0.95rem', cursor: loading ? 'default' : 'pointer',
            transition: 'transform 0.2s',
          }}
        >
          {loading ? 'Analizando estructura y red molecular…' : '🔬 Analizar Compuesto'}
        </button>
      </form>

      {/* RESULTADOS */}
      {result && (
        <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{
            background: '#f3ece0', border: '1px solid #cdd9e6', borderRadius: '12px', padding: '16px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h3 style={{ margin: 0, color: '#1c1917' }}>{result.sandbox.name}</h3>
                <span style={{ color: '#57534e', fontSize: '0.78rem', fontFamily: 'monospace' }}>
                  {result.sandbox.properties.canonical_smiles}
                </span>
              </div>
              <span style={{
                background: `${methodLabels[result.method_used]?.color}20`,
                color: methodLabels[result.method_used]?.color,
                border: `1px solid ${methodLabels[result.method_used]?.color}40`,
                padding: '4px 10px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 700,
              }}>
                {methodLabels[result.method_used]?.label}
              </span>
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <PropertyBadge label="Peso Molecular" value={result.sandbox.properties.molecular_weight} unit="Da" />
              <PropertyBadge label="LogP"            value={result.sandbox.properties.logp} />
              <PropertyBadge label="TPSA"            value={result.sandbox.properties.tpsa} unit="Å²" />
              <PropertyBadge label="Donadores H"     value={result.sandbox.properties.h_bond_donors} />
              <PropertyBadge label="Aceptores H"     value={result.sandbox.properties.h_bond_acceptors} />
              <PropertyBadge label="Enlaces rotables" value={result.sandbox.properties.rotatable_bonds} />
              <PropertyBadge label="Anillos aromáticos" value={result.sandbox.properties.aromatic_rings} />
              <PropertyBadge label="Átomos pesados"  value={result.sandbox.properties.num_heavy_atoms} />
            </div>

            {result.sandbox.linked_targets.length > 0 && (
              <div style={{ marginTop: '10px', fontSize: '0.78rem', color: '#78716c' }}>
                Targets candidatos vinculados: {result.sandbox.linked_targets.join(', ')}
              </div>
            )}
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
              <h3 style={{ color: '#1c1917', fontSize: '1.05rem', margin: 0 }}>
                🏆 Fármacos más similares ({result.combined.length})
              </h3>
              {result.combined.length > 0 && (
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button onClick={exportResultsCsv} style={exportBtnStyle}>⬇ CSV</button>
                  <button onClick={exportResultsJson} style={exportBtnStyle}>⬇ JSON</button>
                  <button onClick={openHtmlReport} style={exportBtnStyle}>📄 Reporte</button>
                </div>
              )}
            </div>

            {result.targets_inferred && (
              <div style={{
                background: '#0f1f2e', border: '1px solid #1e4a5f', borderRadius: '8px',
                padding: '8px 14px', fontSize: '0.78rem', color: '#7dd3fc', marginBottom: '10px',
              }}>
                ℹ️ No se especificaron targets candidatos. La similitud de comportamiento se calculó
                a partir de los targets de los fármacos estructuralmente más similares.
                Para mayor precisión, añade targets conocidos o importa desde SwissTargetPrediction.
              </div>
            )}

            {result.combined.length === 0 ? (
              <div style={{
                background: '#d6ccbb', border: '1px dashed #bcae98', borderRadius: '10px',
                padding: '24px', textAlign: 'center', color: '#78716c',
              }}>
                No se encontraron coincidencias estructurales ni de comportamiento.
                {result.method_used === 'structural_only' && (
                  <div style={{ fontSize: '0.78rem', marginTop: '6px' }}>
                    Prueba seleccionando targets candidatos para activar la comparación por comportamiento.
                  </div>
                )}
                {result.structural_similarity.length === 0 && (
                  <div style={{ fontSize: '0.78rem', marginTop: '6px' }}>
                    La base de datos aún no tiene fingerprints estructurales precalculados,
                    o el compuesto no se asemeja a ningún fármaco indexado.
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {result.combined.map((r, idx) => (
                  <CombinedResultCard key={r.drugbank_id} result={r} rank={idx + 1} sandboxSmiles={result.sandbox.smiles || result.sandbox.properties?.canonical_smiles} />
                ))}
              </div>
            )}
          </div>

          {/* ── Sección de Rutas y GO ─────────────────────────────────────── */}
          <div style={{
            background: '#f3ece0', border: '1px solid #cdd9e6', borderRadius: '12px', padding: '16px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h3 style={{ color: '#1c1917', fontSize: '1.05rem', margin: 0 }}>
                  🗺️ Rutas Metabólicas y Procesos GO
                </h3>
                <p style={{ color: '#57534e', fontSize: '0.78rem', margin: '4px 0 0 0' }}>
                  KEGG pathways, STRING PPI y anotaciones GO para los targets directos y los de fármacos similares
                </p>
              </div>
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                {pathwayData && (
                  <button onClick={exportPathwaysJson} style={exportBtnStyle}>⬇ JSON completo</button>
                )}
                <button
                  onClick={loadPathways}
                  disabled={loadingPathways}
                  style={{
                    background: loadingPathways ? '#d6ccbb' : '#2d2621',
                    border: '1px solid #2d6a8a', color: loadingPathways ? '#0369a1' : '#7dd3fc',
                    padding: '8px 16px', borderRadius: '7px', fontWeight: 700,
                    fontSize: '0.82rem', cursor: loadingPathways ? 'default' : 'pointer',
                  }}
                >
                  {loadingPathways ? '⏳ Cargando…' : pathwayData ? '🔄 Recargar' : '🔬 Analizar rutas y GO'}
                </button>
              </div>
            </div>

            {pathwayError && (
              <div style={{
                background: '#1a0a0a', border: '1px solid #7f1d1d', color: '#fca5a5',
                padding: '8px 12px', borderRadius: '7px', fontSize: '0.8rem', marginTop: '10px',
              }}>⚠ {pathwayError}</div>
            )}

            {loadingPathways && (
              <div style={{ color: '#57534e', fontSize: '0.82rem', textAlign: 'center', padding: '24px' }}>
                Consultando KEGG y STRING (puede tardar 10–30 s por rate limiting)…
              </div>
            )}

            {pathwayData && !loadingPathways && (
              <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {pathwayData.notes.length > 0 && (
                  <div style={{ color: '#78716c', fontSize: '0.75rem', marginBottom: '8px', fontStyle: 'italic' }}>
                    {pathwayData.notes.join(' • ')}
                  </div>
                )}

                <div style={{ color: '#57534e', fontSize: '0.75rem', marginBottom: '12px' }}>
                  Targets analizados: {pathwayData.targets_used.length} proteínas
                  {' '}({pathwayData.targets_used.map(t => t.gene_name || t.uniprot_id).filter(Boolean).slice(0, 8).join(', ')}
                  {pathwayData.targets_used.length > 8 ? ` +${pathwayData.targets_used.length - 8} más` : ''})
                </div>

                {/* ── Contextualización: qué afecta y qué posiblemente afecta ── */}
                {networkSummary && (
                  <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '14px' }}>
                    <div style={{
                      flex: 1, minWidth: '150px', background: '#0c1a2b',
                      border: '1px solid #1e4a5f', borderRadius: '8px', padding: '10px 14px',
                    }}>
                      <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#38bdf8', fontFamily: 'monospace' }}>
                        {networkSummary.directCount}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#78716c' }}>🎯 proteínas que <strong style={{ color: '#7dd3fc' }}>afecta</strong> directamente</div>
                    </div>
                    <div style={{
                      flex: 1, minWidth: '150px', background: '#1a130a',
                      border: '1px solid #78350f', borderRadius: '8px', padding: '10px 14px',
                    }}>
                      <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fbbf24', fontFamily: 'monospace' }}>
                        {networkSummary.indirectCount}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#78716c' }}>🔗 proteínas que <strong style={{ color: '#fde68a' }}>posiblemente afecta</strong> (PPI)</div>
                    </div>
                    <div style={{
                      flex: 1, minWidth: '150px', background: '#042f2e',
                      border: '1px solid #134e4a', borderRadius: '8px', padding: '10px 14px',
                    }}>
                      <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#5eead4', fontFamily: 'monospace' }}>
                        {networkSummary.keggCount}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#78716c' }}>🗺️ rutas KEGG asociadas</div>
                    </div>
                    {networkSummary.ctdInteractions > 0 && (
                      <div style={{
                        flex: 1, minWidth: '150px', background: '#1a1206',
                        border: '1px solid #78350f', borderRadius: '8px', padding: '10px 14px',
                      }}>
                        <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fbbf24', fontFamily: 'monospace' }}>
                          {networkSummary.ctdInteractions.toLocaleString()}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#78716c' }}>🧪 interacciones químico-gen (CTD)</div>
                      </div>
                    )}
                    {networkSummary.topProcess && (
                      <div style={{
                        flex: 2, minWidth: '200px', background: '#f3ece0',
                        border: '1px solid #d6ccbb', borderRadius: '8px', padding: '10px 14px',
                      }}>
                        <div style={{ fontSize: '0.72rem', color: '#78716c', marginBottom: '2px' }}>Proceso biológico predominante</div>
                        <div style={{ fontSize: '0.85rem', color: '#5b21b6', fontWeight: 600 }}>{networkSummary.topProcess}</div>
                      </div>
                    )}
                  </div>
                )}

                {/* ── Visualización de red ───────────────────────────────────── */}
                <div style={{ marginBottom: '18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
                    <span style={{ color: '#57534e', fontSize: '0.82rem', fontWeight: 700 }}>🕸️ Red molecular</span>
                    <div style={{ display: 'flex', background: '#f3ece0', borderRadius: '7px', border: '1px solid #bcae98', overflow: 'hidden' }}>
                      {([
                        ['effect',  '🎯 Efecto (directo/indirecto)'],
                        ['pathway', '🗺️ Rutas asociadas'],
                      ] as const).map(([key, lbl]) => (
                        <button
                          key={key}
                          type="button"
                          onClick={() => setGraphView(key)}
                          style={{
                            padding: '6px 12px', border: 'none', cursor: 'pointer', fontSize: '0.74rem', fontWeight: 600,
                            background: graphView === key ? '#1e4a5f' : 'transparent',
                            color: graphView === key ? '#0284c7' : '#78716c',
                          }}
                        >{lbl}</button>
                      ))}
                    </div>
                  </div>

                  {graphView === 'effect' ? (
                    effectGraph.nodes.length > 1 ? (
                      <>
                        <CytoscapeGraph
                          nodes={effectGraph.nodes}
                          edges={effectGraph.edges}
                          height={440}
                          layout="cose"
                          exportFilename={`red_efecto_${(result?.sandbox.name || 'compuesto').replace(/\s+/g, '_')}`}
                        />
                        <p style={{ color: '#57534e', fontSize: '0.74rem', margin: '8px 0 0 0' }}>
                          El compuesto (violeta) toca sus <strong style={{ color: '#0369a1' }}>targets directos</strong> (azul, línea continua).
                          Los <strong style={{ color: '#fde68a' }}>vecinos PPI</strong> (ámbar, línea punteada) son proteínas que
                          podría afectar indirectamente a través de la red de interacción proteína-proteína de STRING.
                        </p>
                        <GraphLegend items={[
                          { color: '#a855f7', border: '#e9d5ff', label: 'Compuesto sandbox' },
                          { color: '#0c4a6e', border: '#38bdf8', label: 'Target directo (afecta)' },
                          { color: '#d6ccbb', border: '#fbbf24', label: 'Vecino PPI (posiblemente afecta)' },
                          { color: '', border: '#78350f', label: 'Interacción indirecta', dashed: true },
                        ]} />
                      </>
                    ) : (
                      <div style={{ color: '#57534e', fontSize: '0.8rem', textAlign: 'center', padding: '24px', border: '1px dashed #bcae98', borderRadius: '10px' }}>
                        Sin red PPI suficiente para graficar (STRING no devolvió vecinos para estos targets).
                      </div>
                    )
                  ) : (
                    pathwayGraph.nodes.length > 1 ? (
                      <>
                        <CytoscapeGraph
                          nodes={pathwayGraph.nodes}
                          edges={pathwayGraph.edges}
                          height={440}
                          layout="cose"
                          exportFilename={`red_rutas_${(result?.sandbox.name || 'compuesto').replace(/\s+/g, '_')}`}
                        />
                        <p style={{ color: '#57534e', fontSize: '0.74rem', margin: '8px 0 0 0' }}>
                          Cada nodo verde es una <strong style={{ color: '#34d399' }}>ruta KEGG</strong>; su tamaño crece con el número de
                          targets que participan en ella. Las proteínas (azul) conectan las rutas donde el compuesto concentra su efecto.
                        </p>
                        <GraphLegend items={[
                          { color: '#065f46', border: '#34d399', label: 'Ruta KEGG' },
                          { color: '#0c4a6e', border: '#38bdf8', label: 'Proteína diana' },
                        ]} />
                      </>
                    ) : (
                      <div style={{ color: '#57534e', fontSize: '0.8rem', textAlign: 'center', padding: '24px', border: '1px dashed #bcae98', borderRadius: '10px' }}>
                        Sin rutas KEGG mapeadas para graficar.
                      </div>
                    )
                  )}
                </div>

                <KeggTable
                  pathways={pathwayData.kegg?.pathways ?? []}
                  onExportCsv={exportKeggCsv}
                  onExportJson={() => downloadJson('kegg_pathways.json', pathwayData.kegg)}
                />

                <FunctionalTable
                  title="GO — Proceso Biológico"
                  items={pathwayData.go_process}
                  termPrefix="GO:"
                  exportName="go_process"
                  onExportCsv={exportGoProcessCsv}
                  onExportJson={() => downloadJson('go_process.json', pathwayData.go_process)}
                />

                <FunctionalTable
                  title="GO — Función Molecular"
                  items={pathwayData.go_function}
                  termPrefix="GO:"
                  exportName="go_function"
                  onExportCsv={() => downloadCsv('go_function.csv',
                    ['GO Term', 'Descripción', 'N° genes', 'Genes', 'FDR'],
                    pathwayData.go_function.map(t => [t.term, t.description, t.gene_count, t.genes.join('; '), t.fdr]) as any)}
                  onExportJson={() => downloadJson('go_function.json', pathwayData.go_function)}
                />

                <FunctionalTable
                  title="GO — Componente Celular"
                  items={pathwayData.go_component}
                  termPrefix="GO:"
                  exportName="go_component"
                  onExportCsv={() => downloadCsv('go_component.csv',
                    ['GO Term', 'Descripción', 'N° genes', 'Genes', 'FDR'],
                    pathwayData.go_component.map(t => [t.term, t.description, t.gene_count, t.genes.join('; '), t.fdr]) as any)}
                  onExportJson={() => downloadJson('go_component.json', pathwayData.go_component)}
                />

                <FunctionalTable
                  title="Reactome"
                  items={pathwayData.reactome}
                  exportName="reactome"
                  onExportCsv={() => downloadCsv('reactome.csv',
                    ['Término', 'Descripción', 'N° genes', 'Genes', 'FDR'],
                    pathwayData.reactome.map(t => [t.term, t.description, t.gene_count, t.genes.join('; '), t.fdr]) as any)}
                  onExportJson={() => downloadJson('reactome.json', pathwayData.reactome)}
                />

                <FunctionalTable
                  title="WikiPathways"
                  items={pathwayData.wikipathways ?? []}
                  exportName="wikipathways"
                  onExportCsv={() => downloadCsv('wikipathways.csv',
                    ['ID', 'Descripción', 'N° genes', 'Genes', 'FDR'],
                    (pathwayData.wikipathways ?? []).map(t => [t.term, t.description, t.gene_count, t.genes.join('; '), t.fdr]) as any)}
                  onExportJson={() => downloadJson('wikipathways.json', pathwayData.wikipathways)}
                />

                <PpiTable
                  neighbors={pathwayData.string_ppi?.neighbors ?? []}
                  onExportCsv={exportPpiCsv}
                />

                {pathwayData.ctd && (
                  <CtdSection
                    ctd={pathwayData.ctd}
                    onExportSummaryCsv={exportCtdSummaryCsv}
                    onExportGenesCsv={exportCtdGenesCsv}
                    onExportJson={exportCtdJson}
                  />
                )}

                {pathwayData.kegg?.unmapped_targets && pathwayData.kegg.unmapped_targets.length > 0 && (
                  <div style={{ color: '#57534e', fontSize: '0.72rem', marginTop: '6px' }}>
                    Targets sin mapeo KEGG: {pathwayData.kegg.unmapped_targets.join(', ')}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Cascada de efectos (propagación PPI local) ──────────────────── */}
          <div style={{
            background: '#f3ece0', border: '1px solid #3b1a5c', borderRadius: '12px', padding: '16px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h3 style={{ color: '#1c1917', fontSize: '1.05rem', margin: 0 }}>
                  🔗 Cascada de efectos (propagación)
                </h3>
                <p style={{ color: '#57534e', fontSize: '0.78rem', margin: '4px 0 0 0', maxWidth: '560px' }}>
                  Propaga el efecto del compuesto desde sus dianas por la red molecular. <strong style={{ color: '#6d28d9' }}>Dirigida</strong>: sentido activación/inhibición (KEGG, con signo). <strong style={{ color: '#0369a1' }}>Difusión</strong>: magnitud del alcance (STRING, sin signo).
                </p>
              </div>
              {propData && propData.downstream.length > 0 && (
                <button onClick={exportPropCsv} style={exportBtnStyle}>⬇ CSV</button>
              )}
            </div>

            {/* Toggle de modo: cada opción lanza la propagación en ese modo */}
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
              <button
                onClick={() => loadPropagation('directed')}
                disabled={loadingProp}
                style={{
                  background: propMode === 'directed' ? '#2d2621' : '#f3ece0',
                  border: `1px solid ${propMode === 'directed' ? '#6d28d9' : '#bcae98'}`,
                  color: propMode === 'directed' ? '#e9d5ff' : '#57534e',
                  padding: '8px 16px', borderRadius: '7px', fontWeight: 700, fontSize: '0.8rem',
                  cursor: loadingProp ? 'default' : 'pointer',
                }}
              >
                🧭 Dirigida (signo)
              </button>
              <button
                onClick={() => loadPropagation('diffusion')}
                disabled={loadingProp}
                style={{
                  background: propMode === 'diffusion' ? '#2d2621' : '#f3ece0',
                  border: `1px solid ${propMode === 'diffusion' ? '#2d6a8a' : '#bcae98'}`,
                  color: propMode === 'diffusion' ? '#0369a1' : '#57534e',
                  padding: '8px 16px', borderRadius: '7px', fontWeight: 700, fontSize: '0.8rem',
                  cursor: loadingProp ? 'default' : 'pointer',
                }}
              >
                🌊 Difusión (magnitud)
              </button>
            </div>

            {propError && (
              <div style={{
                background: '#1a0a0a', border: '1px solid #7f1d1d', color: '#fca5a5',
                padding: '8px 12px', borderRadius: '7px', fontSize: '0.8rem', marginTop: '10px',
              }}>⚠ {propError}</div>
            )}

            {propData && !loadingProp && (
              propData.available && propData.downstream.length > 0 ? (
                <div style={{ marginTop: '14px' }}>
                  <div style={{ color: '#57534e', fontSize: '0.75rem', marginBottom: '4px' }}>
                    Semillas: {propData.seeds_used.join(', ')}
                    {propData.seeds_missing.length > 0 && (
                      <span style={{ color: '#78716c' }}> · sin nodo en la red: {propData.seeds_missing.join(', ')}</span>
                    )}
                  </div>
                  {propData.mode === 'directed' && (
                    <div style={{ color: '#78716c', fontSize: '0.72rem', marginBottom: '10px' }}>
                      Asumiendo que el compuesto <strong style={{ color: '#fca5a5' }}>inhibe</strong> sus dianas ·
                      cascada de {propData.max_hops} saltos · <span style={{ color: '#15803d' }}>↑ activado</span> / <span style={{ color: '#9f1239' }}>↓ inhibido</span> aguas abajo
                    </div>
                  )}

                  {/* Grafo dirigido con signo (solo modo dirigido) */}
                  {propData.mode === 'directed' && cascadeGraph.edges.length > 0 && (
                    <div style={{ marginBottom: '14px' }}>
                      <CytoscapeGraph
                        nodes={cascadeGraph.nodes}
                        edges={cascadeGraph.edges}
                        height={420}
                        layout="breadthfirst"
                        exportFilename={`cascada_${(result?.sandbox.name || 'compuesto').replace(/\s+/g, '_')}`}
                      />
                      <GraphLegend items={[
                        { color: '#a855f7', border: '#e9d5ff', label: 'Diana (semilla)' },
                        { color: '#14532d', border: '#4ade80', label: 'Activado ↑' },
                        { color: '#7f1d1d', border: '#fb7185', label: 'Inhibido ↓' },
                        { color: '', border: '#22c55e', label: 'Activación (→)', dashed: true },
                        { color: '', border: '#fb7185', label: 'Inhibición (⊣)', dashed: true },
                      ]} />
                    </div>
                  )}
                  {(() => {
                    const directed = propData.mode === 'directed';
                    const maxVal = Math.max(...propData.downstream.map(d => directed ? (d.magnitude ?? 0) : (d.score ?? 0)), 1e-9);
                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                        {propData.downstream.map((d, i) => {
                          const up = (d.sign ?? 1) > 0;
                          const val = directed ? (d.magnitude ?? 0) : (d.score ?? 0);
                          const barColor = directed
                            ? (up ? 'linear-gradient(90deg,#166534,#4ade80)' : 'linear-gradient(90deg,#9f1239,#fb7185)')
                            : 'linear-gradient(90deg,#6d28d9,#a855f7)';
                          return (
                            <div key={d.gene} style={{
                              display: 'flex', alignItems: 'center', gap: '10px',
                              padding: '4px 8px', borderRadius: '6px',
                              background: i % 2 === 0 ? '#f3ece0' : 'transparent',
                            }}>
                              <span style={{ color: '#57534e', fontFamily: 'monospace', fontSize: '0.72rem', width: '24px' }}>#{i + 1}</span>
                              <span style={{ color: '#292524', fontWeight: 600, fontSize: '0.82rem', fontFamily: 'monospace', width: '84px' }}>{d.gene}</span>
                              {directed && (
                                <span style={{
                                  color: up ? '#15803d' : '#9f1239', fontWeight: 700, fontSize: '0.74rem', width: '74px',
                                }}>{up ? '↑ activa' : '↓ inhibe'}</span>
                              )}
                              <div style={{ flex: 1, height: '6px', background: '#d6ccbb', borderRadius: '4px', overflow: 'hidden' }}>
                                <div style={{ width: `${(val / maxVal) * 100}%`, height: '100%', background: barColor }} />
                              </div>
                              <span style={{ color: '#78716c', fontFamily: 'monospace', fontSize: '0.7rem', width: '64px', textAlign: 'right' }}>
                                {directed ? (d.effect ?? 0).toFixed(3) : (d.score ?? 0).toFixed(5)}
                              </span>
                              {d.is_target ? (
                                <span style={{
                                  background: '#052e16', border: '1px solid #166534', color: '#4ade80',
                                  padding: '1px 7px', borderRadius: '4px', fontSize: '0.64rem', fontWeight: 700, width: '64px', textAlign: 'center',
                                }}>diana DG</span>
                              ) : <span style={{ width: '64px' }} />}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}
                  <p style={{ color: '#57534e', fontSize: '0.72rem', margin: '10px 0 0 0' }}>
                    {propData.mode === 'directed' ? (
                      <>En el grafo, las <strong>aristas</strong> son el tipo de relación de KEGG (verde → activa, rojo ⊣ inhibe) y el <strong>color del nodo</strong> es el estado predicho tras propagar desde dianas inhibidas (verde activado, rojo inhibido). Los marcados <strong style={{ color: '#15803d' }}>diana DG</strong> son dianas conocidas que la cascada activa o inhibe — candidatos a efecto secundario. Hipótesis mecanística, no verdad absoluta.</>
                    ) : (
                      <>Magnitud de difusión (Personalized PageRank, sin signo). Los marcados <strong style={{ color: '#15803d' }}>diana DG</strong> son dianas conocidas que el efecto alcanza aguas abajo.</>
                    )}
                  </p>
                </div>
              ) : (
                <div style={{ color: '#57534e', fontSize: '0.8rem', textAlign: 'center', padding: '20px' }}>
                  {propData.reason || (propData.available
                    ? 'Sin propagación: las semillas no tienen nodo en esta red.'
                    : (propMode === 'directed'
                        ? 'Red regulatoria KEGG no cargada (ejecuta load_kegg_regulatory.py).'
                        : 'Red STRING no cargada (ejecuta load_string_network.py).'))}
                </div>
              )
            )}

            {loadingProp && (
              <div style={{ color: '#57534e', fontSize: '0.82rem', textAlign: 'center', padding: '20px' }}>
                Propagando el efecto por la red…
              </div>
            )}
          </div>

          <div style={{ marginTop: '16px' }}>
            <EmbeddingSimilarityPanel smiles={result.sandbox.smiles || result.sandbox.properties?.canonical_smiles} />
          </div>

          <div style={{ marginTop: '16px' }}>
            <BioactivitySection smiles={result.sandbox.smiles || result.sandbox.properties?.canonical_smiles} showReport={false} />
          </div>

          <div style={{ marginTop: '16px' }}>
            <ReportPanel
              kind="sandbox"
              payload={{ analysis: result, pathways: pathwayData, propagation: propData }}
            />
          </div>
        </div>
      )}
    </div>
    </NotebookLayout>
  );
}
