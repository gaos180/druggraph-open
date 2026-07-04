import React, { useState } from 'react';
import { Sparkles, Download, Copy, Check, AlertTriangle } from 'lucide-react';

import {
  reportsApi,
  ReportKind,
  ReportStyle,
  GeneratedReport,
} from '../../api/reports';
import Modal from '../../components/notebook/Modal';
import MarkdownView from './MarkdownView';
import { downloadText } from '../../utils/download';

interface ReportPanelProps {
  kind: ReportKind;
  /** Datos del análisis; se envían al backend, que los recorta antes de Gemini. */
  payload: unknown;
  /** Deshabilita el botón cuando aún no hay análisis disponible. */
  disabled?: boolean;
  /** Etiqueta opcional para personalizar el botón. */
  label?: string;
}

const STYLES: { value: ReportStyle; label: string; hint: string }[] = [
  { value: 'scientific', label: 'Científico', hint: 'Técnico, para investigador' },
  { value: 'executive',  label: 'Ejecutivo',  hint: 'Divulgativo, accesible' },
];

function errorMessage(err: any): string {
  const status = err?.response?.status;
  const detail = err?.response?.data?.error;
  if (status === 503) {
    return detail || 'La reportería IA no está configurada (falta GEMINI_API_KEY en el servidor).';
  }
  if (status === 502) {
    return detail || 'El servicio de IA falló al generar el informe. Inténtalo de nuevo.';
  }
  if (status === 401) {
    return 'Necesitas iniciar sesión para generar informes.';
  }
  return detail || 'No se pudo generar el informe.';
}

export default function ReportPanel({ kind, payload, disabled, label }: ReportPanelProps) {
  const [style, setStyle] = useState<ReportStyle>('scientific');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState<GeneratedReport | null>(null);
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const generate = async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await reportsApi.generate({ kind, payload, style });
      setReport(data);
      setOpen(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!report) return;
    try {
      await navigator.clipboard.writeText(report.report_markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard no disponible */
    }
  };

  const handleDownload = () => {
    if (!report) return;
    const safe = report.title.replace(/[^\w\-]+/g, '_').slice(0, 60) || 'informe';
    downloadText(`${safe}.md`, report.report_markdown);
  };

  const selChip = (active: boolean) =>
    `px-3 py-1.5 rounded-lg text-xs font-semibold border-2 cursor-pointer transition-colors ${
      active
        ? 'bg-[#1e1814] text-[#faf6ee] border-[#1e1814]'
        : 'bg-transparent text-stone-600 border-stone-300 hover:border-stone-500'
    }`;

  return (
    <div className="border-2 border-[#1e1814] rounded-xl p-4 bg-[#faf6ee] shadow-[4px_4px_0px_#1e1814]">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-5 h-5 text-amber-600" />
        <h3 className="text-lg font-hand font-bold text-stone-900">Informe con IA</h3>
      </div>
      <p className="text-xs text-stone-600 mb-3">
        Genera una interpretación en lenguaje natural de este análisis con Gemini.
        El informe es una hipótesis <strong>in-silico</strong> basada solo en estos datos.
      </p>

      <div className="flex flex-wrap gap-4 mb-3">
        <div>
          <div className="text-[0.7rem] uppercase tracking-wide text-stone-500 mb-1">Estilo</div>
          <div className="flex gap-2">
            {STYLES.map((s) => (
              <button key={s.value} className={selChip(style === s.value)} title={s.hint}
                onClick={() => setStyle(s.value)}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <button
        onClick={generate}
        disabled={disabled || loading}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#1e1814] text-[#faf6ee] font-semibold text-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:bg-stone-800 transition-colors"
      >
        <Sparkles className="w-4 h-4" />
        {loading ? 'Generando informe…' : (label || 'Generar informe')}
      </button>

      {report && !loading && (
        <button
          onClick={() => setOpen(true)}
          className="ml-2 inline-flex items-center gap-1 px-3 py-2 rounded-lg border-2 border-stone-300 text-stone-600 text-sm cursor-pointer hover:border-stone-500"
        >
          Ver último informe
        </button>
      )}

      {error && (
        <div className="mt-3 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} maxWidth="max-w-3xl"
        title={report?.title || 'Informe'}>
        {report && (
          <>
            <div className="flex flex-wrap items-center gap-2 mb-4 text-xs text-stone-500">
              <span className="px-2 py-0.5 rounded bg-stone-200">{report.style === 'scientific' ? 'Científico' : 'Ejecutivo'}</span>
              <span className="px-2 py-0.5 rounded bg-stone-200">{report.model}</span>
              <span>{new Date(report.created_at).toLocaleString()}</span>
              <div className="ml-auto flex gap-2">
                <button onClick={handleCopy}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-stone-300 hover:border-stone-500 cursor-pointer">
                  {copied ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? 'Copiado' : 'Copiar'}
                </button>
                <button onClick={handleDownload}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-stone-300 hover:border-stone-500 cursor-pointer">
                  <Download className="w-3.5 h-3.5" /> Markdown
                </button>
              </div>
            </div>
            <MarkdownView markdown={report.report_markdown} />
          </>
        )}
      </Modal>
    </div>
  );
}
