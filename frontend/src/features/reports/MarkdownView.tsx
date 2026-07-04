import React from 'react';

/**
 * MarkdownView — renderizador Markdown mínimo y SEGURO (sin dangerouslySetInnerHTML).
 * Convierte el subconjunto que produce la reportería: encabezados (##, ###),
 * listas (- / *), párrafos y formato en línea (**negrita**, *cursiva*, `código`).
 * Al construir todo con elementos React, no hay superficie de XSS.
 */

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Divide por **negrita**, *cursiva* y `código`, conservando los delimitadores.
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  const parts = text.split(regex).filter((p) => p !== '');
  parts.forEach((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (/^\*\*[^*]+\*\*$/.test(part)) {
      nodes.push(<strong key={key} className="font-bold text-stone-900">{part.slice(2, -2)}</strong>);
    } else if (/^\*[^*]+\*$/.test(part)) {
      nodes.push(<em key={key}>{part.slice(1, -1)}</em>);
    } else if (/^`[^`]+`$/.test(part)) {
      nodes.push(
        <code key={key} className="px-1 py-0.5 rounded bg-stone-200 text-stone-800 text-[0.85em] font-mono">
          {part.slice(1, -1)}
        </code>,
      );
    } else {
      nodes.push(<React.Fragment key={key}>{part}</React.Fragment>);
    }
  });
  return nodes;
}

export default function MarkdownView({ markdown }: { markdown: string }) {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const blocks: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  let paraBuffer: string[] = [];

  const flushList = (key: string) => {
    if (listBuffer.length === 0) return;
    blocks.push(
      <ul key={key} className="list-disc pl-6 my-2 space-y-1 text-stone-700">
        {listBuffer.map((item, i) => (
          <li key={`${key}-${i}`}>{renderInline(item, `${key}-${i}`)}</li>
        ))}
      </ul>,
    );
    listBuffer = [];
  };

  const flushPara = (key: string) => {
    if (paraBuffer.length === 0) return;
    blocks.push(
      <p key={key} className="my-2 text-stone-700 leading-relaxed">
        {renderInline(paraBuffer.join(' '), key)}
      </p>,
    );
    paraBuffer = [];
  };

  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const key = `b-${idx}`;

    if (/^###\s+/.test(line)) {
      flushList(key); flushPara(key);
      blocks.push(<h4 key={key} className="text-base font-bold text-stone-900 mt-4 mb-1">{renderInline(line.replace(/^###\s+/, ''), key)}</h4>);
    } else if (/^##\s+/.test(line)) {
      flushList(key); flushPara(key);
      blocks.push(<h3 key={key} className="text-lg font-hand font-bold text-stone-900 mt-5 mb-1 border-b border-stone-300 pb-1">{renderInline(line.replace(/^##\s+/, ''), key)}</h3>);
    } else if (/^#\s+/.test(line)) {
      flushList(key); flushPara(key);
      blocks.push(<h2 key={key} className="text-xl font-hand font-bold text-stone-900 mt-5 mb-2">{renderInline(line.replace(/^#\s+/, ''), key)}</h2>);
    } else if (/^\s*[-*]\s+/.test(line)) {
      flushPara(key);
      listBuffer.push(line.replace(/^\s*[-*]\s+/, ''));
    } else if (line.trim() === '') {
      flushList(key); flushPara(key);
    } else {
      flushList(key);
      paraBuffer.push(line.trim());
    }
  });
  flushList('end'); flushPara('end');

  return <div className="text-sm">{blocks}</div>;
}
