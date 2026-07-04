# 05 — Análisis de Red Global

Accede desde el Dashboard → **Análisis de Red** o navega a `/network`.

> Esta sección requiere que el **plugin GDS de Neo4j** esté instalado y activo.  
> Si no está disponible, verás el mensaje "Neo4j GDS no disponible" y los paneles estarán deshabilitados.

---

## Panel: Centralidad

Calcula la importancia de cada fármaco en la red global usando dos métricas:

| Métrica | Descripción |
|---------|-------------|
| **PageRank** | Mide la importancia de un fármaco basándose en cuántos otros nodos importantes apuntan a él |
| **Betweenness** | Mide cuántos caminos mínimos entre pares de nodos pasan por ese fármaco (fármacos "puente") |

### Cómo usar el panel de centralidad

1. Haz clic en **Calcular centralidad**.
2. Espera 5–30 segundos (depende del tamaño de la red).
3. Aparece una tabla con los top-N fármacos ordenados por score.
4. Haz clic en cualquier fármaco de la tabla para ir directamente a su perfil.

> **Consejo**: los fármacos con alto PageRank suelen ser compuestos con muchas dianas (poli-farmacológicos). Los de alto Betweenness son "puentes" entre grupos de dianas diferentes.

---

## Panel: Comunidades (Louvain)

Detecta grupos (comunidades) de fármacos que comparten dianas o interaccionan entre sí.

1. Haz clic en **Detectar comunidades**.
2. El algoritmo Louvain agrupa los nodos maximizando la modularidad.
3. El resultado es un grafo Cytoscape donde cada color representa una comunidad diferente.
4. La leyenda muestra el número de comunidades encontradas y el tamaño de cada una.

### Interpretación

- Los fármacos del mismo color tienden a actuar sobre los mismos targets o vías biológicas.
- Una comunidad muy grande puede indicar un mecanismo de acción compartido (ej. todos los AINEs cerca de COX).

---

## Panel: Predicción de Enlaces

Predice posibles interacciones Drug-Drug o Drug-Target que no están registradas en los datos actuales.

### Predicción para un fármaco específico

1. Escribe el DrugBank ID en el campo de búsqueda (ej. `DB01050`).
2. Haz clic en **Predecir**.
3. El sistema calcula similitud de vecindad (Common Neighbors, Adamic-Adar) con todos los nodos del grafo.
4. Aparece una lista de posibles interacciones, ordenadas por score de predicción.

### Predicción global (top-N)

1. En el panel global, haz clic en **Calcular predicciones globales**.
2. Se muestran las N interacciones con mayor probabilidad en toda la red.
3. Útil para identificar hipótesis de drug repurposing (reutilización de fármacos).

---

## Endpoint API

```
GET /api/drugs/gds/centrality/
GET /api/drugs/gds/communities/
GET /api/drugs/gds/predict/<drug_id>/
GET /api/drugs/gds/predict-global/
```

**Ejemplo — Centralidad**:
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/drugs/gds/centrality/
```

```json
{
  "nodes": [
    {
      "drugbank_id": "DB01050",
      "name": "Ibuprofen",
      "pagerank": 0.0023,
      "betweenness": 14.5
    }
  ]
}
```

**Respuesta cuando GDS no está disponible**:
```json
HTTP 503
{
  "error": "Neo4j GDS no disponible. Instala el plugin graph-data-science."
}
```
