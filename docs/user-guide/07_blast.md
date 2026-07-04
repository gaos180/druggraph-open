# 07 — Búsqueda BLAST

BLAST (Basic Local Alignment Search Tool) permite buscar **dianas moleculares** en la base de datos de DrugGraph usando la **secuencia de aminoácidos** de una proteína de interés.

Accede desde el Dashboard → **Búsqueda BLAST** o navega a `/blast`.

---

## Requisitos Previos (Administrador)

Antes de usar BLAST, un administrador debe:

1. Instalar NCBI BLAST+ en el sistema:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install ncbi-blast+
   
   # macOS (Homebrew)
   brew install blast
   ```

2. Construir el índice BLAST:
   ```bash
   cd backend
   python build_blast_db.py
   ```
   Esto genera los archivos de índice en la ruta configurada por `BLAST_DB_PATH`.

3. Configurar las variables de entorno:
   ```bash
   export BLAST_DB_PATH=/ruta/al/indice/blast/druggraph_targets
   export BLAST_MAP_PATH=/ruta/al/mapeo/drugbank_map.json
   ```

> Si BLAST no está configurado, el endpoint retorna HTTP 503 y la UI muestra un mensaje de error informativo.

---

## Ingresar una Secuencia

En el área de texto, pega la secuencia proteica en uno de estos formatos:

### Formato FASTA (recomendado)

```fasta
>Mi proteína de interés
MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWLFTHPSWLKSVEGASNAGGHSSGQHITFLSESPGQRSASAGSSPGQHITFLSESPGQR
```

### Secuencia simple (sin cabecera)

```
MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSG
AEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALR
```

---

## Parámetros de Búsqueda

| Parámetro | Descripción | Valor por defecto |
|-----------|-------------|------------------|
| **Organismo** | Filtrar resultados por especie de la diana | Todos (sin filtro) |
| **E-value** | Umbral de significancia estadística. Valores más bajos = matches más estrictos | `0.001` |
| **Max resultados** | Número máximo de hits a retornar | `10` |

---

## Interpretar los Resultados

Cada tarjeta de resultado (Hit Card) muestra:

| Campo | Descripción |
|-------|-------------|
| **Target** | Nombre de la diana encontrada en DrugGraph |
| **Fármaco** | DrugBank ID y nombre del fármaco que interactúa con esa diana |
| **% Identidad** | Porcentaje de aminoácidos idénticos entre la query y el target |
| **Cobertura** | Porcentaje de la secuencia query cubierta por el alignment |
| **E-value** | Valor esperado estadístico (menor = más significativo) |
| **Bit score** | Score de alineamiento (mayor = mejor match) |

Haz clic en cualquier hit para ir al perfil del fármaco correspondiente.

---

## Ejemplo: Buscar dianas similares a COX-2

```bash
# Buscar targets similares a la Ciclooxigenasa-2 humana (PTGS2)
curl -X POST http://localhost:8000/api/drugs/blast/search/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "sequence": "MLARALLLCAVLALSHTANPCCSHPCQNRGVCMSVGFDQYKCDCTRTGFYGENCTTPEFLTRIKLFLKPTPNTVHYILTHFKGFWNVVNNIPFLRNAIMSYVLTSRSHLIDSPPTYNADYGYKSWEAFSNLSYYTRALPPVPDDCPTPLGVKGKKQLPDSNEIVEKLLLRRKFIPDPQGSNMMFAFFAQHFTHQFFKTSGKMGYKGDFQARFYDILFNTLQQKGPDSIIKAIKNKLAEMKPFIDEKRPKRYFNEQSQDAAFYQNQMKNYGMDVLSQNMQTAQVNELLFQAMKLQPYPMSLEQLEFQMRQLQQFEQAKQLQTQIAQSGSPVKEQLLDGLQQLEKQVEHLQAQLENLERQMAQKRLEEYQKTLHDRVEQLKEHLQDLANQIKDPSTPTASPQDTHKSTSPASQPSTPKPRSESQESPSTSPSPGQM",
    "organism": "Humans",
    "max_results": 5
  }'
```

```json
{
  "hits": [
    {
      "target_name": "Prostaglandin G/H synthase 2",
      "target_id": "BE0000048",
      "drug_name": "Ibuprofen",
      "drugbank_id": "DB01050",
      "identity": 99.8,
      "coverage": 100.0,
      "evalue": "0.0",
      "bit_score": 1540
    },
    {
      "target_name": "Prostaglandin G/H synthase 2",
      "target_id": "BE0000048",
      "drug_name": "Celecoxib",
      "drugbank_id": "DB00482",
      "identity": 99.8,
      "coverage": 100.0,
      "evalue": "0.0",
      "bit_score": 1540
    }
  ],
  "query_length": 604,
  "database_targets": 892
}
```

---

## Casos de Uso Típicos

1. **Identificar fármacos existentes para una diana nueva**: tienes la secuencia de una proteína implicada en una enfermedad y quieres saber qué fármacos ya la tienen como target.

2. **Drug repurposing**: la proteína mutante de una cepa resistente tiene alta homología con una diana de un fármaco aprobado.

3. **Validación cruzada**: confirmar que el target de tu compuesto en el sandbox tiene matches BLAST en la base de datos de fármacos reales.
