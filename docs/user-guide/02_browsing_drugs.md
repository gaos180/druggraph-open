# 02 — Explorar Fármacos

## Acceder al Listado

Navega a `/drugs` o haz clic en la tarjeta **Base de Datos** del Dashboard.

---

## Listado y Paginación

La pantalla muestra una tabla/cuadrícula de fármacos con los campos básicos:

- **DrugBank ID** (ej. `DB01050`)
- **Nombre** (ej. Ibuprofen)
- **Tipo** (Small molecule, Biotech, etc.)
- **Grupos** (approved, investigational, experimental, etc.)

### Paginación

Usa los botones **Anterior** / **Siguiente** al pie de la lista. La paginación es basada en cursor (no en página numérica), lo que garantiza consistencia aunque la colección cambie entre páginas.

---

## Filtros de Búsqueda

Accede a los filtros disponibles desde el panel lateral o la barra de filtros superior:

| Filtro | Descripción | Ejemplo |
|--------|-------------|---------|
| **Tipo** | Tipo de droga según DrugBank | `small molecule` |
| **Grupo** | Estado de aprobación | `approved`, `experimental` |
| **Nombre** | Búsqueda textual por nombre (parcial) | `aspirin` |

Los filtros se aplican en tiempo real al hacer clic en **Aplicar filtros**. Puedes combinar varios filtros.

> **Endpoint API**: `GET /api/drugs/?drug_type=small+molecule&drug_groups=approved&name=ibu&per_page=20`

---

## Perfil Detallado de un Fármaco

Haz clic en cualquier fármaco de la lista para acceder a su perfil completo (`/drugs/<drugbank_id>`).

El perfil se organiza en pestañas:

| Pestaña | Contenido |
|---------|-----------|
| **Química** | SMILES, fórmula molecular, peso molecular, InChI |
| **Clínica** | Mecanismo de acción, indicaciones, farmacocinética (ADMET) |
| **Genómica** | Rutas de síntesis, clasificación farmacogenómica |
| **Mercado** | Nombres comerciales, fabricantes, presentaciones |
| **Dianas** | Lista de proteínas target con tipo de relación |
| **Red** | Grafo de interacciones moleculares (Neo4j) |
| **Rutas** | Efecto directo, indirecto (STRING) y rutas KEGG |

---

## Ejemplo: Buscar Ibuprofeno

1. Ve a `/drugs`.
2. Escribe `ibu` en el campo de nombre.
3. Selecciona el grupo `approved`.
4. Haz clic en **Aplicar filtros**.
5. Aparece **DB01050 — Ibuprofen** (entre otros resultados).
6. Haz clic en el resultado para ver su perfil completo.
7. En la pestaña **Dianas** verás targets como `Prostaglandin G/H synthase 1` y `Prostaglandin G/H synthase 2`.
