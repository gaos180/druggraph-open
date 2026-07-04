# 03 — Red de Interacción

## Acceder al Grafo

Desde el perfil de cualquier fármaco, haz clic en la pestaña **Red**.

---

## Tabla de Interacciones (Vista por defecto)

La vista de tabla muestra todas las interacciones del fármaco con otros nodos del grafo:

| Columna | Descripción |
|---------|-------------|
| **Tipo de nodo** | `Target`, `Category`, `Drug` (interacción Drug-Drug) |
| **Nombre** | Nombre del nodo relacionado |
| **Tipo de relación** | `TARGETS`, `BELONGS_TO`, `INTERACTS_WITH`, etc. |
| **ID** | DrugBank ID o identificador del target |

---

## Vista Cytoscape (Grafo Interactivo)

Haz clic en el botón **Ver grafo** (o el toggle de visualización) para abrir la vista Cytoscape.

### Controles de navegación

| Acción | Cómo hacerla |
|--------|-------------|
| Zoom in/out | Rueda del ratón |
| Pan (desplazar) | Clic + arrastrar en el fondo |
| Seleccionar nodo | Clic sobre el nodo |
| Mover nodo | Clic + arrastrar sobre el nodo |
| Reset zoom | Botón "Ajustar a pantalla" (si disponible) |

### Tipos de nodos y colores

| Color | Tipo |
|-------|------|
| Azul oscuro | Fármaco principal |
| Verde | Target (proteína diana) |
| Naranja | Categoría farmacológica |
| Rojo | Fármaco relacionado (Drug-Drug) |

### Cambiar el layout

Usa el selector de layout (si está disponible) para cambiar el algoritmo de disposición:

- **cose**: layout de fuerzas, bueno para grafos generales (por defecto)
- **circle**: disposición circular
- **grid**: cuadrícula regular
- **breadthfirst**: árbol desde el fármaco central

### Exportar el grafo

Haz clic derecho en el canvas de Cytoscape para acceder a las opciones de exportación (PNG, JPG), si tu navegador lo permite. Alternativamente, usa la función de captura de pantalla del sistema operativo.

---

## Endpoint API

```
GET /api/drugs/<drugbank_id>/graph/
```

**Respuesta**:
```json
{
  "nodes": [
    { "id": "DB01050", "label": "Ibuprofen", "type": "drug" },
    { "id": "T001",    "label": "COX-1",     "type": "target" }
  ],
  "edges": [
    { "source": "DB01050", "target": "T001", "type": "TARGETS" }
  ]
}
```

---

## Ejemplo: Red de Ibuprofeno

1. Ve a `/drugs/DB01050`.
2. Haz clic en la pestaña **Red**.
3. La tabla muestra los 2 targets principales de COX (ciclooxigenasa).
4. Haz clic en **Ver grafo** para ver el grafo interactivo con todos los nodos y aristas.
5. Los nodos verdes son los targets; los naranjas son las categorías (ej. "Nonsteroidal Anti-Inflammatory Agents").
