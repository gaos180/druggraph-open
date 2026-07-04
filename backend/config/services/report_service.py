"""
report_service.py — Orquestación de la reportería IA de DrugGraph.

Toma el resultado de un análisis (sandbox, reposicionamiento, toxicidad, DEG, DDI),
lo **recorta** a lo esencial para acotar tokens/costo, arma un **prompt estructurado
y estricto (anti-alucinación)** según el estilo elegido, llama a `gemini_service` y
**persiste** el informe por usuario en la colección `reports` de MongoDB.

Contratos:
    KINDS   = tipos de análisis soportados.
    STYLES  = registros de redacción ('scientific' | 'executive').

El grounding estricto es el núcleo de calidad: el modelo solo puede usar los datos
JSON provistos, no puede inventar genes/rutas/cifras y debe marcar la incertidumbre.
"""

import datetime as _dt
import json
import logging
import uuid

from config.services import gemini_service
from config.services.mongo import get_db

log = logging.getLogger(__name__)

KINDS = ("sandbox", "repurposing", "toxicity", "deg", "ddi", "bioactivity",
         "denovo", "admet", "dti_gnn")
STYLES = ("scientific", "executive")

# Recortes por lista para acotar el payload enviado al modelo.
TOP_LIST = 15
TOP_DOWNSTREAM = 20

REPORTS_COLLECTION = "reports"


class ReportError(RuntimeError):
    pass


# ══════════════════════════════════════════════════════════════════════════════
# 1. Recorte de payload por tipo de análisis
# ══════════════════════════════════════════════════════════════════════════════

def _take(lst, n=TOP_LIST):
    return lst[:n] if isinstance(lst, list) else []


def _trim_sandbox(p: dict) -> dict:
    analysis = p.get("analysis") or p.get("sandbox_analysis") or {}
    pathways = p.get("pathways") or {}
    prop = p.get("propagation") or {}
    sandbox = analysis.get("sandbox") or {}

    return {
        "compound": {
            "name": sandbox.get("name"),
            "smiles": sandbox.get("smiles"),
            "properties": sandbox.get("properties"),
            "linked_targets": _take(sandbox.get("linked_targets") or [], 30),
        },
        "structural_similarity": _take(analysis.get("structural_similarity") or []),
        "behavioral_similarity": _take(analysis.get("behavioral_similarity") or []),
        "combined_similarity": _take(analysis.get("combined") or []),
        "targets_used": _take(pathways.get("targets_used") or [], 30),
        "kegg_pathways": _take((pathways.get("kegg") or {}).get("pathways") or []),
        "go_process": _take(pathways.get("go_process") or []),
        "go_function": _take(pathways.get("go_function") or []),
        "reactome": _take(pathways.get("reactome") or []),
        "wikipathways": _take(pathways.get("wikipathways") or []),
        "propagation_mode": prop.get("mode"),
        "propagation_seeds_used": prop.get("seeds_used"),
        "propagation_downstream": _take(prop.get("downstream") or [], TOP_DOWNSTREAM),
    }


def _trim_repurposing(p: dict) -> dict:
    return {
        "drug": p.get("drug"),
        "targets": _take(p.get("targets") or [], 30),
        "candidates": _take(p.get("candidates") or []),
        "go_profile": _take(p.get("go_profile") or []),
    }


def _trim_toxicity(p: dict) -> dict:
    return {
        "drug": p.get("drug"),
        "risk_score": p.get("risk_score"),
        "risk_level": p.get("risk_level"),
        "alert_counts": p.get("alert_counts"),
        "alerts": _take(p.get("alerts") or [], 30),
        "cyp_interactions": _take(p.get("cyp_interactions") or []),
        "predicted_offtargets": _take(p.get("predicted_offtargets") or []),
        "structural_cluster": _take(p.get("structural_cluster") or []),
        "target_count": p.get("target_count"),
    }


def _trim_deg(p: dict) -> dict:
    return {
        "drug": p.get("drug"),
        "stats": p.get("stats"),
        "overlap": _take(p.get("overlap") or [], 30),
        "go_enrichment": _take(p.get("go_enrichment") or []),
        "notes": p.get("notes"),
    }


def _trim_ddi(p: dict) -> dict:
    out = {
        "mode": p.get("mode"),
        "drug": p.get("drug") or p.get("drug_a"),
    }
    if p.get("mode") == "pair":
        out.update({
            "drug_a": p.get("drug_a"),
            "drug_b": p.get("drug_b"),
            "interacts": p.get("interacts"),
            "description": p.get("description"),
        })
    else:
        out.update({
            "interaction_count": p.get("interaction_count"),
            "interactions": _take(p.get("interactions") or [], 40),
        })
    return out


def _trim_bioactivity(p: dict) -> dict:
    chembl = p.get("chembl") or {}
    pubchem = p.get("pubchem") or {}
    return {
        "drug": p.get("drug"),
        "smiles": p.get("smiles"),
        "chembl_molecule": chembl.get("molecule"),
        "chembl_mechanisms": _take(chembl.get("mechanisms") or []),
        "chembl_activities": _take(chembl.get("activities") or [], TOP_DOWNSTREAM),
        "pubchem_cid": pubchem.get("cid"),
        "pubchem_active": pubchem.get("active"),
        "pubchem_inactive": pubchem.get("inactive"),
        "pubchem_total": pubchem.get("total"),
        "pubchem_top_active_assays": _take(
            [a for a in (pubchem.get("assays") or []) if a.get("activity") == "Active"], TOP_LIST
        ),
    }


def _trim_denovo(p: dict) -> dict:
    return {
        "engine": p.get("engine"),
        "paper": p.get("paper"),
        "seed_smiles": p.get("seed_smiles"),
        "mode": p.get("mode"),
        "generated": p.get("generated"),
        "candidates": _take(p.get("candidates") or [], TOP_DOWNSTREAM),
        "disclaimer": p.get("disclaimer"),
    }


def _trim_admet(p: dict) -> dict:
    return {
        "smiles": p.get("smiles"),
        "drug": p.get("drug"),
        "predictions": _take(p.get("predictions") or [], 30),
    }


def _trim_dti_gnn(p: dict) -> dict:
    return {
        "drug": p.get("drug"),
        "model": p.get("model"),
        "predictions": _take(p.get("predictions") or [], 30),
    }


_TRIMMERS = {
    "sandbox": _trim_sandbox,
    "repurposing": _trim_repurposing,
    "toxicity": _trim_toxicity,
    "deg": _trim_deg,
    "ddi": _trim_ddi,
    "bioactivity": _trim_bioactivity,
    "denovo": _trim_denovo,
    "admet": _trim_admet,
    "dti_gnn": _trim_dti_gnn,
}


# ══════════════════════════════════════════════════════════════════════════════
# 2. Prompts (estructurados + estrictos anti-alucinación)
# ══════════════════════════════════════════════════════════════════════════════

_SYSTEM_INSTRUCTION = """\
Eres un asistente experto en farmacología computacional y biología de sistemas que \
redacta informes para la plataforma DrugGraph.

REGLAS ESTRICTAS (obligatorias, sin excepción):
1. Usa EXCLUSIVAMENTE los datos JSON que se te entregan. NO inventes genes, rutas, \
proteínas, fármacos, valores numéricos ni afirmaciones clínicas que no estén en los datos.
2. Cita los identificadores (genes, rutas, IDs DrugBank), scores, p-valores/FDR y \
signos (+/-) EXACTAMENTE como aparecen en los datos. No redondees ni alteres cifras.
3. Si un dato no está presente, dilo explícitamente ("no disponible en los datos"). \
No rellenes vacíos con conocimiento general.
4. Todo lo que reportes es una HIPÓTESIS computacional in-silico, NO un diagnóstico ni \
consejo clínico. Sé claro sobre la incertidumbre y las limitaciones del método.
5. Puedes aportar interpretación mecanística plausible SOLO si la anclas a las dianas/ \
rutas presentes en los datos, y marcándola como hipótesis.
6. Escribe en español, con formato Markdown (encabezados ##, listas, y **negritas** \
para resaltar). No inventes tablas con datos que no tengas.
7. Termina SIEMPRE con un descargo de responsabilidad de que es un análisis in-silico \
exploratorio y no sustituye validación experimental ni criterio clínico.
"""

_KIND_CONTEXT = {
    "sandbox": (
        "Análisis de un compuesto en el 'Laboratorio Virtual': similitud estructural "
        "(Tanimoto sobre fingerprints Morgan) y conductual (solapamiento de dianas) "
        "frente a fármacos reales, rutas afectadas (KEGG/GO/Reactome) por sus dianas, "
        "y propagación del efecto por la red (difusión PageRank o cascada dirigida con "
        "signo donde -1=inhibición y +1=activación del gen downstream)."
    ),
    "repurposing": (
        "Candidatos de reposicionamiento de un fármaco por similitud de red de dianas "
        "(índice de Jaccard del conjunto de genes diana; 'shared_genes' = dianas "
        "compartidas) y perfil de enriquecimiento funcional GO/KEGG del fármaco."
    ),
    "toxicity": (
        "Perfil de toxicidad/off-targets de un fármaco: alertas por anti-targets "
        "documentados (hERG/KCNH2, CYPs, dopamina, etc. con nivel high/medium/low), "
        "off-targets predichos topológicamente (score Adamic-Adar), cluster estructural "
        "de fármacos similares y un score de riesgo agregado 0-10."
    ),
    "deg": (
        "Análisis de expresión diferencial (DEG): genes up/down significativos, su "
        "intersección con las dianas del fármaco, y enriquecimiento funcional (ORA con "
        "FDR vía g:Profiler) de los genes relevantes."
    ),
    "ddi": (
        "Interacciones fármaco-fármaco (DDI) documentadas en DrugBank: en modo 'single' "
        "todas las interacciones del fármaco; en modo 'pair' si dos fármacos interactúan "
        "y la descripción del mecanismo."
    ),
    "bioactivity": (
        "Bioactividad experimental del compuesto: mecanismo de acción y potencia curados en "
        "ChEMBL (pchembl_value = -log10 de la concentración molar; a mayor pChEMBL, más potente; "
        "standard_type IC50/Ki/EC50/Kd) y resumen de bioensayos de PubChem "
        "(active/inactive por ensayo). Es evidencia MEDIDA, no predicha."
    ),
    "denovo": (
        "Diseño molecular de novo: moléculas GENERADAS in silico a partir de un seed con un "
        "motor publicado (CReM, fragment-based; o REINVENT4, generativo RNN), filtradas por "
        "propiedades drug-like: QED (0-1, calidad drug-like), SA score (1 fácil - 10 difícil de "
        "sintetizar), similitud de Tanimoto al seed y reglas de Lipinski cumplidas (0-4). Son "
        "HIPÓTESIS sin validación experimental; NO afirmes actividad biológica no medida."
    ),
    "admet": (
        "Predicción ADMET/toxicidad desde el SMILES con modelos supervisados propios entrenados "
        "sobre datasets públicos (MoleculeNet: Tox21, BBBP, ESOL…). Cada endpoint trae su valor/ "
        "probabilidad y el ROC-AUC/RMSE del modelo en test (calidad predictiva). Son PREDICCIONES "
        "in silico, no medidas; cita el model_auc para transmitir la incertidumbre."
    ),
    "dti_gnn": (
        "Predicción de interacción fármaco-diana (DTI) con una red neuronal de grafos entrenada "
        "(GraphSAGE + pipeline de Link Prediction en Neo4j GDS). Cada predicción trae una "
        "probabilidad y el modelo reporta AUCPR/AP en test. Sugiere dianas NO documentadas como "
        "hipótesis de repurposing; no son interacciones confirmadas."
    ),
}

_STRUCTURE_SCIENTIFIC = """\
Redacta un INFORME CIENTÍFICO riguroso para un investigador/farmacólogo, con estas \
secciones (usa ## por sección; omite una sección solo si no hay datos para ella):
## Resumen ejecutivo
## Dianas moleculares y efecto directo
## Rutas biológicas afectadas y mecanismo plausible
## Efecto en cadena / propagación (si aplica)
## Riesgos y off-targets (si aplica)
## Limitaciones del análisis
## Descargo de responsabilidad (in-silico)
Sé preciso, técnico y cuantitativo (cita scores/FDR)."""

_STRUCTURE_EXECUTIVE = """\
Redacta un INFORME EJECUTIVO/DIVULGATIVO claro y accesible para una audiencia no \
especialista (p.ej. presentación de proyecto), con estas secciones (usa ## por \
sección; omite una sección solo si no hay datos):
## TL;DR (2-3 frases)
## Hallazgos clave
## Riesgos a vigilar
## Siguientes pasos sugeridos
## Descargo de responsabilidad (in-silico)
Minimiza la jerga; cuando uses un término técnico, explícalo en una frase. Aun así, \
no inventes datos: apóyate solo en lo provisto."""


def _build_prompt(kind: str, style: str, trimmed: dict) -> str:
    context = _KIND_CONTEXT.get(kind, "")
    structure = _STRUCTURE_SCIENTIFIC if style == "scientific" else _STRUCTURE_EXECUTIVE
    data_json = json.dumps(trimmed, ensure_ascii=False, indent=2, default=str)
    return (
        f"CONTEXTO DEL ANÁLISIS ({kind}):\n{context}\n\n"
        f"INSTRUCCIONES DE FORMATO:\n{structure}\n\n"
        f"DATOS DEL ANÁLISIS (única fuente permitida):\n```json\n{data_json}\n```\n\n"
        "Genera el informe siguiendo las reglas estrictas y la estructura indicada."
    )


def _title_for(kind: str, trimmed: dict) -> str:
    drug = trimmed.get("drug") or trimmed.get("compound") or {}
    name = (drug.get("name") if isinstance(drug, dict) else None) or ""
    labels = {
        "sandbox": "Informe de compuesto (Laboratorio Virtual)",
        "repurposing": "Informe de reposicionamiento",
        "toxicity": "Informe de toxicidad",
        "deg": "Informe de expresión diferencial",
        "ddi": "Informe de interacciones farmacológicas",
        "bioactivity": "Informe de bioactividad experimental",
        "denovo": "Informe de diseño de novo",
        "admet": "Informe de predicción ADMET",
        "dti_gnn": "Informe de predicción DTI (GNN)",
    }
    base = labels.get(kind, "Informe")
    return f"{base} — {name}".strip(" —") if name else base


# ══════════════════════════════════════════════════════════════════════════════
# 3. Persistencia en MongoDB
# ══════════════════════════════════════════════════════════════════════════════

def save_report(record: dict) -> str:
    db = get_db()
    db[REPORTS_COLLECTION].insert_one(record)
    return record["_id"]


def list_reports(user_id: str, limit: int = 50) -> list[dict]:
    db = get_db()
    cursor = (
        db[REPORTS_COLLECTION]
        .find(
            {"user_id": user_id},
            {"report_markdown": 0},  # lista ligera: sin el cuerpo completo
        )
        .sort("created_at", -1)
        .limit(limit)
    )
    out = []
    for doc in cursor:
        doc["report_id"] = doc.pop("_id")
        doc["created_at"] = _iso(doc.get("created_at"))
        out.append(doc)
    return out


def get_report(user_id: str, report_id: str) -> dict | None:
    db = get_db()
    doc = db[REPORTS_COLLECTION].find_one({"_id": report_id, "user_id": user_id})
    if not doc:
        return None
    doc["report_id"] = doc.pop("_id")
    doc["created_at"] = _iso(doc.get("created_at"))
    return doc


def delete_report(user_id: str, report_id: str) -> int:
    db = get_db()
    res = db[REPORTS_COLLECTION].delete_one({"_id": report_id, "user_id": user_id})
    return res.deleted_count


def _iso(value):
    if isinstance(value, _dt.datetime):
        return value.isoformat()
    return value


# ══════════════════════════════════════════════════════════════════════════════
# 4. Punto de entrada
# ══════════════════════════════════════════════════════════════════════════════

def build_report(
    kind: str,
    payload: dict,
    *,
    style: str = "scientific",
    model: str | None = None,
    user_id: str,
) -> dict:
    """
    Genera y persiste un informe. Devuelve el registro (con markdown).

    Lanza:
        ReportError                     — kind/style inválidos o payload vacío.
        gemini_service.GeminiUnavailable — Gemini no configurado (la vista → 503).
        gemini_service.GeminiError      — fallo de la API (la vista → 502).
    """
    if kind not in KINDS:
        raise ReportError(f"Tipo de análisis inválido: {kind}. Válidos: {KINDS}")
    if style not in STYLES:
        raise ReportError(f"Estilo inválido: {style}. Válidos: {STYLES}")
    if not isinstance(payload, dict) or not payload:
        raise ReportError("El campo 'payload' debe ser un objeto no vacío.")

    trimmed = _TRIMMERS[kind](payload)
    prompt = _build_prompt(kind, style, trimmed)
    resolved_model = gemini_service.resolve_model(model)

    markdown = gemini_service.generate(
        prompt,
        model=resolved_model,
        system_instruction=_SYSTEM_INSTRUCTION,
    )

    now = _dt.datetime.now(_dt.timezone.utc)
    record = {
        "_id": uuid.uuid4().hex,
        "user_id": user_id,
        "kind": kind,
        "style": style,
        "model": resolved_model,
        "title": _title_for(kind, trimmed),
        "input_summary": trimmed,
        "report_markdown": markdown,
        "created_at": now,
    }
    save_report(record)

    return {
        "report_id": record["_id"],
        "kind": kind,
        "style": style,
        "model": resolved_model,
        "title": record["title"],
        "report_markdown": markdown,
        "created_at": now.isoformat(),
    }
