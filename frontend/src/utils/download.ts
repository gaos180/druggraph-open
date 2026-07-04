/**
 * download.ts — utilidades de descarga de archivos en el navegador.
 * Centraliza la lógica de exportación CSV/JSON usada por varias páginas.
 */

/** Descarga una tabla como CSV (escapa comillas, comas y saltos de línea). */
export function downloadCsv(
  filename: string,
  headers: string[],
  rows: (string | number)[][],
) {
  const esc = (v: string | number) => {
    const s = String(v ?? '');
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s;
  };
  const lines = [headers.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))];
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  triggerDownload(blob, filename);
}

/** Descarga cualquier dato serializable como JSON con sangría. */
export function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  triggerDownload(blob, filename);
}

/** Descarga texto plano (p.ej. un informe en Markdown). */
export function downloadText(filename: string, text: string, mime = 'text/markdown;charset=utf-8;') {
  const blob = new Blob([text], { type: mime });
  triggerDownload(blob, filename);
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
