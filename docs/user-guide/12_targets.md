# 12 — Dianas Moleculares

**Ruta:** `/targets`

La página de Dianas Moleculares permite explorar el catálogo completo de proteínas diana registradas en DrugGraph. Para cada diana se muestra su perfil de datos UniProt, localización subcelular, los fármacos que la tienen como target y su red de dianas relacionadas.

Accede desde el Dashboard → **Dianas** o navega directamente a `/targets`.

---

## Buscador de dianas

El buscador acepta texto libre y devuelve resultados en tiempo real (a partir de 2 caracteres):

| Campo de búsqueda | Ejemplos |
|------------------|---------|
| Nombre de proteína | `Prostaglandin`, `Kinase`, `Receptor` |
| Símbolo de gen (HGNC) | `PTGS2`, `EGFR`, `TP53` |
| UniProt accession | `P35354`, `P00533` |

### Filtro "Solo humanos"

Activa el switch **Solo humanos** para mostrar únicamente las dianas cuyo campo `organism` sea `Humans` en Neo4j.

> **Nota técnica**: Los targets humanos en Neo4j tienen el valor `organism = 'Humans'` (importado desde DrugBank). No se usa `'Homo sapiens'`. Si observas que faltan algunos targets al filtrar, verifica que el campo `organism` del nodo tenga exactamente ese valor.

### Paginación

Los resultados se muestran de 20 en 20. Usa los botones **Anterior** / **Siguiente** para navegar. La barra de búsqueda y el filtro de organismo se mantienen al cambiar de página.

---

## Tarjeta de diana en el listado

Cada diana aparece como una tarjeta con:

| Campo | Descripción |
|-------|-------------|
| Nombre | Nombre completo de la proteína |
| Gen | Símbolo HGNC (ej. `PTGS2`) |
| Organismo | Especie (ej. `Humans`) |
| UniProt | Accession con enlace a uniprot.org |
| Fármacos | Número de fármacos en DrugGraph que tienen esta diana registrada |

Haz clic en la tarjeta para abrir el perfil completo de la diana.

---

## Perfil de diana (`/targets/:id`)

El perfil detallado muestra toda la información disponible agrupada en secciones.

### Datos generales

| Campo | Descripción |
|-------|-------------|
| Nombre completo | Nombre oficial de la proteína |
| Símbolo de gen | Nomenclatura HGNC |
| Organismo | Especie del target |
| UniProt ID | Identificador único; enlace externo a UniProt |
| Secuencia | Secuencia de aminoácidos completa (colapsada por defecto) |

### Localización subcelular (SwissBioPics)

Imagen interactiva de la célula que resalta los compartimentos donde se localiza la proteína (ej. membrana plasmática, núcleo, mitocondria). Los datos provienen de UniProt/SwissBioPics.

Si la imagen no puede cargarse (fallo de red o proteína sin datos de localización), se muestra un mensaje alternativo sin interrumpir el resto de la página.

### Fármacos que actúan sobre esta diana

Tabla de los fármacos registrados en Neo4j que tienen esta proteína como target:

| Columna | Descripción |
|---------|-------------|
| DrugBank ID | Identificador (ej. `DB01050`) con enlace al perfil del fármaco |
| Nombre | Nombre del fármaco |
| Tipo de relación | `INHIBITS`, `ACTIVATES`, `SUBSTRATE`, `BINDER`, `OTHER` |

### Red de dianas relacionadas

Grafo Cytoscape que muestra las dianas que comparten fármacos con esta diana. Las aristas representan fármacos en común; el grosor indica cuántos fármacos comparten.

Interacciones disponibles en el grafo:

| Acción | Efecto |
|--------|--------|
| Clic en nodo | Muestra nombre y número de fármacos compartidos |
| Doble clic en nodo | Navega al perfil de esa diana |
| Rueda del ratón | Zoom in / out |
| Arrastrar | Mover el lienzo |
| Botón ⬇ PNG | Exporta el grafo a imagen de alta resolución (×2) |

### Rutas biológicas (KEGG)

Lista de rutas metabólicas de KEGG en las que participa esta diana, obtenidas mediante su UniProt ID → KEGG gene ID → pathways. Columnas:

| Campo | Descripción |
|-------|-------------|
| ID de ruta | Identificador KEGG (ej. `hsa00590`) |
| Nombre | Nombre de la ruta |
| Enlace | Acceso directo al mapa KEGG |

---

## Ejemplo de búsqueda y exploración

1. Navega a `/targets`.
2. Escribe `PTGS` en el buscador. Aparecerán `PTGS1` (COX-1) y `PTGS2` (COX-2).
3. Activa **Solo humanos** si quieres excluir isoformas de otras especies.
4. Haz clic en la tarjeta de `PTGS2`.
5. En el perfil, observa que está localizada en la membrana del retículo endoplasmático (SwissBioPics).
6. En **Fármacos**, verás Ibuprofeno, Naproxeno, Celecoxib y decenas más con relación `INHIBITS`.
7. En **Red de dianas**, `PTGS1` aparece como diana más relacionada (mayor número de fármacos compartidos).
8. En **Rutas KEGG**, la ruta `hsa00590 — Arachidonic acid metabolism` enlaza al mapa completo.

---

## Cómo usar la API directamente

```bash
# Buscar dianas que contengan "PTGS" en nombre o gen, solo humanos
curl "http://localhost:8000/api/drugs/targets/?search=PTGS&organism=Humans" \
  -H "Authorization: Bearer <token>"

# Obtener el perfil completo de PTGS2
curl "http://localhost:8000/api/drugs/targets/BE0000262/" \
  -H "Authorization: Bearer <token>"
```

Consulta la [Referencia de API REST](08_api_reference.md) para la especificación completa de los endpoints de dianas.

---

## Limitaciones

- La imagen de localización subcelular (SwissBioPics) requiere conexión a internet en el cliente; no se cachea en el servidor.
- Las rutas KEGG se obtienen al cargar el perfil; si KEGG no responde, la sección muestra mensaje de error y el resto del perfil sigue disponible.
- El grafo de dianas relacionadas solo muestra las 50 dianas más conectadas para evitar grafos ilegibles.
- Las dianas sin `uniprot_id` en Neo4j no tendrán datos de localización subcelular ni rutas KEGG.
