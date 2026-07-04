# DDI y CPI open — TWOSIDES · DDInter · STITCH

Guía de las fuentes abiertas que reemplazan las interacciones fármaco-fármaco (DDI)
propietarias de DrugBank y que añaden interacciones químico-proteína (CPI) al grafo.

Todo el pipeline vive en `backend/scripts/ingest/` y se ejecuta como módulo desde
`backend/` (`python -m scripts.ingest.<modulo>`), reutilizando las conexiones de
`scripts/ingest/_common.py` (Mongo, Neo4j, Postgres, `open_id`, `chunked`, `log`).

---

## 1. Fuentes y licencias

| Fuente | Contenido | Licencia | Descarga |
|--------|-----------|----------|----------|
| **TWOSIDES** (nSIDES / Tatonetti Lab) | DDI de farmacovigilancia (eventos adversos por par de fármacos), identificados por **STITCH stereo/flat-CID** | **CC0** (uso libre) | https://nsides.io · https://tatonettilab.org/resources/nsides/ |
| **DDInter 2.0** | DDI curadas con nivel de severidad (Major/Moderate/Minor), identificadas por **nombre** | **CC BY-NC-SA** (solo académico) | http://ddinter.scbdd.com/ |
| **STITCH v5.0** | Interacciones químico(CID)–proteína(ENSP) con `combined_score` | **CC BY 4.0** (atribución) | http://stitch.embl.de/ → `9606.protein_chemical.links.detailed.v5.0.tsv.gz` |
| **STRING info** (crosswalk ENSP→gen) | `string_protein_id → preferred_name` | CC BY 4.0 | https://stringdb-downloads.org/ → `9606.protein.info.v12.0.txt.gz` |

> Los ficheros pueden pesar cientos de MB o GB. **No se descargan automáticamente**:
> baja el fichero a mano y pásale la ruta local a los scripts.

---

## 2. Mapeo de identificadores

### Fármaco por PubChem CID (robusto)
El ID primario de cada fármaco es el ID abierto `DC<struct_id>`. Para cruzar fuentes
externas usamos el **PubChem CID**, que step01 guarda en el documento Mongo `drugs`
como `external-identifiers: [{ "resource": "PubChem CID", "identifier": "<cid>" }]`.

- `step04_ddi_open.py` construye el índice `CID → mongo_id` desde ese campo y resuelve
  cada par DDI por CID (con normalización de ceros a la izquierda y de prefijos STITCH
  residuales `CIDs/CIDm`). Si el CSV trae `name_a,name_b` en vez de `cid_a,cid_b`, cae
  automáticamente al **modo nombre** (fallback, usado por DDInter).
- **STITCH stereo/flat-CID → PubChem CID**: `CIDs00012345`/`CIDm12345` → `12345`
  (se quita el prefijo `CIDs`/`CIDm` y los ceros a la izquierda). Lo hace
  `prepare_ddi_stitch.stitch_to_cid()` y `step04._norm_cid()` (misma lógica).

### Proteína por ENSP → gen (STITCH CPI)
STITCH identifica las proteínas con `9606.ENSP…`. Reutilizamos **el mismo crosswalk
que `scripts/load_string_network.py`**: el fichero `9606.protein.info.v12.0.txt.gz`
mapea `string_protein_id → preferred_name` (símbolo de gen), conservando el prefijo de
taxón, así el cruce con la columna `protein` de STITCH es directo.

Con el símbolo de gen, `step05_stitch_cpi.py` reengancha a un `:Target` **ya existente**
por `gene_name` — reutilizando su `drugbank_target_id` (= UniProt cuando lo tiene) sin
duplicar claves de `:Target`. La resolución a UniProt es, por tanto, **indirecta** (vía
el `:Target` existente): STITCH+STRING solo dan el símbolo de gen.

> **Crosswalk pendiente / límite conocido:** no hay un mapa directo ENSP→UniProt en el
> repo. Si un ENSP no está en el info de STRING, el gen queda vacío y la fila se
> descarta, salvo que se use `--create-missing`, que materializa un `:Target` sintético
> keyed por ENSP (`drugbank_target_id = 'STITCH-ENSP:<ensp>'`) para no perder la arista.

---

## 3. Orden de ejecución

```bash
cd backend && source venv/bin/activate

# — DDI (TWOSIDES, CC0) —
# 1) normaliza el volcado crudo (STITCH-CID → PubChem CID) al CSV de step04
python -m scripts.ingest.prepare_ddi_stitch \
    --twosides data/raw/twosides.tsv.gz \
    --out      data/ddi_twosides.csv
# 2) carga las DDI en Mongo (drug-interactions) + Neo4j (:INTERACTS_WITH)
python -m scripts.ingest.step04_ddi_open \
    --csv data/ddi_twosides.csv --source TWOSIDES     # modo CID autodetectado

# — DDI alternativa (DDInter, CC BY-NC-SA, por nombre) —
python -m scripts.ingest.prepare_ddi_stitch --source ddinter \
    --twosides data/raw/ddinter.csv --out data/ddinter.csv
python -m scripts.ingest.step04_ddi_open \
    --csv data/ddinter.csv --source DDInter           # modo nombre autodetectado

# — CPI (STITCH, CC BY 4.0) — DESPUÉS de step03_build_graph (necesita :Drug/:Target) —
python -m scripts.ingest.step05_stitch_cpi \
    --links data/raw/9606.protein_chemical.links.detailed.v5.0.tsv.gz \
    --info  /home/gabriel/string_data/9606.protein.info.v12.0.txt.gz \
    --min-score 700
```

Resumen de dependencias entre pasos:

- `prepare_ddi_stitch` → `step04_ddi_open` (produce/consume el CSV).
- `step04_ddi_open` requiere que **step01/step02** hayan poblado Mongo (índice de CID/nombre).
- `step05_stitch_cpi` requiere que **step03_build_graph** haya creado `:Drug` y `:Target`
  (y, para reenganchar por gen, el crosswalk `--info` de STRING).

---

## 4. Detalle de cada script

### `prepare_ddi_stitch.py` (fichero → fichero, no toca BD)
- `--twosides <ruta>` (crudo, admite `.gz`) · `--out <csv>` · `--source {twosides,ddinter}`.
- Autodetecta separador (TSV/CSV) y columnas; se pueden forzar con
  `--col-a/--col-b/--col-event/--col-severity`.
- **twosides** → emite `cid_a,cid_b,description,severity` (description = evento adverso o
  "DDI reportada por farmacovigilancia"; severity si hay columna).
- **ddinter** → emite `name_a,name_b,description,severity` (severity = nivel de interacción).
- Barra de progreso con `tqdm` si está instalado.

### `step04_ddi_open.py` (Mongo + Neo4j, idempotente, por lotes)
- `--csv <csv>` · `--source <etiqueta>` · `--mode {cid,name}` (autodetectado por columnas).
- Escribe el array Mongo `drug-interactions` (ambas direcciones) y las relaciones
  `(:Drug)-[:INTERACTS_WITH {description, severity, source}]-(:Drug)`.

### `step05_stitch_cpi.py` (Neo4j, idempotente, por lotes)
- `--links <ruta>` (STITCH detailed, admite `.gz`) · `--info <ruta>` (crosswalk ENSP→gen)
  · `--min-score 700` (parametrizable) · `--create-missing`.
- Filtra por `combined_score >= min-score` y por que el químico esté en el catálogo.
- Crea `(:Drug)-[:STITCH_TARGET {score, source:'STITCH', ensp}]->(:Target)` con `MERGE`
  (reengancha a `:Target` existentes por `gene_name`; con `--create-missing` materializa
  dianas sintéticas por ENSP).

---

## 5. Dependencias

Deps pip necesarias (para que el agente principal las consolide en
`requirements-ingest.txt`):

- `tqdm` — barras de progreso en `prepare_ddi_stitch` y `step05_stitch_cpi`
  (ya presente en `requirements-ingest.txt`; es la única extra que introducen estos scripts).

No hacen falta librerías nuevas más allá de las ya usadas por el pipeline
(`pymongo`, `neo4j`, Django/settings vía `_common.py`). El crosswalk ENSP→gen reutiliza
`scripts/load_string_network.py`, sin dependencias adicionales.
