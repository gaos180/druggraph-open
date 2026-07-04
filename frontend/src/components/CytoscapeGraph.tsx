import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import cytoscape, { Core, ElementDefinition, LayoutOptions, Layouts } from 'cytoscape';

export interface CyNode {
  id: string;
  label: string;
  kind: 'drug' | 'target' | 'sandbox' | 'predicted' | 'category' | 'seed' | 'activated' | 'inhibited';
  weight?: number;
  meta?: Record<string, any>;
}

export interface CyEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  style?: 'solid' | 'dashed';
  /** +1 activación (flecha verde) / -1 inhibición (barra-T roja) */
  sign?: 1 | -1;
}

interface ContextMenuState {
  x: number;
  y: number;
  node: CyNode;
}

interface Props {
  nodes: CyNode[];
  edges: CyEdge[];
  height?: number | string;
  layout?: string;
  onNodeClick?: (node: CyNode) => void;
  exportFilename?: string;
}

// Paleta "cuaderno": relleno acuarela claro + borde tinta. El texto (debajo del
// nodo, sobre papel) siempre es tinta oscura para legibilidad.
const INK = '#2b251d';
const KIND_STYLE: Record<CyNode['kind'], { bg: string; border: string; text: string }> = {
  drug:      { bg: '#93c5fd', border: INK, text: INK },
  target:    { bg: '#fca5a5', border: INK, text: INK },
  sandbox:   { bg: '#d8b4fe', border: INK, text: INK },
  predicted: { bg: '#fde047', border: INK, text: INK },
  category:  { bg: '#6ee7b7', border: INK, text: INK },
  seed:      { bg: '#fcd34d', border: INK, text: INK },
  activated: { bg: '#86efac', border: INK, text: INK },
  inhibited: { bg: '#fda4af', border: INK, text: INK },
};

function ContextMenu({
  menu,
  onClose,
}: {
  menu: ContextMenuState;
  onClose: () => void;
}) {
  const navigate = useNavigate();

  const isDrug   = menu.node.kind === 'drug' || menu.node.kind === 'sandbox';
  const isTarget = menu.node.kind === 'target';
  const uniprotId = menu.node.meta?.uniprot ?? menu.node.meta?.uniprot_id ?? '';
  const drugId    = menu.node.meta?.drugbank_id ?? menu.node.id;

  const btn: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '8px',
    padding: '8px 12px', cursor: 'pointer', fontSize: '0.85rem',
    color: '#2b251d', background: 'transparent', border: 'none',
    fontFamily: "'Patrick Hand', cursive",
    textAlign: 'left', width: '100%', borderRadius: '4px',
    transition: 'background 0.1s',
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
    onClose();
  };

  return (
    <>
      {/* Backdrop invisible para cerrar */}
      <div
        style={{ position: 'fixed', inset: 0, zIndex: 999 }}
        onClick={onClose}
        onContextMenu={e => { e.preventDefault(); onClose(); }}
      />
      <div
        style={{
          position: 'fixed',
          left: Math.min(menu.x, window.innerWidth - 220),
          top: Math.min(menu.y, window.innerHeight - 200),
          zIndex: 1000,
          background: '#faf6ee',
          border: '2px solid #2b251d',
          borderRadius: '12px',
          boxShadow: '5px 5px 0 rgba(43,37,29,0.25)',
          minWidth: '210px',
          overflow: 'hidden',
        }}
      >
        {/* Cabecera */}
        <div style={{
          padding: '9px 12px 7px',
          borderBottom: '1px solid rgba(43,37,29,0.15)',
          fontSize: '0.82rem', color: '#574c3e',
          fontWeight: 700, fontFamily: "'Patrick Hand', cursive",
        }}>
          <span style={{
            display: 'inline-block', width: '8px', height: '8px',
            borderRadius: '50%', background: KIND_STYLE[menu.node.kind].bg,
            marginRight: '6px',
          }} />
          {menu.node.label.length > 28 ? menu.node.label.slice(0, 28) + '…' : menu.node.label}
        </div>

        {/* Opciones */}
        <div style={{ padding: '4px' }}>
          <button
            style={btn}
            onMouseEnter={e => (e.currentTarget.style.background = '#ece3d2')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            onClick={() => copyToClipboard(menu.node.label)}
          >
            📋 Copiar nombre
          </button>

          {isDrug && (
            <button
              style={btn}
              onMouseEnter={e => (e.currentTarget.style.background = '#ece3d2')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              onClick={() => { navigate(`/drugs/${drugId}`); onClose(); }}
            >
              💊 Ver perfil del fármaco
            </button>
          )}

          {isTarget && (
            <button
              style={btn}
              onMouseEnter={e => (e.currentTarget.style.background = '#ece3d2')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              onClick={() => {
                navigate(`/targets`);
                onClose();
              }}
            >
              🎯 Ver en Navegador de Dianas
            </button>
          )}

          {uniprotId && (
            <button
              style={btn}
              onMouseEnter={e => (e.currentTarget.style.background = '#ece3d2')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              onClick={() => {
                window.open(`https://www.uniprot.org/uniprotkb/${uniprotId}`, '_blank', 'noopener');
                onClose();
              }}
            >
              🔗 Abrir en UniProt ({uniprotId})
            </button>
          )}

          {isDrug && (
            <button
              style={btn}
              onMouseEnter={e => (e.currentTarget.style.background = '#ece3d2')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              onClick={() => copyToClipboard(drugId)}
            >
              🪪 Copiar ID ({drugId.slice(0, 12)})
            </button>
          )}

          {isTarget && uniprotId && (
            <button
              style={btn}
              onMouseEnter={e => (e.currentTarget.style.background = '#ece3d2')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              onClick={() => {
                window.open(`https://string-db.org/cgi/network?identifiers=${uniprotId}`, '_blank', 'noopener');
                onClose();
              }}
            >
              🕸️ Ver red en STRING
            </button>
          )}
        </div>
      </div>
    </>
  );
}

function CytoscapeGraph({
  nodes,
  edges,
  height = 500,
  layout = 'cose',
  onNodeClick,
  exportFilename = 'grafo',
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const layoutRef = useRef<Layouts | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);

  const exportPng = useCallback(() => {
    if (!cyRef.current) return;
    const dataUrl = (cyRef.current as any).png({ full: true, scale: 2, bg: '#faf6ee' });
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `${exportFilename}.png`;
    a.click();
  }, [exportFilename]);

  useEffect(() => {
    if (!contextMenu) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setContextMenu(null);
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [contextMenu]);

  useEffect(() => {
    if (!containerRef.current) return;

    const elements: ElementDefinition[] = [
      ...nodes.map((n) => ({
        data: { id: n.id, label: n.label, kind: n.kind, weight: n.weight ?? 1, meta: n.meta },
      })),
      ...edges.map((e) => ({
        data: { id: e.id, source: e.source, target: e.target, label: e.label ?? '', estyle: e.style ?? 'solid', esign: e.sign ?? 0 },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: cytoscape.NodeSingular) => KIND_STYLE[ele.data('kind') as CyNode['kind']]?.bg ?? '#475569',
            'border-color':     (ele: cytoscape.NodeSingular) => KIND_STYLE[ele.data('kind') as CyNode['kind']]?.border ?? '#64748b',
            'border-width': 2.5,
            'label': 'data(label)',
            'color': INK,
            'font-family': "'Patrick Hand', 'Caveat', cursive",
            'font-size': '12px',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 4,
            'text-max-width': '120px',
            'text-wrap': 'ellipsis',
            'width':  (ele: cytoscape.NodeSingular) => 18 + Math.min(40, (ele.data('weight') ?? 1) * 6),
            'height': (ele: cytoscape.NodeSingular) => 18 + Math.min(40, (ele.data('weight') ?? 1) * 6),
          },
        },
        {
          selector: 'node:selected',
          style: { 'border-width': 4, 'border-color': '#1e1814' },
        },
        {
          selector: 'edge',
          style: {
            'width': 1.8,
            'line-color': '#574c3e',
            'target-arrow-color': '#574c3e',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 0.9,
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-family': "'Patrick Hand', 'Caveat', cursive",
            'font-size': '10px',
            'color': '#574c3e',
            'text-rotation': 'autorotate',
            'text-background-color': '#faf6ee',
            'text-background-opacity': 0.85,
            'text-background-padding': '2px',
          },
        },
        {
          selector: 'edge[estyle = "dashed"]',
          style: {
            'line-style': 'dashed',
            'line-color': '#b45309',
            'target-arrow-color': '#b45309',
          },
        },
        // Aristas con signo (cascada dirigida): +1 activación (verde, flecha) / -1 inhibición (rojo, barra-T)
        {
          selector: 'edge[esign = 1]',
          style: {
            'width': 2,
            'line-color': '#22c55e',
            'target-arrow-color': '#22c55e',
            'target-arrow-shape': 'triangle',
          },
        },
        {
          selector: 'edge[esign = -1]',
          style: {
            'width': 2,
            'line-color': '#fb7185',
            'target-arrow-color': '#fb7185',
            'target-arrow-shape': 'tee',
          },
        },
      ],
      layout: { name: 'preset' } as LayoutOptions,
      wheelSensitivity: 0.2,
      minZoom: 0.2,
      maxZoom: 3,
    });

    const ly = cy.layout({ name: layout, animate: false, padding: 30 } as LayoutOptions);
    layoutRef.current = ly;
    ly.run();

    if (onNodeClick) {
      cy.on('tap', 'node', (evt: cytoscape.EventObject) => {
        const d = evt.target.data();
        onNodeClick({ id: d.id, label: d.label, kind: d.kind, weight: d.weight, meta: d.meta });
      });
    }

    // Menú contextual con clic derecho
    cy.on('cxttap', 'node', (evt: cytoscape.EventObject) => {
      evt.originalEvent?.preventDefault();
      const d = evt.target.data();
      const pos = (evt.originalEvent as MouseEvent);
      setContextMenu({
        x: pos.clientX,
        y: pos.clientY,
        node: { id: d.id, label: d.label, kind: d.kind, weight: d.weight, meta: d.meta },
      });
    });

    // Clic en fondo → cerrar menú
    cy.on('tap', (evt: cytoscape.EventObject) => {
      if (evt.target === cy) setContextMenu(null);
    });

    cyRef.current = cy;
    return () => {
      try { layoutRef.current?.stop(); } catch (_) {}
      layoutRef.current = null;
      try { cy.stop(true, true); } catch (_) {}
      try { cy.destroy(); } catch (_) {}
      cyRef.current = null;
    };
  }, [nodes, edges, layout, onNodeClick]);

  return (
    <div style={{ position: 'relative' }}>
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height,
          // Papel + rejilla "blueprint" tenue (tema cuaderno).
          backgroundColor: '#faf6ee',
          backgroundImage:
            'linear-gradient(to right, rgba(59,130,246,0.10) 1px, transparent 1px), linear-gradient(to bottom, rgba(59,130,246,0.10) 1px, transparent 1px)',
          backgroundSize: '25px 25px',
          border: '2px solid #2b251d',
          borderRadius: '14px',
          boxShadow: '4px 4px 0 rgba(43,37,29,0.12)',
        }}
      />
      {/* Botón exportar PNG */}
      <button
        onClick={exportPng}
        title="Exportar grafo como imagen PNG"
        style={{
          position: 'absolute', top: '10px', right: '10px',
          background: '#faf6ee', border: '2px solid #2b251d',
          color: '#3a332a', padding: '4px 11px', borderRadius: '10px',
          fontSize: '0.78rem', cursor: 'pointer', fontWeight: 700,
          fontFamily: "'Patrick Hand', cursive",
          boxShadow: '2px 2px 0 rgba(43,37,29,0.2)',
          zIndex: 10,
        }}
        onMouseEnter={e => { e.currentTarget.style.background = '#f0e9da'; }}
        onMouseLeave={e => { e.currentTarget.style.background = '#faf6ee'; }}
      >
        ⬇ PNG
      </button>
      <div style={{
        position: 'absolute', bottom: '8px', right: '12px',
        fontSize: '0.72rem', color: '#8a7d6a', pointerEvents: 'none',
        fontFamily: "'Patrick Hand', cursive",
      }}>
        Clic derecho en nodo para más opciones
      </div>
      {contextMenu && (
        <ContextMenu menu={contextMenu} onClose={() => setContextMenu(null)} />
      )}
    </div>
  );
}

export default React.memo(CytoscapeGraph);
