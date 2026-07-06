# Evaluación de integración — pharmaco-suite (Eduardo Cubillos)

_2026-07-06. Repo evaluado: https://github.com/EduardoCubillos/pharmaco-suite (clonado e inspeccionado)._

Evaluación de integrar el `pharmaco-suite` de un compañero en DrugGraph Open. Aporta **modelado de
pharmacóforos 3D** (ausente hoy) y **diseño de novo guiado por pharmacóforo**, y encaja como el
puente natural al **Tier 5 estructural** (`docs/TIER5_PLAN.md`).

## 1. Qué es (verificado sobre el código, ~4568 líneas, 2 CLIs)

- **`pharmacophore_cli`** — genera modelos de pharmacóforo 3D desde tres perspectivas y los combina
  por **consenso ponderado** (voto cruzado, estilo PHASE/Baroni 2007):
  - **SBP** (structure-based): interacciones proteína-ligando de un co-cristal PDB vía **PLIP**
    (fallback a BioPython por distancias si PLIP falta).
  - **LBP** (ligand-based): features RDKit sobre uno o varios SMILES (multi-ligando: features en ≥50%).
  - **RBP** (receptor-based): residuos del sitio de unión mapeados a features a pH fisiológico.
  - **Consensus** + grafo 2D (MST) + visores HTML interactivos (py3Dmol/vis.js).
- **`denovo_cli`** — de novo por **algoritmo genético SELFIES** con fitness de pharmacóforo LBP
  multi-ligando + filtro ADMET (Lipinski/QED≥0.3/SA≤5/PSA≤140) + filtro de diversidad (Tanimoto<0.85).
  Descarga activos de **ChEMBL** por target ID. Salida: **SDF + PDBQT (Meeko, listo para AutoDock Vina)** + CSV.

Código limpio, modular (`core/` por CLI) y **bien citado** (Wolber&Langer 2005, Baroni 2007, PLIP,
SELFIES, Vina…). Calidad académica sólida.

## 2. Compatibilidad — VERIFICADA en nuestro venv ✅

- **Deps**: 7/13 ya estaban en el venv (rdkit, numpy, pandas, scipy, matplotlib, requests, networkx).
  Instalé las 4 ligeras que faltaban (biopython, selfies, py3Dmol, lxml) sin conflicto con torch/GDS.
  Opcionales: **meeko** (export PDBQT/docking) y **plip** (mejor SBP; hay fallback).
- **Smoke test**: `pharmacophore.py lbp` sobre 3 SMILES (aspirina/ibuprofeno/ác. salicílico) corrió
  con nuestro RDKit 2026.3 y generó 4 features de consenso + PDB + HTML. **Corre sin fricción.**
- No usa torch, GDS ni conda obligatorio (recomienda conda para RDKit, pero el pip-RDKit nuestro sirve).

## 3. Encaje estratégico

| Aspecto | Valoración |
|---------|-----------|
| **Pharmacóforos** | 🟢 **Modalidad NUEVA** — DrugGraph no tiene nada de esto. Alto valor. |
| **Puente al Tier 5** | 🟢 SBP trabaja desde estructura PDB (structure-based) y el de novo **exporta PDBQT listo para Vina** → alimenta directamente el cribado por docking del `TIER5_PLAN.md`. Pharmacóforo → docking es el flujo estándar. |
| **De novo (denovo_cli)** | 🟡 **Solapa** con Tier 4.4 (CReM/SyntheMol/REINVENT), pero con motor distinto (GA SELFIES + fitness pharmacofórico). Complementario: sería un 4º motor. |
| **Filtro ADMET** | 🟡 Solapa con el scoring de nuestro `denovo_service` (Lipinski/QED/SA). Redundante pero inocuo. |
| **Datos que ya tenemos** | 🟢 `:Target`+UniProt (IDs PDB para SBP/RBP), catálogo SMILES (LBP), `chembl_service` (activos por target). Se enchufan bien. |

**Síntesis**: pharmaco-suite + el `TIER5_PLAN` (docking Vina) = un **pipeline estructural completo**:
pharmacóforo (del receptor) → de novo guiado → PDBQT → docking → validación EF/ROC.

## 4. Arquitectura de integración recomendada

**Opción A (recomendada) — wrapper de servicio por subprocess**, idéntico al patrón ya usado con
SyntheMol y Chemprop (degradación 503, cómputo offline, endpoint que lee resultados):

```
config/services/pharmacophore_service.py   # invoca pharmacophore.py (all/sbp/lbp/rbp) por subprocess
drugs/views/tools/pharmacophore.py         # POST /api/tools/pharmacophore/  → features + visor HTML
frontend/.../PharmacophoreTool.tsx          # entrada: target PDB+ligando ó SMILES del catálogo
# y como 4º motor de novo:
denovo_service.py  → engine='pharma_ga'    # delega en denovo_cli/denovo.py (GA SELFIES + fitness LBP)
```

- **Vendorizar** el suite en `backend/third_party/pharmaco_suite/` (o instalarlo como paquete) y
  llamarlo con `sys.executable`/su binario, como hice con chemprop. Bajo acoplamiento, sin reescribir.
- Los outputs HTML interactivos del pharmacóforo se pueden servir tal cual en el frontend.
- Opción B (importar sus módulos `core/` directamente) = más acoplado y frágil ante cambios; no recomendada.

## 5. Plan concreto (como Tier 5, por fases)

1. **5.1 — Pharmacóforos** (mayor valor nuevo, deps ligeras): servicio + endpoint + UI para SBP/LBP/RBP/
   consenso. Alimentar los PDB IDs desde `:Target`/UniProt; LBP desde SMILES del catálogo o de novo.
2. **5.2 — De novo pharmaco-guiado**: `engine='pharma_ga'` en `denovo_service`, usando `chembl_service`
   para los activos y el fitness LBP. Salida SDF/PDBQT.
3. **5.3 — Docking** (del `TIER5_PLAN.md`): el PDBQT de 5.2 → AutoDock Vina → cribado + validación
   EF/ROC vs. inhibidores conocidos. Cierra el pipeline estructural.

## 6. Dependencias a añadir (a `requirements-ml.txt`, todas ligeras)

`biopython selfies py3Dmol lxml` (ya instaladas y probadas) + opcionales `meeko` (PDBQT) y `plip`
(SBP de calidad). Ninguna entra en conflicto con torch/transformers/GDS.

## 7. Riesgos y bloqueadores

| Riesgo | Severidad | Mitigación |
|--------|-----------|-----------|
| **Sin LICENCIA** en el repo (all rights reserved por defecto) | 🔴 **Crítico para la edición OPEN** | DrugGraph Open es redistribuible; NO se puede vendorizar/publicar sin permiso. **Pedir a Eduardo que añada una licencia OSI (MIT/Apache-2.0)** compatible. Para uso local del curso no bloquea. |
| PLIP/Meeko opcionales | 🟡 Medio | SBP tiene fallback BioPython; PDBQT solo si se hace docking. Documentar como opcionales. |
| Solape de de novo/ADMET con Tier 4 | 🟢 Bajo | Convivencia (motor extra), no reemplazo. |
| Cómputo del GA (pop 60 × 50 gen) | 🟢 Bajo | CPU, minutos; encaja en el patrón offline. |
| RDKit vía conda (recomendado por el suite) | 🟢 Bajo | Verificado: el pip-RDKit del venv funciona (smoke test OK). |

## 8. Esfuerzo estimado

- **5.1 Pharmacóforos** (servicio+endpoint+UI): ~1 integración tipo Chemprop/SyntheMol (hechas en esta
  sesión). Bajo-medio.
- **5.2 De novo pharma-GA**: menor (reusa `denovo_service` + `chembl_service`).
- **5.3 Docking**: la pieza mayor (subsistema Vina del `TIER5_PLAN`).

## 9. Recomendación

**Integrar, como Tier 5, empezando por el módulo de pharmacóforos (5.1).** Es una modalidad nueva de
alto valor, dependencias ligeras, ya probado en nuestro entorno, y encaja limpiamente en el patrón de
servicios existente. Luego 5.2 (de novo pharma-guiado) y 5.3 (docking) completan el pipeline estructural.

**Acción previa imprescindible**: resolver la **licencia** con Eduardo antes de vendorizar/publicar en
el repo open (coautoría/atribución + licencia OSI). Sin eso, la integración queda para uso local, no
para la edición redistribuible.
