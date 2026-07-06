# Tier 5 — Plan: cribado estructural por docking (NDM-1 como caso piloto)

_Estado: **EN ESPERA** (planificado, no implementado). 2026-07-06._

Basado en el repo `Insilico Drug Discovery for NDM-1` de la tabla de métodos externos. Es la única
recomendación que introduce una **modalidad realmente nueva**: pasar de los métodos basados en
grafo/ligando (Tiers 3–4) al **structure-based drug discovery** (docking molecular + ADMET + MD).
Todos los tiers actuales razonan sobre similitud, topología o propiedades del ligando; ninguno usa
la **estructura 3D de la proteína diana**. Este tier lo añade.

## 1. Objetivo

Dado una **diana** (proteína, p. ej. la β-lactamasa **NDM-1**, clave en resistencia a antibióticos)
y un **conjunto de fármacos** (el catálogo DrugGraph o candidatos de novo del Tier 4.4), estimar la
**afinidad de unión** por docking y rankear candidatos de reposicionamiento/inhibición — con su
perfil ADMET (ya lo tenemos, Tier 4.3/4.6) para priorizar los viables.

## 2. Encaje con lo que ya existe

- **Dianas + UniProt**: `populate_uniprot.py` ya enriquece `:Target` con datos canónicos de UniProt;
  el navegador de dianas ya muestra estructuras (`frontend/*.cif`). Reutilizable como fuente de receptores.
- **Ligandos**: SMILES del catálogo (4310) + generador de novo (SyntheMol/CReM) del Tier 4.4.
- **Filtrado**: ADMET (4.3) y toxicidad Chemprop (4.6) ya puntúan drug-likeness/toxicidad de los hits.
- **Patrón de servicio**: mismo esquema Tier 4 — servicio con degradación 503, script offline, endpoint.

## 3. Datos necesarios (reales, públicos)

| Recurso | Fuente | Uso |
|---------|--------|-----|
| Estructura 3D de la diana | **RCSB PDB** (NDM-1: p. ej. 3SPU, 4EYL) o **AlphaFold DB** por UniProt | Receptor para docking |
| Sitio activo / caja de docking | Literatura / detección de cavidades (fpocket) | Definir el box de búsqueda |
| Ligandos | Catálogo DrugGraph (SMILES) + de novo Tier 4.4 | Moléculas a acoplar |
| Set de validación | Inhibidores conocidos de NDM-1 (ChEMBL) + decoys (DUD-E) | Medir enriquecimiento (ROC/EF) |

## 4. Stack técnico

- **AutoDock Vina** (o **smina/gnina**) — motor de docking open-source, CLI por subprocess (patrón
  ya usado en SyntheMol/Chemprop). GNINA añade rescoring por CNN si hay GPU.
- **Meeko / OpenBabel + RDKit** — preparación de ligandos (3D, protonación, PDBQT).
- **Preparación del receptor**: `prepare_receptor` (ADFR) o script propio; **fpocket** para la cavidad.
- **(Opcional, fase 2) MD** — OpenMM para refinar los top hits (validación de estabilidad del complejo).

## 5. Arquitectura propuesta

```
config/services/docking_service.py   # prepara receptor+ligando, corre Vina por subprocess, parsea afinidad
scripts/prepare_receptor.py          # descarga PDB/AlphaFold, define caja (fpocket), genera PDBQT (offline)
scripts/run_docking_screen.py        # cribado batch del catálogo vs una diana → escribe resultados a Mongo
drugs/views/tools/docking.py         # GET /api/tools/docking/<target>/  (lee resultados precomputados)
frontend/.../DockingTool.tsx         # tabla de hits: afinidad (kcal/mol) + ADMET + estructura
```

- **Compute-once / read-cheap** (igual que GDS materializado y DTI-GNN): el cribado batch es caro
  → se corre offline y persiste `(:Drug)-[:DOCKS_TO {affinity, target}]->(:Target)` en Neo4j o una
  colección Mongo `docking_results`; el endpoint solo lee.
- **Degradación 503** si Vina no está instalado o no hay resultados para la diana.

## 6. Métrica de éxito (validación honesta)

- **Enrichment Factor (EF@1%)** y **ROC-AUC** distinguiendo inhibidores conocidos de NDM-1 (ChEMBL)
  vs. decoys (DUD-E) — el estándar para validar un protocolo de docking antes de confiar en él.
- Correlación docking-score vs. IC50/Ki experimentales cuando existan (ChEMBL bioactividad).

## 7. Esfuerzo y riesgos

- **Esfuerzo**: alto (subsistema nuevo). Fase 1 (Vina + un receptor + cribado + endpoint) ≈ varios
  días; Fase 2 (MD, multi-diana, GPU/GNINA) más.
- **Cómputo**: docking de 4310 ligandos × 1 diana es factible en CPU (minutos-horas por diana);
  MD es caro (mejor GPU). Encaja con el patrón offline + persistencia.
- **Riesgos**: preparación correcta del receptor/caja (la calidad del docking depende de esto);
  el docking rígido sobreestima; mitigar con validación EF/ROC antes de reportar hits.

## 8. Orden sugerido cuando se active

1. `prepare_receptor.py` para NDM-1 (PDB 3SPU) + caja por fpocket.
2. Validar el protocolo con inhibidores ChEMBL vs decoys DUD-E (EF/ROC) — **puerta de calidad**.
3. `run_docking_screen.py` sobre el catálogo → persistir resultados.
4. Endpoint + UI `DockingTool` (afinidad + ADMET + enlace a la estructura).
5. (Fase 2) MD OpenMM para top-10 y generalizar a otras dianas.
