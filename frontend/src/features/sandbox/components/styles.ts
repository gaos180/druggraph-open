/**
 * styles.ts — estilos y helpers de color compartidos por los componentes del Sandbox.
 */
import React from 'react';

/** Color según probabilidad SwissTargetPrediction (0–1) — para fondos oscuros. */
export function probColor(p: number): string {
  if (p >= 0.7) return '#4ade80';
  if (p >= 0.4) return '#facc15';
  if (p >= 0.2) return '#fb923c';
  return '#a8a29e';
}

/** Misma escala pero accesible sobre fondos claros (WCAG AA ≥ 4.5:1). */
export function probColorDark(p: number): string {
  if (p >= 0.7) return '#15803d';
  if (p >= 0.4) return '#92400e';
  if (p >= 0.2) return '#9a3412';
  return '#57534e';
}

/** Color según el tipo de acción CTD (increases ↑ verde / decreases ↓ rojo). */
export function actionColor(action: string): string {
  if (action.startsWith('increases')) return '#4ade80';
  if (action.startsWith('decreases')) return '#fb7185';
  return '#57534e';
}

export const th: React.CSSProperties = {
  padding: '6px 8px', textAlign: 'left', color: '#78716c', fontSize: '0.72rem',
  fontWeight: 600, background: '#f3ece0', position: 'sticky', top: 0,
};
export const td: React.CSSProperties = {
  padding: '5px 8px', color: '#57534e', verticalAlign: 'top',
};
export const miniBtn: React.CSSProperties = {
  background: '#d6ccbb', border: '1px solid #bcae98', color: '#78716c',
  padding: '3px 8px', borderRadius: '5px', fontSize: '0.7rem',
  cursor: 'pointer', fontWeight: 600,
};
export const exportBtnStyle: React.CSSProperties = {
  background: '#d6ccbb', border: '1px solid #bcae98', color: '#57534e',
  padding: '5px 12px', borderRadius: '6px', fontSize: '0.75rem',
  cursor: 'pointer', fontWeight: 600,
};
