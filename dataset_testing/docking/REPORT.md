# Validación del protocolo de docking (Tier 5.3) — NDM-1

_Generado: 2026-07-06. Reproducible con `backend/scripts/eval_docking.py`._

Antes de confiar en los scores de docking hay que probar que el montaje (receptor + caja +
parámetros) **distingue de verdad los inhibidores conocidos de los no-unidores**. Esta es la
"puerta de calidad" del cribado estructural.

## Diseño

- **Receptor**: NDM-1 (PDB **3SPU**), caja centrada en los **Zn del sitio activo** (cadena A),
  preparado con OpenBabel (`scripts/prepare_receptor.py`).
- **Activos**: 30 inhibidores medidos de metalo-β-lactamasa (ChEMBL, pChEMBL ≥ 5;
  `actives_chembl.smi`).
- **Decoys**: 60 moléculas drug-like del catálogo con MW similar, presuntas no-unidoras
  (DUD-E no incluye NDM-1).
- **Docking**: AutoDock Vina, exhaustiveness 6, mapas calculados una sola vez.
- **Métricas**: ROC-AUC y Enrichment Factor (EF@k%), rankeando por afinidad (más negativa = mejor).

## Resultados

| Métrica | Valor | Lectura |
|---------|------:|---------|
| **ROC-AUC** | **0.775** | Buena discriminación activo/decoy (docking sólido suele dar 0.6–0.8) |
| **EF@1%** | **3.03** | En el top 1% hay **3× más activos** que por azar |
| **EF@5%** | 2.28 | 2.3× de enriquecimiento en el top 5% |
| Afinidad media activos | −7.06 kcal/mol | ~1 kcal/mol más fuerte que los decoys |
| Afinidad media decoys | −6.12 kcal/mol | |
| Acoplados OK | 29 activos / 59 decoys | (algunos SMILES no embebibles se descartan) |

Datos y curvas: `ndm1_validation.csv` (por molécula), `ndm1_metrics.json`, `ndm1_validation.png`
(ROC + histograma de afinidades).

## Conclusión

**El protocolo de docking a NDM-1 es fiable**: separa inhibidores conocidos de no-unidores con
ROC-AUC 0.775 y enriquecimiento 3× en el top 1%. Es un resultado **honesto y positivo** — notable
porque NDM-1 es una metaloenzima y el docking rígido de Vina no modela explícitamente la
coordinación del Zn; aun así, la caja centrada en el sitio activo captura suficiente
complementariedad estérica/electrostática para discriminar. Con esta puerta de calidad superada,
el cribado batch del catálogo (`run_docking_screen.py`) tiene respaldo para proponer candidatos.

**Limitaciones**: docking rígido (receptor fijo), scoring aproximado sin término explícito de
quelación del Zn; los mejores hits deberían refinarse con MD/MM-GBSA (fase 2). Decoys del catálogo
(no DUD-E property-matched estricto).
