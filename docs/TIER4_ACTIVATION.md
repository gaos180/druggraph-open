# Activación del Tier 4 (ML propio): RAM, 4.1, 4.2 y roadmap de métodos externos

_Última actualización: 2026-07-06._

Estado de partida (ver `DATASET_STATE.md`): **4.3 ADMET activo** (RandomForest sobre
MoleculeNet, `backend/models/admet/`), **4.4 de novo** con motores CReM + SyntheMol + REINVENT4
(código), **4.1 chemical-space** y **4.2 DTI-GNN** sin poblar. Este documento explica cuánta RAM
tiene realmente el equipo, cómo liberarla/ampliarla, y los pasos exactos para activar 4.1 y 4.2.

---

## 1. Análisis de RAM de este equipo

| Métrica | Valor |
|---------|------:|
| RAM física total | **14.2 GB** (`MemTotal` 14 245 096 kB) |
| Swap total | 2.0 GB |
| **Disponible ahora** | **~2.5 GB** (swap lleno) |
| Disco libre en `/` | 185 GB |

### Quién consume la RAM ahora mismo

⚠️ **El proceso `qemu-system-x86_64` (~3 GB, `-m 3477`) es la VM interna de Docker Desktop**
(LinuxKit; discos `~/.docker/desktop/vms/0/data/Docker.raw`, lanzada por `com.docker.backend`,
contexto `desktop-linux`). En Linux, Docker Desktop corre **todos** los contenedores *dentro* de
esa VM. Por tanto sus ~3 GB **SON** los contenedores (Neo4j-open 1.38 GB + Neo4j-original 0.87 GB +
mongos + postgres ≈ 2.6 GB, bajo el tope de 3.4 GB de la VM), **no** memoria adicional aparte.
**No la apagues**: matarías Docker y todas las BD de DrugGraph.

| Proceso / contenedor | RSS aprox. | ¿Reclamable? |
|----------------------|-----------:|--------------|
| **VM Docker Desktop** (`qemu -m 3477`) — contiene TODOS los contenedores | **~3.0 GB** | **No** — es Docker mismo; techo compartido de 3.4 GB para todos los contenedores |
| Firefox (varias pestañas) | **~3.0 GB** | **Sí** — cerrar pestañas/navegador (RAM del host) |
| **Stack DrugGraph ORIGINAL** (`druggraph-neo4j` 0.87 GB + `druggraph-mongodb` 85 MB, DENTRO de la VM Docker) | ~1.0 GB | **Sí, pero** libera espacio *dentro* de la VM (no necesariamente al host) |
| Backends dev del original (:8000 / :8010, procesos del host) | ~0.6 GB | **Sí** (RAM del host) |
| Stack DrugGraph-OPEN (neo4j 1.38 GB + mongo + postgres, DENTRO de la VM Docker) | ~1.55 GB | **No** (lo necesitas) |
| GNOME/nautilus/claude/otros (host) | ~1.5 GB | Parcial |

### Conclusión: cuánta RAM puedes usar

Hay **dos "pools" de RAM distintos** y cada carga del Tier 4 usa uno:

- **RAM del HOST** (para 4.1: torch/ChemBERTa corren como proceso del venv, *fuera* de Docker).
  Hoy ~2.5 GB libres; **cerrando Firefox liberas ~3 GB** → suficiente para torch (~2–4 GB pico).
  La VM de Docker está capada a 3.4 GB y no molesta a esta carga.
- **RAM DENTRO de la VM Docker** (para 4.2: GDS corre *dentro* de Neo4j, dentro de la VM). El heap
  de Neo4j compite con mongo+postgres+el stack original en el tope de **3.4 GB de la VM**. Para
  darle aire a GDS: **(a) parar el stack ORIGINAL** (libera ~1 GB dentro de la VM) y/o **(b) subir
  la memoria asignada a la VM de Docker Desktop** (§2.3), y luego subir el heap del contenedor.

**Regla práctica:** para **4.1** cierra Firefox (RAM host). Para **4.2** para el stack original y/o
amplía la VM de Docker (RAM de la VM). No hay que "apagar QEMU" — eso ES Docker.

---

## 2. Cómo liberar y ampliar RAM

### 2.1 Liberar RAM del host (rápido, reversible)

⚠️ **No apagues el proceso `qemu-system` — es Docker Desktop** (§1). Para liberar RAM:

```bash
# a) Cerrar Firefox o sus pestañas pesadas → libera ~2–3 GB de RAM del HOST (lo que usa 4.1).

# b) Parar el stack DrugGraph ORIGINAL → libera ~1 GB DENTRO de la VM Docker (aire para 4.2).
#    Sus contenedores están dentro de la misma VM Docker que el stack open:
docker stop druggraph-neo4j druggraph-mongodb
#    y cierra los backends dev del original (:8000 / :8010), que sí son procesos del host:
ss -tlnp | grep -E ':8000|:8010'      # identifica los PID y ciérralos

free -h    # 'disponible' (host) sube al cerrar Firefox/backends; la VM Docker sigue ~3.4 GB
```

### 2.2 Ampliar swap (colchón anti-OOM; hay 185 GB de disco libre)

```bash
sudo fallocate -l 8G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
free -h    # Swap ahora 10 GB
# Persistir: añade  /swapfile none swap sw 0 0  a /etc/fstab
```
El swap **no reemplaza** RAM real (es lento), pero evita que el OOM-killer mate a Neo4j durante
un pico. Útil como red de seguridad para las cargas de 4.1/4.2.

### 2.3 Subir el heap de Neo4j-open (para GDS y consultas profundas)

**Primero, el techo de la VM Docker.** El heap de Neo4j nunca podrá superar la RAM total de la VM
de Docker Desktop (hoy **~3.4 GB para TODOS los contenedores**). Si vas a subir el heap de Neo4j,
sube antes la memoria de la VM: **Docker Desktop → Settings → Resources → Memory** (o edita
`~/.docker/desktop/settings-store.json`, clave `memoryMiB`, y reinicia Docker Desktop). Súbela a
p. ej. 6–8 GB si el host lo permite tras cerrar Firefox. Alternativa sin ampliar la VM: **parar el
stack original** (§2.1b) para liberar ~1 GB dentro de la VM.

Después, amplía el heap del contenedor en `docker-compose.yml` (servicio `neo4j`):

```yaml
    environment:
      - NEO4J_server_memory_heap_initial__size=1500m
      - NEO4J_server_memory_heap_max__size=2500m      # antes 1000m
      - NEO4J_server_memory_pagecache_size=1000m      # antes 500m
    deploy:
      resources:
        limits:
          memory: 4000M                               # antes 1600M
```
Luego recrea solo ese contenedor (los datos persisten en el volumen `neo4j_data`):
```bash
docker compose up -d neo4j
```
Beneficio colateral: habilita también **STRING a score≥700** (~1–2 M aristas) y
`proximity_significance` con módulos grandes, hoy limitados por el heap.

---

## 3. Activar 4.1 — Mapa del espacio químico (ChemBERTa + UMAP/HDBSCAN)

**Prerrequisito de RAM:** hazlo con el host liberado (§2.1). El cuello de botella es torch cargando
el modelo ChemBERTa y haciendo inferencia sobre ~4310 fármacos con SMILES.

```bash
cd backend && source venv/bin/activate

# 1) Deps (torch CPU = más ligero). ~1.5 GB de descarga la primera vez.
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers umap-learn hdbscan joblib

# 2) Poblar embeddings ChemBERTa (768-dim) en :Drug.chemberta + índice vectorial Neo4j.
#    ~4310 moléculas en CPU: del orden de 10–30 min. Es IDEMPOTENTE: puedes trocearlo.
python -m scripts.populate_chemberta_embeddings            # o --limit 500 para ir por tandas
#    (Descarga el modelo ChemBERTa (~350–500 MB) de HuggingFace la primera vez.)

# 3) Construir el mapa 2D: UMAP + HDBSCAN sobre los 4310×768 embeddings.
#    Ligero (<1 GB, minutos). Escribe Mongo `chemical_space` + models/chemical_space/umap.joblib.
python -m scripts.build_chemical_space

# 4) Verificar
curl -s http://localhost:8090/api/tools/chemical-space/ | head    # nube de puntos (200)
```

Notas:
- Poblar `chemberta` **también activa la similitud por embeddings (Tier 3.2)** — dos features por
  el precio de una carga.
- El endpoint `POST /api/tools/chemical-space/locate/` (ubicar un SMILES nuevo) necesita
  torch+transformers en runtime (no solo la nube).
- Si la inferencia satura RAM, corre `populate_chemberta_embeddings --limit N` por tandas: es
  idempotente y solo procesa lo que falte.

---

## 4. Activar 4.2 — Predicción DTI por GNN (GDS)

**Corrección importante:** el plugin **GDS ya está instalado y cargado** en Neo4j-open
(GDS **2.13.8**, 423 procedimientos `gds.*`; el compose lo declara en
`NEO4J_PLUGINS=["apoc","graph-data-science"]`). Y `scikit-learn` ya está en el venv (se instaló
para ADMET). Es decir: **4.2 no está bloqueado por dependencias**, solo por la estabilidad del
heap de Neo4j durante la proyección del grafo.

```bash
cd backend && source venv/bin/activate

# 1) (recomendado) Sube el heap de Neo4j primero (§2.3) para que la proyección GDS no lo tumbe.

# 2) Entrena. Usa FastRP (MUCHO más ligero que GraphSAGE) en este equipo:
python -m scripts.train_dti_gnn --method fastrp --top-k 20
#    - Proyecta el grafo (≈5 k Drug + 1.8 k Target + 17 k TARGETS + 100 k STRING_ASSOC).
#    - Calcula embeddings FastRP + cabezal Link Prediction (regresión logística, muestreo negativo).
#    - Reporta AUCPR/AP en test, escribe (:Drug)-[:PREDICTED_TARGET {score}]->(:Target) y
#      persiste métricas en Mongo `model_metrics`. Es idempotente (reescribe las aristas).

# 3) Verificar
curl -s http://localhost:8090/api/tools/dti-gnn/DC4/ | head       # predicciones (200)
```

Notas:
- **FastRP antes que GraphSAGE**: GraphSAGE entrena una red y consume bastante más heap/CPU;
  FastRP es proyección aleatoria y basta para el cabezal LP. Si FastRP va bien y sobra RAM, prueba
  `--method graphsage`.
- La proyección GDS es el momento de mayor presión sobre Neo4j → hazlo con el host liberado y el
  heap subido. Los scripts son idempotentes: si Neo4j se reinicia, reintenta sin duplicar.
- Si prefieres no tocar Neo4j en producción, corre esto como paso offline y luego el endpoint solo
  **lee** las aristas `:PREDICTED_TARGET` (barato).

---

## 5. Roadmap: qué de la tabla de repos externos encaja en DrugGraph Open

Análisis de los métodos propuestos contra el sustrato del proyecto (grafo Neo4j Drug–Target–Gene,
bioactividad ChEMBL/PubChem, STRING PPI, UniProt, RDKit, GDS). Clave transversal: **casi todos son
o (a) predictores QSAR tipo GNN, o (b) generadores de novo, y el proyecto YA tiene un "slot" para
cada cosa** (4.3 predictor ADMET, 4.4 de novo). Además, **los antibióticos-específicos requieren
etiquetas de actividad antibacteriana que el proyecto no tiene cargadas** (no hay MIC/actividad).

| Repo / método | Veredicto | Razón |
|---------------|-----------|-------|
| **SyntheMol / SyntheMol-RL** | ✅ **Ya integrado (4.4c)** | Motor de novo con síntesis garantizada. Framework agnóstico de dominio: le enchufas tu predictor. Falta activarlo (bloques + predictor). |
| **Antibiotics_Chemprop** (GNN message-passing) | ⭐ **Implementar — máximo valor** | Chemprop es la **pieza clave**: es el predictor de bioactividad que SyntheMol necesita para guiar la búsqueda, y un **upgrade natural del ADMET 4.3** (GNN en vez de RandomForest). Un solo modelo sirve a 4.3 y 4.4. Necesita torch (misma restricción de RAM que 4.1). |
| **de-novo-antibiotics** (generativo de novo) | 🔁 **Redundante** | Ya cubierto por CReM/SyntheMol/REINVENT4 en 4.4. |
| **AstraZeneca GNN** (GNN genérico de propiedades) | 🔁 **Redundante** | Solapa con DTI-GNN (4.2) y con el Chemprop de arriba. Sin API pública propia. |
| **Insilico NDM-1** (Docking + ADMET + MD) | 🧭 **Nueva modalidad (Tier 5)** | La parte ADMET ya está (4.3). Lo **novedoso es el docking estructural** contra una diana concreta: nuevo subsistema (AutoDock Vina/GNINA + preparación de receptor) apoyado en las estructuras UniProt/PDB que ya maneja el navegador de dianas. Alto esfuerzo, alta novedad. |
| **BiomedGPS-Studio** (Knowledge graph + GNN) | 🔷 **Extensión de 4.2** | DrugGraph **ya ES** un knowledge graph biomédico en Neo4j. El aporte sería extender el Link Prediction de 4.2 a **más tipos de arista** (p. ej. fármaco→enfermedad para repurposing). Encaje arquitectónico directo. |
| **FinGAT** (GAT + fingerprints) | ⚠️ **Nicho / opcional** | Otro QSAR (GAT) redundante con Chemprop; además antibiótico-específico (necesita etiquetas de actividad). Valor marginal. |
| **antibioticsai** ("structural class…", Wong 2023) | ⚠️ **Investigación / opcional** | Predictor + explicabilidad (racionales de subestructura). Idea valiosa pero antibiótico-específica y pesada de portar. |
| **GraphCW** (Concept Whitening, GNN explicable) | ⚠️ **Investigación / opcional** | Capa de **explicabilidad** sobre un GNN de propiedades. Interesante si el objetivo es interpretabilidad; hoy el proyecto no la prioriza. |
| **Sieber Lab** (org con varios repos) | ➖ **No es un método único** | Es una organización/fuente de componentes, no algo implementable "de una". |

### Recomendación priorizada

1. **Chemprop como predictor GNN compartido** (de `Antibiotics_Chemprop`): entrénalo sobre la
   bioactividad que ya tenemos (ChEMBL) y **úsalo a la vez como (a) score model de SyntheMol 4.4 y
   (b) upgrade del ADMET 4.3**. Es el mayor retorno por unidad de esfuerzo y desbloquea el de novo
   con síntesis garantizada de punta a punta. (Depende de torch → resolver RAM con §2.)
2. **Extender 4.2 (BiomedGPS-style)** a Link Prediction fármaco→enfermedad para reforzar el
   repurposing, reutilizando el grafo y GDS que ya están.
3. **Docking estructural (NDM-1-style) como Tier 5** si se quiere una modalidad realmente nueva
   (structure-based), apoyada en las dianas UniProt/estructuras `.cif` existentes.
4. Explicabilidad (GraphCW/antibioticsai) y GATs (FinGAT): **diferir** salvo que aparezca un
   dataset antibiótico concreto y un objetivo de interpretabilidad.

**Prerrequisito común de (1):** los métodos GNN necesitan torch/Chemprop → la misma liberación de
RAM del §2. Los antibiótico-específicos necesitan además **cargar un dataset de actividad
antibacteriana** (p. ej. de ChEMBL) que hoy no está en el pipeline.
