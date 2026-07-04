"""
sandbox_service — Servicio de "químico sandbox" para DrugGraph.

Permite a un usuario ingresar un compuesto (SMILES + targets candidatos) SIN
afectar la base compartida:
  - _chemistry: fingerprint molecular (RDKit, Morgan/ECFP4) y propiedades.
  - _nodes:     nodo temporal (:SandboxDrug) en Neo4j, aislado por session_id,
                con relaciones -[:SANDBOX_TARGETS]-> hacia targets reales.
  - _similarity: similitud estructural (Tanimoto) y de comportamiento
                (GDS nodeSimilarity / Jaccard sobre targets compartidos).
  - analyze_sandbox_compound (este módulo): orquesta crear + ambas similitudes +
                combinar + limpiar el nodo.

Dependencias: pip install rdkit neo4j
"""

from ._chemistry import (
    RDKIT_OK, FP_RADIUS, FP_NBITS,
    validate_smiles, compute_fingerprint, fingerprint_from_text, tanimoto_similarity,
    named_similarities,
)
from ._nodes import (
    SANDBOX_TTL_SECONDS, MAX_CANDIDATE_TARGETS,
    create_sandbox_drug, delete_sandbox_drug, cleanup_expired_sandboxes,
)
from ._similarity import (
    MAX_SIMILAR_RESULTS, MAX_GDS_CANDIDATE_POOL,
    structural_similarity,
    behavioral_similarity_by_shared_targets,
    behavioral_similarity_gds,
    _behavioral_score_for_drugs,
    _infer_targets_from_structural,
)

__all__ = [
    "RDKIT_OK", "FP_RADIUS", "FP_NBITS",
    "validate_smiles", "compute_fingerprint", "fingerprint_from_text", "tanimoto_similarity",
    "named_similarities",
    "SANDBOX_TTL_SECONDS", "MAX_CANDIDATE_TARGETS",
    "create_sandbox_drug", "delete_sandbox_drug", "cleanup_expired_sandboxes",
    "MAX_SIMILAR_RESULTS", "MAX_GDS_CANDIDATE_POOL",
    "structural_similarity",
    "behavioral_similarity_by_shared_targets", "behavioral_similarity_gds",
    "analyze_sandbox_compound",
]


def analyze_sandbox_compound(
    smiles: str,
    name: str = "Compuesto sandbox",
    target_ids: list[str] | None = None,
    session_id: str | None = None,
    cleanup: bool = True,
) -> dict:
    """
    Pipeline completo:
      1. Crea el nodo :SandboxDrug (temporal) en Neo4j.
      2. Calcula similitud estructural (Tanimoto) contra fármacos reales.
      3. Calcula similitud de comportamiento (targets compartidos) —
         intenta GDS primero, cae a Jaccard simple si no está disponible.
      4. Combina ambos scores en un ranking unificado (50/50).
      5. (opcional) Elimina el nodo sandbox al finalizar.

    Retorna:
        {
            "sandbox": { ...metadata del compuesto, sin el campo fingerprint... },
            "structural_similarity": [ {drugbank_id, name, score} ],
            "behavioral_similarity": [ {drugbank_id, name, score, shared_targets?} ],
            "combined": [ {drugbank_id, name, structural_score, behavioral_score,
                            combined_score, shared_targets?} ],
            "method_used": "gds" | "jaccard" | "structural_only" | "none"
        }
    """
    sandbox = create_sandbox_drug(
        smiles=smiles, name=name, target_ids=target_ids, session_id=session_id
    )

    structural = structural_similarity(sandbox["fingerprint"])

    behavioral = []
    method_used = "structural_only" if structural else "none"
    targets_inferred = False

    if sandbox["linked_targets"]:
        # Jaccard por identidad proteica (uniprot_id / gene_name) como clave canónica.
        # No usamos GDS aquí porque compara nodos exactos de Neo4j: si la misma proteína
        # tiene distintos drugbank_target_id según el rol (target vs enzima), GDS no
        # detecta la coincidencia y devuelve 0% aunque los fármacos compartan la proteína.
        behavioral = behavioral_similarity_by_shared_targets(sandbox["linked_targets"])
        if behavioral:
            method_used = "jaccard"
            # El LIMIT del ranking general puede dejar fuera fármacos que sí están
            # en el top estructural (ej. ibuprofeno con 28 targets queda en posición #98
            # cuando hay 97 fármacos con target set más pequeño y Jaccard más alto).
            # Los rescatamos con una query dirigida para asegurar que tengan su score.
            behavioral_ids = {b["drugbank_id"] for b in behavioral}
            missing = [s["drugbank_id"] for s in structural if s["drugbank_id"] not in behavioral_ids]
            if missing:
                extra = _behavioral_score_for_drugs(sandbox["linked_targets"], missing)
                behavioral.extend(extra)
        elif not structural:
            method_used = "none"
    elif structural:
        # Sin targets explícitos: inferir de los fármacos estructuralmente más similares.
        # Para compuestos idénticos a un fármaco real (score=1.0) reproduce sus targets
        # exactos; para compuestos novedosos usa la unión de los análogos más cercanos.
        inferred = _infer_targets_from_structural(structural)
        if inferred:
            behavioral = behavioral_similarity_by_shared_targets(inferred)
            if behavioral:
                method_used = "jaccard_inferred"
                targets_inferred = True
                behavioral_ids = {b["drugbank_id"] for b in behavioral}
                missing = [s["drugbank_id"] for s in structural if s["drugbank_id"] not in behavioral_ids]
                if missing:
                    extra = _behavioral_score_for_drugs(inferred, missing)
                    behavioral.extend(extra)

    # ── Combinar rankings (50% estructural + 50% comportamiento) ──────────
    combined_map: dict[str, dict] = {}

    for s in structural:
        combined_map[s["drugbank_id"]] = {
            "drugbank_id": s["drugbank_id"],
            "name": s["name"],
            "structural_score": s["score"],
            "behavioral_score": 0.0,
        }

    for b in behavioral:
        entry = combined_map.setdefault(b["drugbank_id"], {
            "drugbank_id": b["drugbank_id"],
            "name": b["name"],
            "structural_score": 0.0,
            "behavioral_score": 0.0,
        })
        entry["behavioral_score"] = b["score"]
        if "shared_targets" in b:
            entry["shared_targets"] = b["shared_targets"]

    combined = []
    for entry in combined_map.values():
        entry["combined_score"] = round(
            0.5 * entry["structural_score"] + 0.5 * entry["behavioral_score"], 4
        )
        combined.append(entry)

    combined.sort(key=lambda x: x["combined_score"], reverse=True)
    combined = combined[:MAX_SIMILAR_RESULTS]

    # Quitar el fingerprint del dict de salida (interno, no útil para el frontend)
    sandbox_out = {k: v for k, v in sandbox.items() if k != "fingerprint"}

    if cleanup:
        delete_sandbox_drug(sandbox_id=sandbox["sandbox_id"])

    return {
        "sandbox": sandbox_out,
        "structural_similarity": structural,
        "behavioral_similarity": behavioral,
        "combined": combined,
        "method_used": method_used,
        "targets_inferred": targets_inferred,
    }
