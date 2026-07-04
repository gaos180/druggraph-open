"""Pipeline de ingesta open-source de DrugGraph Open.

Restaura los dumps SQL de DrugCentral/ChEMBL en el Postgres de staging y proyecta
(ETL) a MongoDB (documentos de fármaco) + Neo4j (grafo molecular), produciendo el
mismo esquema que consumía DrugGraph sobre DrugBank — pero con datos redistribuibles.

Orden de ejecución en scripts/ingest/README.md.
"""
