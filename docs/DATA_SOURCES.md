# Fuentes de datos — DrugGraph Open

DrugGraph Open reemplaza el dataset propietario de **DrugBank** por un conjunto de
fuentes **open-source y redistribuibles**. Todas las que forman el catálogo permiten
uso académico y redistribución bajo licencias abiertas (CC BY / CC BY-SA / dominio
público). Ninguna requiere licencia comercial ni acuerdo de confidencialidad.

## Fuentes del catálogo (reemplazan a DrugBank)

| Fuente | Rol en DrugGraph Open | Licencia | Formato / acceso |
|--------|-----------------------|----------|------------------|
| **DrugCentral** | **Backbone del catálogo**: fármacos, estructura (SMILES/InChI), tipo, estado de aprobación, dianas (bioactividad), clases farmacológicas/ATC, indicaciones | CC BY-SA 4.0 | Dump PostgreSQL (`drugcentral.dump.sql.gz`) |
| **ChEMBL** | Enriquecimiento: bioactividad experimental, mecanismos de acción, SMILES canónico, cross-refs | CC BY-SA 3.0 | Dump PostgreSQL/SQLite + API REST |
| **UniProt** | Datos canónicos de proteína para el navegador de dianas | CC BY 4.0 | API REST (`rest.uniprot.org`) |
| **Open Targets** | Evidencia diana→enfermedad (tool de reposicionamiento/evidencia) | CC0 1.0 | GraphQL API |
| **PubChem** | Propiedades fisicoquímicas, BioAssay, cross-refs por CID | Dominio público | API REST (PUG) |
| **CTD** (Comparative Toxicogenomics Database) | Interacciones curadas químico-gen (sandbox) | Gratuito uso académico; datos redistribuibles con atribución | `CTD_chem_gene_ixns.csv.gz` |
| **ToxinPred** | Predicción/anotación de toxicidad de péptidos (tool de toxicidad) | Académico libre | Modelo/servicio (ver `step06`) |

## Fuentes de red / pathways (ya eran open en DrugGraph)

Estas no dependían de DrugBank y se conservan igual:

| Fuente | Rol | Licencia |
|--------|-----|----------|
| **STRING** | PPI vecinos + red bulk para propagación (difusión) | CC BY 4.0 |
| **KEGG** | Pathways de dianas + KGML regulatorio (cascada dirigida) | Libre para académico (API) |
| **OmniPath / SIGNOR** | Red causal con signo (cascada dirigida, opcional) | CC BY / académico |
| **Reactome / WikiPathways / GO** | Enriquecimiento funcional (vía STRING/g:Profiler) | CC BY / CC0 |
| **BLAST+** | Homología de secuencia local | Dominio público (NCBI) |

## Interacciones fármaco-fármaco (DDI)

DrugBank era la fuente de las DDI **documentadas** (`drug-interactions`). Su reemplazo open:

| Fuente | Licencia | Nota |
|--------|----------|------|
| **DDInter 2.0** | CC BY-NC-SA 4.0 (**no comercial**) | ~240k DDI clínicas con severidad y mecanismo. Para uso académico. |
| **TWOSIDES / OFFSIDES (nSIDES)** | CC0 | DDI derivadas de farmacovigilancia (FAERS). 100% libre, incluye comercial. |

El pipeline usa **TWOSIDES por defecto** (CC0, sin restricciones) y deja DDInter como
opción documentada. El *riesgo PK/PD predicho* (`ddi_risk.py`) no depende de ninguna
fuente: se calcula sobre CYPs/dianas compartidas/proximidad y sigue funcionando igual.

## Mapeo de campos: DrugBank → DrugCentral (documento Mongo `drugs`)

El documento mantiene los **nombres de campo heredados** (`drugbank-id`, `name`, …) por
compatibilidad con el código de la app; el contenido proviene de fuentes open. El
identificador primario es un ID abierto derivado de DrugCentral (`DC<struct_id>`,
prefijo configurable con `OPEN_ID_PREFIX`).

| Campo Mongo (heredado) | Origen open-source |
|------------------------|--------------------|
| `drugbank-id` | `'DC' + structures.id` (DrugCentral struct_id) |
| `drugcentral_id` | `structures.id` (nuevo, explícito) |
| `name` | `structures.name` |
| `type` | `structure_type.type` → `small molecule` / `biotech` |
| `groups` | derivado de `approval` (approved/…) |
| `description` | `structures.mrdef` (MoA) + resumen ChEMBL |
| `unii` | `identifier` where `id_type='UNII'` |
| `average-mass` | RDKit sobre SMILES (o `structures`) |
| `calculated-properties` (SMILES/InChI/InChIKey) | `structures.smiles / inchi / inchikey` |
| `external-identifiers` | `identifier` (ChEMBL, PubChem CID, CAS, KEGG…) |
| `targets[]` | `act_table_full` agrupado por struct_id (`accession`→uniprot, `gene`, `action_type`) |
| `categories[]` | `pharma_class` + `struct2atc`/`atc` |
| `indications` | `omop_relationship` where `relationship_name='indication'` |
| `drug-interactions[]` | TWOSIDES (CC0) por struct_id ↔ struct_id |

## Mapeo al grafo Neo4j

Idéntico al modelo de DrugGraph (la app no cambia):

- `(:Drug {drugbank_id:'DC…', name, type, groups})`
- `(:Target {drugbank_target_id, name, gene_name, uniprot_id})`
- `(:Category {name})`
- `(:Drug)-[:TARGETS {action}]->(:Target)`
- `(:Drug)-[:IN_CATEGORY]->(:Category)`
- `(:Drug)-[:INTERACTS_WITH {source}]-(:Drug)`
- `(:Gene {name})` + `[:STRING_ASSOC]`, `[:REGULATES]` (scripts heredados, ya open)

## Atribución

Al publicar/derivar de estos datos, cita cada fuente según su licencia. Ver el
`NOTICE` del repositorio para el texto de atribución completo.
