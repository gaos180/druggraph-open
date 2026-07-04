# 13 — DDI Checker (Verificador de Interacciones Fármaco-Fármaco)

**Ruta:** `/tools/ddi`

El DDI Checker permite consultar las interacciones fármaco-fármaco (DDI) registradas en la base de datos Neo4j de DrugGraph. Las DDIs proceden originalmente de DrugBank y están representadas como aristas `:INTERACTS_WITH` entre nodos `:Drug`.

Accede desde **Herramientas → DDI Checker** en el sidebar de ToolsPage.

---

## ¿Cuándo usarlo?

- Quieres saber si dos fármacos concretos tienen una interacción documentada.
- Necesitas listar todas las DDIs conocidas de un fármaco determinado para evaluar su perfil de seguridad.
- Estás revisando un plan de tratamiento con varios fármacos y deseas detectar posibles incompatibilidades.

---

## Modos de uso

### Modo par (A ↔ B)

Comprueba si existe interacción entre dos fármacos específicos.

1. En el campo **Fármaco A**, introduce el DrugBank ID o el nombre del fármaco.
2. En el campo **Fármaco B**, introduce el segundo fármaco.
3. Haz clic en **Verificar**.

**Resultado:**

| Escenario | Visualización |
|-----------|--------------|
| Interacción encontrada | Panel verde con descripción de la interacción |
| Sin interacción registrada | Panel gris "No se encontraron interacciones entre estos fármacos" |
| Fármaco no encontrado | Mensaje de error con el ID que no pudo resolverse |

La descripción de la DDI es el texto literal de DrugBank, en inglés. Incluye el mecanismo y la recomendación clínica.

### Modo lista (todas las DDIs de un fármaco)

Lista todas las interacciones conocidas de un fármaco.

1. Introduce solo el **Fármaco A**.
2. Deja el campo **Fármaco B** vacío.
3. Haz clic en **Verificar**.

La respuesta incluye:

- Número total de interacciones encontradas (`interaction_count`)
- Tabla paginada con todos los fármacos con los que interactúa, ordenados alfabéticamente por nombre
- Descripción de cada interacción

> El tiempo de respuesta en modo lista es mayor cuanto más DDIs tenga el fármaco. Para compuestos con > 200 DDIs (frecuente en AINEs y anticoagulantes) puede tardar 2–3 segundos.

---

## Tabla de resultados (modo lista)

| Columna | Descripción |
|---------|-------------|
| DrugBank ID | Identificador del fármaco con el que interactúa (enlace al perfil) |
| Nombre | Nombre del fármaco |
| Descripción | Texto DrugBank de la interacción |

---

## Exportar resultados

El botón **Exportar CSV** descarga la tabla de resultados en formato CSV con las columnas:

```
drugbank_id_a, name_a, drugbank_id_b, name_b, description
```

En modo par, el CSV contendrá una sola fila (si hay interacción) o estará vacío (si no hay interacción).

---

## Ejemplos

### Ejemplo 1: Ibuprofeno + Aspirina

```bash
curl "http://localhost:8000/api/tools/ddi/?drug_a=DB01050&drug_b=DB00945" \
  -H "Authorization: Bearer <token>"
```

Resultado esperado:
```json
{
  "mode": "pair",
  "drug_a": { "drugbank_id": "DB01050", "name": "Ibuprofen" },
  "drug_b": { "drugbank_id": "DB00945", "name": "Aspirin" },
  "has_interaction": true,
  "description": "Ibuprofen may decrease the cardioprotective effect of Aspirin..."
}
```

### Ejemplo 2: Todas las DDIs del Ibuprofeno

```bash
curl "http://localhost:8000/api/tools/ddi/?drug_a=DB01050" \
  -H "Authorization: Bearer <token>"
```

Resultado esperado (fragmento):
```json
{
  "mode": "single",
  "drug": { "drugbank_id": "DB01050", "name": "Ibuprofen" },
  "interaction_count": 245,
  "interactions": [
    { "drugbank_id": "DB00945", "name": "Aspirin", "description": "..." },
    { "drugbank_id": "DB01050", "name": "...", "description": "..." }
  ]
}
```

---

## Limitaciones

- Las DDIs mostradas son únicamente las **registradas en DrugBank** e importadas a Neo4j. Una ausencia de resultado no garantiza que no exista interacción clínica.
- Las descripciones están en **inglés** (idioma original de DrugBank).
- La herramienta no evalúa la **gravedad clínica** de la interacción; esa valoración requiere consulta especializada.
- Las DDIs en Neo4j son **no dirigidas** por modelo; la consulta busca la arista en ambas direcciones (`A→B` y `B→A`).
- Solo los fármacos con `drugbank_id` registrado en Neo4j pueden consultarse. Los compuestos del sandbox no tienen DDIs.
