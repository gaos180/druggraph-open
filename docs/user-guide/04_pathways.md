# 04 — Rutas Biológicas

## Acceder a la Sección

Desde el perfil de un fármaco, haz clic en la pestaña **Rutas** (o similar según el nombre en la UI).

> Esta sección realiza llamadas a APIs externas (STRING y KEGG) que pueden tardar **varios segundos**. Es normal ver un spinner mientras cargan.

---

## Sub-pestaña: Efecto Directo

Muestra las proteínas que el fármaco toca **directamente**, según los datos de DrugBank/Neo4j.

Para cada target se muestra:
- **Nombre** de la proteína
- **Tipo de relación** (inhibidor, sustrato, inductor, etc.)
- **Gen** asociado (ej. `PTGS1`, `PTGS2`)
- **UniProt ID** (enlace directo a la ficha UniProt)
- **Organismo** (generalmente *Humans*)

---

## Sub-pestaña: Efecto Indirecto (STRING)

Muestra proteínas que interactúan con los targets directos a través de la red PPI de STRING.

### Cómo interpretar la lista

| Campo | Significado |
|-------|-------------|
| **Proteína vecina** | Gen/proteína que interactúa con al menos un target directo |
| **Conectada a** | Qué targets directos la conectan con el fármaco |
| **Score** | Confianza de la interacción según STRING (0–1); ≥0.9 = muy alta |

### Colores del score

- Verde brillante (≥0.9): interacción muy confiable
- Verde amarillo (≥0.7): confiable
- Amarillo (≥0.5): moderado
- Naranja (<0.5): baja confianza

### Grafo PPI

Sobre la lista aparece un grafo Cytoscape que muestra:
- Nodos grandes = targets directos del fármaco
- Nodos pequeños = proteínas indirectas
- Aristas punteadas = interacciones PPI de STRING

### Imagen de red oficial

Al final de la sección hay un `<details>` expandible con la imagen de red que provee directamente STRING (sin consumir nuestra API).

---

## Sub-pestaña: Rutas KEGG

Muestra las vías biológicas de KEGG donde participan los targets del fármaco.

| Campo | Significado |
|-------|-------------|
| **Nombre de la ruta** | Ej. "Complement and coagulation cascades" |
| **ID KEGG** | Ej. `hsa04610` (enlace a la página de la ruta en KEGG) |
| **Targets** | Cuántos targets del fármaco participan en esta ruta (más = mayor impacto) |
| **Genes** | Badges con los nombres de los genes que caen en la ruta |

Haz clic en el nombre de la ruta para ir directamente a la visualización del mapa en `kegg.jp`.

---

## Parámetros de Query (API)

```
GET /api/drugs/<drugbank_id>/pathways/?include=string,kegg&species=9606&score=400
```

| Parámetro | Valores | Default | Descripción |
|-----------|---------|---------|-------------|
| `include` | `string`, `kegg`, `string,kegg` | `string,kegg` | Qué fuentes externas consultar |
| `species` | NCBI taxon ID | `9606` (Homo sapiens) | Especie para STRING y KEGG |
| `score` | 0–1000 | `400` (confianza media) | Umbral mínimo de confianza STRING |

---

## Ejemplo: Rutas del Ibuprofeno (DB01050)

```bash
curl -H "Authorization: Bearer <tu_token>" \
  "http://localhost:8000/api/drugs/DB01050/pathways/?include=string,kegg"
```

```json
{
  "drug": { "drugbank_id": "DB01050", "name": "Ibuprofen" },
  "direct_targets": [
    {
      "drugbank_target_id": "BE0000232",
      "name": "Prostaglandin G/H synthase 1",
      "gene_name": "PTGS1",
      "uniprot_id": "P23219",
      "rel_types": ["inhibitor"]
    }
  ],
  "indirect": {
    "direct_genes": ["PTGS1", "PTGS2"],
    "neighbors": [
      {
        "partner_protein": "ALOX5",
        "max_score": 0.731,
        "connected_to": ["PTGS2"],
        "connection_count": 1
      }
    ],
    "edges": [{ "source": "PTGS2", "target": "ALOX5", "score": 0.731 }]
  },
  "pathways": {
    "pathways": [
      {
        "pathway_id": "path:hsa00590",
        "name": "Arachidonic acid metabolism",
        "target_count": 2,
        "targets": ["Prostaglandin G/H synthase 1", "Prostaglandin G/H synthase 2"]
      }
    ],
    "unmapped_targets": [],
    "pathway_count": 1
  },
  "notes": []
}
```
