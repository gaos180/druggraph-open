# 07 — Vista de Despliegue

## 7.1 Entorno de Desarrollo Local

```
Máquina del desarrollador
│
├── docker compose up -d
│   ├── mongo:latest          → localhost:27017
│   │   └── druggraph (DB)
│   │       ├── users (colección)
│   │       └── drugs (colección)
│   │
│   └── neo4j:5.x-community   → localhost:7474 (HTTP Browser)
│       con plugin GDS          → localhost:7687 (Bolt)
│
├── python manage.py runserver → localhost:8000
│   └── backend/venv/          ← pip install -r requirements.txt
│       (Django 4.x + DRF + pymongo + neo4j-driver + requests + rdkit)
│
└── npm start                  → localhost:3000
    └── frontend/node_modules/ ← npm install
        (React 18 + TypeScript + Axios + Cytoscape.js)
```

### docker-compose.yml (puertos y volúmenes relevantes)

```yaml
services:
  mongo:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/druggraph123
      NEO4J_PLUGINS: '["graph-data-science"]'
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
```

## 7.2 Variables de Entorno (Backend)

| Variable | Default (desarrollo) | Descripción |
|----------|---------------------|-------------|
| `MONGODB_URI` | `mongodb://localhost:27017/` | URI de conexión MongoDB |
| `MONGODB_DB` | `druggraph` | Nombre de la base de datos |
| `NEO4J_URI` | `bolt://localhost:7687` | URI Bolt de Neo4j |
| `NEO4J_USER` | `neo4j` | Usuario Neo4j |
| `NEO4J_PASSWORD` | `druggraph123` | Contraseña Neo4j |
| `JWT_SECRET` | `druggraph-jwt-secret-change-in-production` | Clave HMAC para JWT |
| `BLAST_DB_PATH` | `` (vacío) | Ruta al índice BLAST (blastdb prefix) |
| `BLAST_MAP_PATH` | `` (vacío) | Ruta al JSON de mapeo target→drugbank_id |
| `BLAST_THREADS` | `2` | Hilos de blastp |

## 7.3 Variables de Entorno (Frontend)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `http://localhost:8000/api` | Base URL del backend |

## 7.4 Pasos de Primer Arranque

```bash
# 1. Levantar bases de datos
docker compose up -d

# 2. Activar entorno Python e instalar dependencias
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Crear usuario admin
python seed_admin.py   # → admin@druggraph.dev / admin1234

# 4. (Opcional) Construir índice BLAST
pip install biopython   # si se usa el script de construcción
python build_blast_db.py

# 5. (Opcional) Poblar fingerprints en Neo4j para sandbox estructural
python populate_fingerprints.py

# 6. Iniciar backend
python manage.py runserver

# 7. Iniciar frontend (en otra terminal)
cd ../frontend
npm install
npm start
```

## 7.5 Puertos Usados

| Puerto | Servicio |
|--------|---------|
| 3000 | React SPA (npm start) |
| 8000 | Django REST API |
| 27017 | MongoDB |
| 7474 | Neo4j Browser (HTTP) |
| 7687 | Neo4j Bolt |
