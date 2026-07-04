# 08 — Referencia de API REST

Base URL: `http://localhost:8000/api`

Todos los endpoints (excepto `/auth/register/` y `/auth/login/`) requieren:
```
Authorization: Bearer <jwt_token>
```

---

## Autenticación

### POST /api/auth/register/
```json
{ "email": "usuario@ejemplo.com", "name": "Mi Nombre", "password": "micontraseña123" }
```
**Respuesta 201**: `{ "token": "<jwt>", "user": { "id", "email", "name", "is_admin" } }`

### POST /api/auth/login/
```json
{ "email": "usuario@ejemplo.com", "password": "micontraseña123" }
```
**Respuesta 200**: `{ "token": "<jwt>", "user": { ... } }`

### GET /api/auth/me/
**Respuesta 200**: `{ "id": "...", "email": "...", "name": "...", "is_admin": false }`

---

## Fármacos

### GET /api/drugs/
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `search` | string | Búsqueda por nombre, SMILES, DrugBank ID, CAS |
| `drug_type` | string | `small molecule` \| `biotech` |
| `group` | string | `approved` \| `investigational` \| `experimental` \| `withdrawn` \| `nutraceutical` \| `illicit` \| `vet_approved` |
| `page` | int | Número de página (default: 1) |

**Respuesta 200**:
```json
{
  "page": 1, "per_page": 20, "has_next": true, "has_prev": false,
  "results": [ { "_id", "name", "type", "groups", "description", "drugbank-id" } ]
}
```

### GET /api/drugs/filters/
**Respuesta 200**: `{ "types": ["small molecule", "biotech"], "groups": ["approved", ...] }`

### GET /api/drugs/{drug_id}/
Devuelve el documento completo del fármaco (MongoDB). `drug_id` puede ser DrugBank ID (`DB01050`) o `_id` de Mongo.

### GET /drugs/{drug_id}/graph/
> Sin prefijo `/api/`. Devuelve el grafo Neo4j del fármaco.

```json
{
  "drug": { "drugbank_id", "name", "type", "groups" },
  "interactions": [ { "target_id", "target_name", "gene_name", "organism", "role" } ],
  "categories": [ { "name" } ],
  "drug_interactions": [ { "drugbank_id", "name", "description" } ],
  "stats": { "target_count", "category_count", "drug_interaction_count" }
}
```

---

## Rutas Biológicas

### GET /api/drugs/{drug_id}/pathways/
Combina targets Neo4j + vecinos STRING + rutas KEGG.

```json
{
  "drug_id": "DB01050",
  "direct_targets": [ { "gene_name", "uniprot_id", "name", "organism" } ],
  "string_neighbors": [ { "gene_name", "score" } ],
  "kegg_pathways": [ { "pathway_id", "name", "target_count", "targets": [...] } ],
  "notes": [...]
}
```

---

## Sandbox / Laboratorio Virtual

### POST /api/drugs/sandbox/analyze/
```json
{
  "smiles":     "CC(=O)Oc1ccccc1C(=O)O",
  "name":       "Mi compuesto",
  "target_ids": ["BE0000262", "BE0000017"],
  "persist":    false
}
```

**Respuesta 200**:
```json
{
  "sandbox": {
    "session_id", "sandbox_id", "name", "smiles",
    "properties": { "molecular_weight", "logp", "tpsa", "h_bond_donors",
                    "h_bond_acceptors", "rotatable_bonds", "aromatic_rings",
                    "num_heavy_atoms", "canonical_smiles" },
    "linked_targets": ["BE0000262"],
    "expires_at": 1718400000.0
  },
  "structural_similarity": [ { "drugbank_id", "name", "score" } ],
  "behavioral_similarity": [ { "drugbank_id", "name", "score", "shared_targets" } ],
  "combined":             [ { "drugbank_id", "name", "structural_score",
                              "behavioral_score", "combined_score", "shared_targets" } ],
  "method_used": "gds | jaccard | structural_only | none"
}
```

### GET /api/drugs/sandbox/targets/?search=EGFR
Autocompletado de targets (Neo4j) por nombre, gen, UniProt ID o DrugBank target ID. Mínimo 2 caracteres.

**Respuesta 200**:
```json
{
  "results": [
    { "drugbank_target_id": "BE0000262", "uniprot_id": "P35354",
      "gene_name": "PTGS2", "name": "Prostaglandin G/H synthase 2", "organism": "Humans" }
  ]
}
```

### POST /api/drugs/sandbox/swiss-targets/ — importar CSV
Recibe un CSV exportado desde [swisstargetprediction.ch](http://www.swisstargetprediction.ch), cruza con Neo4j y devuelve los targets enriquecidos con `drugbank_target_id`.

```bash
curl -X POST http://localhost:8000/api/drugs/sandbox/swiss-targets/ \
  -H "Authorization: Bearer <token>" \
  -F "file=@SwissTargetPrediction_ibuprofen.csv"
```

### GET /api/drugs/sandbox/swiss-targets/?smiles=...&organism=Homo+sapiens — API en tiempo real
Llama directamente a SwissTargetPrediction. Requiere conexión a internet en el servidor.

**Respuesta común (ambos modos)**:
```json
{
  "total":    100,
  "matched":  91,
  "organisms": ["Homo sapiens", "Mus musculus", "Rattus norvegicus"],
  "results": [
    {
      "uniprot_id":         "P35354",
      "gene_name":          "PTGS2",
      "target_name":        "Prostaglandin G/H synthase 2",
      "probability":        1.0,
      "target_class":       "Oxidoreductase",
      "chembl_id":          "CHEMBL230",
      "known_actives":      1065,
      "drugbank_target_id": "BE0000262",
      "db_name":            "Prostaglandin G/H synthase 2",
      "db_organism":        "Humans",
      "in_druggraph":       true
    }
  ]
}
```

**Errores**:
- `400` — SMILES ausente o CSV inválido
- `502` — SwissTargetPrediction no responde (usa modo CSV como alternativa)

### POST /api/drugs/sandbox/pathways/

Calcula rutas metabólicas KEGG, enriquecimiento funcional STRING y vecinos PPI para un conjunto de targets y/o fármacos.

**Body:**
```json
{
  "target_ids": ["BE0000262", "BE0000017"],
  "drug_ids":   ["DB01050", "DB00945"]
}
```

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `target_ids` | array | No* | Lista de `drugbank_target_id`. Máx. 30. |
| `drug_ids` | array | No* | Lista de `drugbank_id`. Los targets de estos fármacos se añaden al análisis. Máx. 10. |

\* Al menos uno de los dos campos debe estar presente y no vacío.

**Respuesta 200:**
```json
{
  "targets_used": [
    { "drugbank_target_id": "BE0000262", "gene_name": "PTGS2",
      "uniprot_id": "P35354", "name": "Prostaglandin G/H synthase 2" }
  ],
  "kegg": {
    "pathways": [
      { "pathway_id": "hsa00590", "name": "Arachidonic acid metabolism",
        "target_count": 8, "targets": ["PTGS1", "PTGS2"],
        "kegg_genes": ["hsa:5742"] }
    ],
    "unmapped_targets": [],
    "pathway_count": 86
  },
  "string_ppi": {
    "direct_genes": ["PTGS1", "PTGS2"],
    "neighbors": [
      { "partner_protein": "UGT1A6",
        "partner_string_id": "9606.ENSP...",
        "max_score": 0.994,
        "connected_to": ["PTGS2"],
        "connection_count": 1 }
    ],
    "edges": [...]
  },
  "go_process":    [ { "term": "GO:0006631", "description": "Fatty acid metabolic process",
                       "gene_count": 18, "genes": ["PTGS1"], "fdr": 1e-8 } ],
  "go_function":   [...],
  "go_component":  [...],
  "string_kegg":   [...],
  "reactome":      [...],
  "wikipathways":  [...],
  "ctd": {
    "available": true,
    "genes": [
      { "gene": "PTGS2", "gene_id": 5743,
        "interaction_count": 5123, "chemical_count": 980,
        "actions": [ { "action": "increases^expression", "count": 410 },
                     { "action": "decreases^activity", "count": 150 } ],
        "top_chemicals": [
          { "name": "Acetaminophen", "mesh_id": "D000082", "cas": "103-90-2",
            "count": 47, "in_druggraph": true, "drugbank_id": "DB00316" }
        ] }
    ],
    "summary": {
      "genes_with_data": 2,
      "total_interactions": 8456,
      "top_chemicals": [
        { "name": "Acetaminophen", "cas": "103-90-2", "drugbank_id": "DB00316",
          "in_druggraph": true, "gene_count": 2, "total_count": 91,
          "genes": ["PTGS1", "PTGS2"] }
      ]
    }
  },
  "notes":         []
}
```

> **CTD**: el campo `ctd` proviene de la colección MongoDB `ctd_gene_interactions`, cargada por el script `load_ctd_interactions.py` desde [ctdbase.org](https://ctdbase.org/downloads/). Es una consulta rápida (no llama a APIs externas). Si los datos no se han cargado, `ctd.available` es `false`. `summary.top_chemicals` lista los químicos que afectan al mayor número de genes diana (exploración de "qué otros compuestos afectan el mismo perfil").

**Errores:**
- `400` — Ningún target o drug_id proporcionado, o los IDs no se encuentran en Neo4j
- `502` — STRING o KEGG no responden

### POST /api/drugs/sandbox/propagation/

Propaga el efecto del compuesto por la red molecular **local** (no llama a APIs externas; ~1–5 s) y devuelve los genes alcanzados aguas abajo. Dos modos según `mode`.

**Body:**
```json
{ "genes": ["EGFR"], "mode": "directed", "seed_sign": -1, "max_hops": 3, "top_n": 40 }
{ "target_ids": ["BE0000262"], "drug_ids": ["DB01050"], "mode": "diffusion", "top_n": 40 }
```

| Campo | Descripción |
|-------|-------------|
| `genes` / `target_ids` / `drug_ids` | Semillas (símbolos directos, o se resuelven a genes diana) |
| `mode` | `"directed"` (KEGG `:REGULATES`, con signo) · `"diffusion"` (STRING, magnitud). Default `diffusion` |
| `seed_sign` | Solo directed: `-1` el fármaco inhibe sus dianas (default), `+1` las activa |
| `max_hops` | Solo directed: profundidad de la cascada (default 3) |

**Respuesta — modo directed:**
```json
{
  "available": true, "mode": "directed", "seed_sign": -1, "max_hops": 3,
  "seeds_used": ["EGFR"], "seeds_missing": [],
  "downstream": [
    { "gene": "MAPK1", "effect": -26.75, "magnitude": 26.75, "sign": -1, "is_target": true },
    { "gene": "SRC",   "effect": -24.37, "magnitude": 24.37, "sign": -1, "is_target": true }
  ]
}
```
`sign`: +1 = la cascada **activa** ese gen, −1 = lo **inhibe**.

**Respuesta — modo diffusion:**
```json
{
  "available": true, "mode": "diffusion", "damping": 0.6,
  "seeds_used": ["PTGS1", "PTGS2"], "seeds_missing": [],
  "downstream": [ { "gene": "PTGES", "score": 0.0104, "is_target": false } ]
}
```

**Errores:**
- `400` — No se proporcionaron genes/target_ids/drug_ids
- `503` — Plugin GDS no instalado, o la red del modo no está cargada (`available=false`; ver `reason`)

### DELETE /api/drugs/sandbox/{sandbox_id}/
Elimina un nodo `:SandboxDrug` antes de su TTL de 30 minutos.

---

## Dianas Moleculares

### GET /api/drugs/targets/

Lista paginada de proteínas diana registradas en Neo4j.

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `search` | string | Búsqueda por nombre, símbolo de gen o UniProt ID (mín. 2 caracteres) |
| `organism` | string | Filtro por organismo. Valor `Humans` para proteínas humanas |
| `page` | int | Número de página (default: 1) |

> **Nota**: Los targets humanos en Neo4j tienen `organism = 'Humans'` (no 'Homo sapiens'). Usa este valor exacto al filtrar.

**Respuesta 200:**
```json
{
  "page": 1, "per_page": 20, "has_next": true, "has_prev": false,
  "results": [
    {
      "drugbank_target_id": "BE0000262",
      "name": "Prostaglandin G/H synthase 2",
      "gene_name": "PTGS2",
      "uniprot_id": "P35354",
      "organism": "Humans",
      "drug_count": 45
    }
  ]
}
```

### GET /api/drugs/targets/{target_id}/

Perfil completo de una diana. `target_id` es el `drugbank_target_id` (ej. `BE0000262`).

**Respuesta 200:**
```json
{
  "drugbank_target_id": "BE0000262",
  "name": "Prostaglandin G/H synthase 2",
  "gene_name": "PTGS2",
  "uniprot_id": "P35354",
  "organism": "Humans",
  "sequence": "MLARALLLCAVLALSHTANPCCSHPCQNRGVCMSVGFDQYKCDCTRTGFYGENCTTPEFLTRIKLFLKPTPNTVHYILTHFKGFWNVVNNIPFLRNAIMSYVLTSRSHLIDSPPTYNADYGYKSWEAFSNLSYYTRALPPVPDDCPTPLGVKGKKQLPDSNEIVEKLLLRRKFIPDPQGSNMMFAFFAQHFTHQFFKTDHKRGPAFTNGLGHGVDSLTLGNLPRLKELDSYEDTKIIFNSFESVLLFLTVKHFTLKLLNLDHNQRNIFDLREAGDEREQKLISEEDLNHYERQIKPGDVFSFLRNLSRDLFLANIINSYVLTSRSHLIDSPPTYNADYG...",
  "drugs": [
    { "drugbank_id": "DB01050", "name": "Ibuprofen", "rel_type": "INHIBITS" }
  ],
  "related_targets": [
    { "drugbank_target_id": "BE0000263", "gene_name": "PTGS1",
      "name": "Prostaglandin G/H synthase 1", "shared_drugs": 12 }
  ],
  "kegg_pathways": [
    { "pathway_id": "hsa00590", "name": "Arachidonic acid metabolism" }
  ]
}
```

**Errores:**
- `404` — `target_id` no encontrado en Neo4j

---

## BLAST

### POST /api/drugs/blast/search/
```json
{
  "sequence": "MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAK...",
  "evalue":   0.001,
  "max_hits": 10
}
```

**Respuesta 200**:
```json
{
  "hits": [
    { "target_id": "BE0000262", "target_name": "...", "gene_name": "PTGS2",
      "identity": 98.5, "evalue": 1.2e-120, "score": 850,
      "drugs": [ { "drugbank_id", "name" } ] }
  ],
  "query_length": 120,
  "database_hits": 1
}
```

---

## GDS — Análisis de Red

> Requiere el plugin **Neo4j GDS**. Sin él los endpoints devuelven `503`.

### GET /api/drugs/gds/centrality/
| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `top_n` | 20 | Nodos más centrales a devolver |
| `algorithm` | `pagerank` | `pagerank` \| `betweenness` \| `degree` |

### GET /api/drugs/gds/communities/
Detección de comunidades Louvain sobre el grafo de interacciones.

### GET /api/drugs/gds/predict/{drug_id}/
Predicción de nuevos enlaces para un fármaco concreto (Adamic-Adar).

### GET /api/drugs/gds/predict-global/
Predicción global de nuevas interacciones fármaco-diana en toda la red.

---

## Herramientas Analíticas

> Todos los endpoints del módulo de herramientas requieren autenticación JWT.  
> Base path: `/api/tools/`

### GET /api/tools/ddi/

Verifica interacciones fármaco-fármaco registradas en Neo4j (arista `:INTERACTS_WITH`).

**Modos de uso:**

| Modo | Parámetros | Descripción |
|------|-----------|-------------|
| Par | `?drug_a=DB01050&drug_b=DB00945` | Comprueba si existe DDI entre los dos fármacos |
| Lista | `?drug_a=DB01050` | Retorna todas las DDIs del fármaco A |

**Respuesta 200 — modo par:**
```json
{
  "mode": "pair",
  "drug_a": { "drugbank_id": "DB01050", "name": "Ibuprofen" },
  "drug_b": { "drugbank_id": "DB00945", "name": "Aspirin" },
  "has_interaction": true,
  "description": "Ibuprofen may decrease the cardioprotective effect of Aspirin..."
}
```

**Respuesta 200 — modo lista:**
```json
{
  "mode": "single",
  "drug": { "drugbank_id": "DB01050", "name": "Ibuprofen" },
  "interaction_count": 245,
  "interactions": [
    { "drugbank_id": "DB00945", "name": "Aspirin", "description": "..." }
  ]
}
```

**Errores:**
- `400` — parámetro `drug_a` ausente
- `404` — DrugBank ID no encontrado en Neo4j

```bash
# Ejemplo: comprobar DDI entre Ibuprofeno y Aspirina
curl "http://localhost:8000/api/tools/ddi/?drug_a=DB01050&drug_b=DB00945" \
  -H "Authorization: Bearer <token>"

# Ejemplo: listar todas las DDIs del Ibuprofeno
curl "http://localhost:8000/api/tools/ddi/?drug_a=DB01050" \
  -H "Authorization: Bearer <token>"
```

---

### POST /api/tools/deg-analysis/

Cruce de genes DEG con targets del fármaco + enriquecimiento GO/KEGG.

**Body:**
```json
{
  "drug_id":              "DB00945",
  "genes": [
    { "symbol": "PTGS1", "log2fc": -1.8, "pvalue": 0.001, "padj": 0.005 },
    { "symbol": "TP53",  "log2fc":  1.1, "pvalue": 0.04,  "padj": 0.09  }
  ],
  "fc_threshold":        1.0,
  "pval_threshold":      0.05,
  "use_fdr":             false,
  "organism":            "hsapiens",
  "go_sources":          ["GO:BP", "GO:MF", "GO:CC", "KEGG"],
  "significance_method": "fdr_bh"
}
```

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `drug_id` | string | Sí | DrugBank ID del fármaco (ej. `DB00945`) |
| `genes` | array | Sí | Lista de genes. Solo `symbol` es obligatorio; `log2fc`, `pvalue`, `padj` son opcionales |
| `fc_threshold` | float | No | Umbral absoluto de log₂FC para considerar un gen significativo (default: 1.0) |
| `pval_threshold` | float | No | Umbral de p-valor / FDR (default: 0.05) |
| `use_fdr` | bool | No | Si `true`, usa `padj` en lugar de `pvalue` para el filtro de significancia (default: false) |
| `organism` | string | No | Código g:Profiler del organismo (default: `hsapiens`) |
| `go_sources` | array | No | Fuentes GO a consultar (default: GO:BP, GO:MF, GO:CC, KEGG) |
| `significance_method` | string | No | Método de corrección múltiple: `fdr_bh`, `bonferroni`, `g_SCS`, `fdr_by` (default: `fdr_bh`) |

**Respuesta 200:**
```json
{
  "drug":   { "name": "Acetylsalicylic acid", "drugbank_id": "DB00945" },
  "stats": {
    "total_input": 10, "significant": 4, "up": 2, "down": 2,
    "drug_targets": 8, "overlap": 2, "overlap_up": 1, "overlap_down": 1,
    "has_quantitative": true
  },
  "genes": [
    {
      "symbol": "PTGS1", "log2fc": -1.8, "pvalue": 0.001, "padj": 0.005,
      "sig_value": 0.001, "is_sig": true, "direction": "down",
      "is_target": true, "target_id": "BE0000263",
      "gene_name": "PTGS1", "uniprot_id": "P23219", "rel_type": "INHIBITS"
    }
  ],
  "drug_targets": [ { "target_id", "name", "gene_name", "uniprot_id", "rel_type" } ],
  "overlap":      [ { "symbol", "log2fc", "pvalue", "padj", "direction",
                      "target_id", "gene_name", "uniprot_id", "rel_type" } ],
  "go_enrichment": [
    {
      "source": "GO:BP", "term_id": "GO:0006954", "term_name": "inflammatory response",
      "p_value": 1.2e-5, "fdr": 3.4e-4,
      "intersection_size": 2, "term_size": 480, "query_size": 4,
      "genes": ["PTGS1", "PTGS2"]
    }
  ],
  "notes": []
}
```

**Errores:**
- `400` — `drug_id` ausente, lista de genes vacía, o `drug_id` no encontrado en la base de datos
- `502` — g:Profiler no responde (el cruce se devuelve igual; `go_enrichment` queda vacío con nota)

---

### GET /api/tools/repurposing/{drug_id}/

Candidatos a reposicionamiento por similitud de perfil de dianas (Jaccard).

| Parámetro URL | Descripción |
|---------------|-------------|
| `drug_id` | DrugBank ID del fármaco de referencia |

**Respuesta 200:**
```json
{
  "drug":    { "name": "Acetylsalicylic acid", "drugbank_id": "DB00945" },
  "targets": [ { "target_id", "name", "gene_name", "uniprot_id", "rel_type" } ],
  "candidates": [
    {
      "drugbank_id":  "DB00788",
      "name":         "Naproxen",
      "jaccard":      0.421,
      "shared_count": 8,
      "shared_genes": ["PTGS1", "PTGS2", "ALOX5"],
      "targets_a":    12,
      "targets_b":    15
    }
  ],
  "go_profile": [ { "source", "term_id", "term_name", "p_value", "fdr",
                    "intersection_size", "term_size", "query_size", "genes" } ]
}
```

Los candidatos se devuelven ordenados por Jaccard descendente (máximo 50). Solo se incluyen fármacos con Jaccard > 0.05.

**Errores:**
- `404` — DrugBank ID no encontrado o sin targets en Neo4j

---

### GET /api/tools/toxicity/{drug_id}/

Evaluación de riesgo de toxicidad: anti-targets directos, CYPs, off-targets predichos y cluster estructural.

| Parámetro URL | Descripción |
|---------------|-------------|
| `drug_id` | DrugBank ID del fármaco a evaluar |

**Respuesta 200:**
```json
{
  "drug":       { "name": "Acetylsalicylic acid", "drugbank_id": "DB00945" },
  "risk_score": 4,
  "risk_level": "moderado",
  "alert_counts": { "high": 0, "medium": 2, "low": 1 },
  "alerts": [
    {
      "level":       "medium",
      "icon":        "⚠️",
      "category":    "Gastrotoxicidad",
      "gene_name":   "PTGS1",
      "target_name": "Prostaglandin G/H synthase 1",
      "uniprot_id":  "P23219",
      "rel_type":    "INHIBITS",
      "message":     "Inhibición de PTGS1 asociada a daño de mucosa gástrica y úlcera péptica."
    }
  ],
  "cyp_interactions": [
    { "gene": "CYP2C9", "rel_type": "SUBSTRATE", "level": "medium",
      "note": "Sustrato de CYP2C9; inhibidores de esta enzima pueden elevar sus niveles plasmáticos." }
  ],
  "predicted_offtargets": [
    {
      "target_id": "BE0000789", "target_name": "...", "gene_name": "ALOX5",
      "uniprot_id": "P09917", "organism": "Humans",
      "score": 12.4, "shared_via": 5,
      "is_antitarget": false, "antitarget_level": null,
      "antitarget_category": null, "antitarget_message": null
    }
  ],
  "structural_cluster": [
    { "drugbank_id": "DB00788", "name": "Naproxen", "jaccard": 0.34, "shared_count": 8 }
  ],
  "target_count": 12
}
```

**Valores de `risk_level`:**

| Valor | Score |
|-------|-------|
| `sin_datos` | 0 (sin targets) |
| `bajo` | 1–2 |
| `moderado` | 3–5 |
| `alto` | 6–8 |
| `muy_alto` | 9–10 |

**Errores:**
- `404` — DrugBank ID no encontrado en Neo4j

---

## Códigos de error comunes

| Código | Descripción |
|--------|-------------|
| `400` | Parámetros incorrectos o faltantes |
| `401` | Token JWT ausente o inválido |
| `404` | Recurso no encontrado |
| `500` | Error interno del servidor |
| `502` | Error llamando a API externa (SwissTargetPrediction, STRING, KEGG) |
| `503` | Servicio no disponible (Neo4j GDS no instalado, RDKit ausente) |
