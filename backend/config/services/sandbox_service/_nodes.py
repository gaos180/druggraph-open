"""
_nodes.py — Ciclo de vida del nodo temporal :SandboxDrug en Neo4j.

Crea, elimina y limpia (por TTL) los nodos sandbox, aislados por session_id y
vinculados a targets candidatos vía -[:SANDBOX_TARGETS]->.
"""

import logging
import time
import uuid

from neo4j import exceptions as neo4j_exc

from config.services.neo4j_service import _session
from ._chemistry import RDKIT_OK, validate_smiles, compute_fingerprint

log = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────
SANDBOX_TTL_SECONDS   = 30 * 60   # 30 minutos — limpieza automática
MAX_CANDIDATE_TARGETS = 30        # targets que el usuario puede asociar al sandbox


def create_sandbox_drug(
    smiles: str,
    name: str = "Compuesto sandbox",
    target_ids: list[str] | None = None,
    session_id: str | None = None,
) -> dict:
    """
    Crea un nodo temporal (:SandboxDrug) en Neo4j, aislado por session_id.

    Parámetros:
        smiles      : SMILES del compuesto.
        name        : nombre descriptivo dado por el usuario.
        target_ids  : drugbank_target_id de targets candidatos
                      (máx. MAX_CANDIDATE_TARGETS).
        session_id  : si no se provee, se genera uno nuevo (uuid4).

    Retorna:
        {
            "session_id":  str,
            "sandbox_id":  str,
            "name":        str,
            "smiles":      str,
            "fingerprint": str,        # "" si RDKit no disponible
            "properties":  {...},      # propiedades fisicoquímicas (RDKit)
            "linked_targets": [str],   # drugbank_target_id efectivamente vinculados
            "expires_at": float,       # epoch timestamp
        }

    Lanza ValueError si el SMILES es inválido o RDKit no está disponible.
    """
    props = validate_smiles(smiles)
    if props is None:
        raise ValueError(
            "SMILES inválido."
            if RDKIT_OK else
            "RDKit no está instalado en el servidor: no se puede procesar el compuesto."
        )

    fingerprint = compute_fingerprint(smiles) or ""

    session_id = session_id or str(uuid.uuid4())
    sandbox_id = str(uuid.uuid4())
    created_at = time.time()
    expires_at = created_at + SANDBOX_TTL_SECONDS

    target_ids = (target_ids or [])[:MAX_CANDIDATE_TARGETS]

    cypher_create = """
        CREATE (s:SandboxDrug {
            sandbox_id:       $sandbox_id,
            session_id:       $session_id,
            name:             $name,
            smiles:           $smiles,
            canonical_smiles: $canonical_smiles,
            fingerprint:      $fingerprint,
            molecular_weight: $molecular_weight,
            logp:             $logp,
            h_bond_donors:    $h_bond_donors,
            h_bond_acceptors: $h_bond_acceptors,
            tpsa:             $tpsa,
            rotatable_bonds:  $rotatable_bonds,
            aromatic_rings:   $aromatic_rings,
            created_at:       $created_at,
            expires_at:       $expires_at
        })
        RETURN s.sandbox_id AS sandbox_id
    """

    cypher_link_target = """
        MATCH (s:SandboxDrug {sandbox_id: $sandbox_id}),
              (t:Target {drugbank_target_id: $target_id})
        MERGE (s)-[:SANDBOX_TARGETS]->(t)
        RETURN t.drugbank_target_id AS linked
    """

    linked_targets = []
    try:
        with _session() as session:
            session.run(
                cypher_create,
                sandbox_id=sandbox_id,
                session_id=session_id,
                name=name[:200],
                smiles=smiles,
                canonical_smiles=props["canonical_smiles"],
                fingerprint=fingerprint,
                molecular_weight=props["molecular_weight"],
                logp=props["logp"],
                h_bond_donors=props["h_bond_donors"],
                h_bond_acceptors=props["h_bond_acceptors"],
                tpsa=props["tpsa"],
                rotatable_bonds=props["rotatable_bonds"],
                aromatic_rings=props["aromatic_rings"],
                created_at=created_at,
                expires_at=expires_at,
            )

            for tid in target_ids:
                result = session.run(
                    cypher_link_target, sandbox_id=sandbox_id, target_id=tid
                ).single()
                if result:
                    linked_targets.append(result["linked"])

    except neo4j_exc.ServiceUnavailable:
        log.error("Neo4j no disponible al crear sandbox")
        raise
    except Exception as exc:
        log.error("Error creando sandbox: %s", exc)
        raise

    return {
        "session_id":  session_id,
        "sandbox_id":  sandbox_id,
        "name":        name,
        "smiles":      smiles,
        "fingerprint": fingerprint,
        "properties":  props,
        "linked_targets": linked_targets,
        "expires_at": expires_at,
    }


def delete_sandbox_drug(sandbox_id: str | None = None, session_id: str | None = None) -> int:
    """
    Elimina nodo(s) :SandboxDrug y todas sus relaciones.

    - Si se pasa sandbox_id: borra ese nodo específico.
    - Si se pasa session_id: borra TODOS los nodos sandbox de esa sesión.

    Retorna el número de nodos eliminados.
    """
    if not sandbox_id and not session_id:
        raise ValueError("Se requiere sandbox_id o session_id")

    if sandbox_id:
        cypher = """
            MATCH (s:SandboxDrug {sandbox_id: $key})
            DETACH DELETE s
            RETURN count(s) AS deleted
        """
        params = {"key": sandbox_id}
    else:
        cypher = """
            MATCH (s:SandboxDrug {session_id: $key})
            DETACH DELETE s
            RETURN count(s) AS deleted
        """
        params = {"key": session_id}

    try:
        with _session() as session:
            result = session.run(cypher, **params).single()
            return result["deleted"] if result else 0
    except Exception as exc:
        log.error("Error eliminando sandbox: %s", exc)
        return 0


def cleanup_expired_sandboxes() -> int:
    """
    Elimina todos los nodos :SandboxDrug cuyo expires_at ya pasó.
    Pensado para ejecutarse periódicamente (management command / cron / celery beat).
    """
    cypher = """
        MATCH (s:SandboxDrug)
        WHERE s.expires_at < $now
        DETACH DELETE s
        RETURN count(s) AS deleted
    """
    try:
        with _session() as session:
            result = session.run(cypher, now=time.time()).single()
            deleted = result["deleted"] if result else 0
            if deleted:
                log.info("Limpieza sandbox: %d nodos expirados eliminados", deleted)
            return deleted
    except Exception as exc:
        log.error("Error en cleanup_expired_sandboxes: %s", exc)
        return 0
