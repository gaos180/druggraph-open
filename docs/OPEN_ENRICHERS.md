# Enriquecedores open-source (`step06`–`step08`)

Estos pasos son **enriquecedores opcionales** del catálogo: se corren _después_ de tener
los documentos base y el grafo poblados. Añaden campos nuevos al documento Mongo `drugs`
desde fuentes abiertas, sin tocar el backbone que producen `step01`/`step03`. Todos son
**idempotentes** (`update_one`/`$set`) y degradan limpiamente si su fuente no está
disponible. Ver atribuciones globales en [`DATA_SOURCES.md`](DATA_SOURCES.md).

## Orden recomendado

Se ejecutan tras cargar el catálogo y las dianas (para tener `targets[*].gene_name`):

```
step01_drugcentral_to_mongo      # backbone del catálogo
step03_build_graph               # grafo Neo4j (:Drug/:Target)
scripts/populate_targets.py      # colección `targets` + gene_name en dianas
─────────────────────────────────────────────────────────────────────
step06_opentargets   →  enriquecedor diana→enfermedad   (necesita gene_name en targets)
step07_pubchem       →  propiedades fisicoquímicas       (necesita cross-ref PubChem CID)
step08_toxinpred     →  toxicidad de péptidos            (requiere input externo, ver abajo)
```

`step06` y `step07` son independientes entre sí y pueden correrse en cualquier orden.
`step08` es un flujo por lote con un paso manual intermedio (ToxinPred no tiene API).

---

## `step06_opentargets.py` — evidencia diana→enfermedad

- **Fuente:** Open Targets Platform (GraphQL API, `api.platform.opentargets.org`). Sin API key.
- **Licencia:** CC0 1.0 (dominio público).
- **Servicio reutilizado:** `config/services/opentargets_service.py`
  - `ensembl_from_symbol(symbol) -> str | None` — mapea símbolo de gen a Ensembl id (ENSG).
  - `target_diseases(ensembl_id, size=15) -> list[dict]` — enfermedades asociadas con score.
  - `REQUESTS_OK: bool` — flag de disponibilidad (degrada si falta `requests`).
- **Campo añadido:** `open_targets_diseases` — lista de
  `{disease, disease_id, score, target_gene}`, top-N por score (por defecto 10).
- **Lógica:** toma los genes de `doc['targets'][*]['gene_name']`, consulta Open Targets
  por gen (cacheado por gen dentro de la corrida) y conserva, por enfermedad, la fila de
  mayor score entre las dianas del fármaco.
- **Flags:** `--limit N` (subconjunto), `--per-target N` (enfermedades pedidas por gen),
  `--top N` (enfermedades guardadas por fármaco).

```bash
python -m scripts.ingest.step06_opentargets --limit 200 --top 10
```

---

## `step07_pubchem.py` — propiedades fisicoquímicas por CID

- **Fuente:** PubChem PUG-REST (`pubchem.ncbi.nlm.nih.gov/rest/pug`). Sin API key.
- **Licencia:** dominio público.
- **Servicio de referencia:** `config/services/pubchem_service.py` (mismo patrón de
  rate-limit; ese cliente no expone "propiedades por CID", así que el paso hace la
  llamada PUG directa con `requests`, respetando ≤ 5 req/s).
- **Campo añadido:** `pubchem_properties` —
  `{cid, MolecularWeight, XLogP, TPSA, HBondDonorCount, HBondAcceptorCount, RotatableBondCount, source}`.
  (Perfil "regla de 5" de Lipinski + TPSA/rotables.)
- **Lógica:** selecciona fármacos con cross-ref `"PubChem CID"` en `external-identifiers`
  y consulta el endpoint `.../compound/cid/<CID>/property/<props>/JSON`. Un error de red
  por fármaco se registra y se continúa.
- **Flags:** `--limit N`.

```bash
python -m scripts.ingest.step07_pubchem --limit 200
```

---

## `step08_toxinpred.py` — toxicidad de péptidos (flujo por lote)

- **Fuente:** ToxinPred (Raghava Lab, IIIT-Delhi),
  https://webs.iiitd.edu.in/raghava/toxinpred/
- **Licencia:** uso académico libre.
- **Campo añadido:** `toxinpred` — `{prediction: "Toxin"|"Non-Toxin", score, sequence, source}`.

> **REQUIERE INPUT EXTERNO.** ToxinPred **no tiene una API pública estable**, y el
> documento de DrugCentral **no trae la secuencia peptídica**. Por eso el paso no inventa
> un endpoint: implementa un flujo honesto en dos modos alrededor del servidor web/binario.

**Modo `export`** — genera un FASTA de fármacos peptídicos candidatos (`type != "small
molecule"` o los que ya tengan una secuencia en el documento; encabezado `>DC<id>|<name>`
para re-emparejar). Los candidatos sin secuencia se listan en un warning para completarlos
manualmente (p.ej. desde UniProt).

```bash
python -m scripts.ingest.step08_toxinpred --mode export --out peptidos.fasta
```

**Paso manual:** subir `peptidos.fasta` a ToxinPred (o correr su binario) y descargar el CSV.

**Modo `annotate`** — lee el CSV de ToxinPred y escribe `toxinpred` en cada fármaco. El
parser tolera nombres de columna variables (case-insensitive, con aliases y flags de
override) y empareja por ID abierto (`DC…`) o por nombre.

```bash
python -m scripts.ingest.step08_toxinpred --mode annotate --csv toxinpred_out.csv
python -m scripts.ingest.step08_toxinpred --mode annotate --csv out.csv \
    --id-col ID --seq-col Sequence --pred-col Prediction --score-col "ML Score" --match id
```

**Supuestos/límites:**
- Solo aplica a fármacos peptídicos; los small molecules se ignoran.
- La cobertura depende de que el operador aporte las secuencias (DrugCentral no las trae).
- El emparejamiento por nombre es exacto (case-insensitive); ante ambigüedad usar `--match id`.

---

## Dependencias

Ninguna dependencia nueva de pip: los tres pasos usan solo `requests` (ya listado en
`requirements-ingest.txt`) y la librería estándar (`csv`, `argparse`, `threading`, `time`).
`step08` no requiere red desde el script (el trabajo online lo hace el operador en el
servidor de ToxinPred).

| Paso | Deps pip | Otros requisitos |
|------|----------|------------------|
| `step06_opentargets` | `requests` (ya) | internet (Open Targets GraphQL); `targets[*].gene_name` poblado |
| `step07_pubchem` | `requests` (ya) | internet (PubChem PUG); cross-ref `PubChem CID` |
| `step08_toxinpred` | — (stdlib) | FASTA + CSV externos de ToxinPred (paso manual) |
