"""
dossier_service.py — Informe integral de una molécula generado con Gemini (estructura fija).

Agrega TODO lo que la plataforma sabe de una molécula (propiedades, similitud, dianas documentadas
y predichas, efectos en cascada, rutas KEGG, enfermedades que afecta/podría tratar, especies de las
dianas) y lo envía a Gemini con un prompt de **estructura fija** (secciones definidas) + instrucción
de sistema anti-alucinación (usar solo el JSON provisto). El resultado es un informe Markdown
reproducible en secciones.

Requiere GEMINI_API_KEY (gemini_service). Degrada con available=False (→503) si no está.
"""
import json
import logging

log = logging.getLogger(__name__)

SYSTEM = """\
Eres un asistente científico de descubrimiento de fármacos. Redacta un INFORME en español a partir
EXCLUSIVAMENTE del JSON de datos que se te entrega (predicciones in silico de la plataforma
DrugGraph Open). Reglas estrictas:
- NO inventes genes, dianas, enfermedades, rutas, números ni especies que no estén en el JSON.
- Si una sección no tiene datos, escribe "Sin datos suficientes" — no rellenes con conocimiento externo.
- Marca todo como HIPÓTESIS in silico (no validación experimental).
- Sigue EXACTAMENTE la estructura de secciones pedida, con esos títulos, en Markdown.
- Sé conciso y técnico; usa viñetas y menciona los genes/scores concretos del JSON.
"""

SECTIONS = """\
Estructura OBLIGATORIA del informe (usa estos títulos H2 en Markdown):

## 1. Resumen e identidad
Qué es la molécula (fórmula, propiedades, drug-likeness) y su clase probable según sus vecinos.

## 2. A qué se parece (similitud)
Los fármacos estructuralmente más cercanos y qué implican.

## 3. Dianas y especies
Dianas documentadas y predichas (con gen y score). Indica la(s) especie(s) donde se encuentran las
dianas (campo `species`) y qué tan conservadas podrían estar (solo si el JSON lo indica).

## 4. Efectos en cascada
Genes/vías corriente abajo afectados (campo `cascade`), interpretando el efecto de red.

## 5. Rutas y pathways
Rutas KEGG/biológicas asociadas a las dianas (campo `pathways`).

## 6. Enfermedades que puede afectar
Enfermedades asociadas a las dianas de la molécula (contexto mecanístico).

## 7. Enfermedades que podría tratar (repurposing)
Hipótesis de reposicionamiento (campo `repurposing`), con su probabilidad.

## 8. Toxicidad y ADMET
Riesgos ADMET (BBBP, solubilidad) y toxicidad Tox21 (campos `admet`, `chemprop_toxicity`).

## 9. Docking estructural y selección de pose
Resultado del docking a la diana principal (campo `docking`): pose recomendada (RMSD + energía),
nº de ligandos conocidos de referencia. Interpreta el gráfico RMSD-vs-energía (la mejor pose es la
de abajo-izquierda). El gráfico se adjunta aparte.

## 10. Fármacos y efectos relacionados
Fármacos similares/co-dirigidos y efectos esperables por compartir dianas/rutas.

## 11. Conclusión y siguientes pasos
Síntesis honesta + qué validar (MD, ensayos). Recuerda el disclaimer in-silico.
"""


def _gather(query: str, include_docking: bool = True) -> dict:
    """Agrega los datos de la plataforma para la molécula."""
    from config.services import molecule_analysis_service as mas
    base = mas.build(query, include_network=True)
    if not base.get("available"):
        return base

    net = base.get("network", {})
    # Lista unificada de dianas (documentadas + predichas/consenso) con gen + uniprot.
    tgts = []
    for t in (net.get("documented_targets") or []):
        tgts.append({"gene": t.get("gene"), "uniprot": t.get("uniprot"), "name": t.get("name"), "kind": "documentada"})
    for t in (net.get("predicted_targets") or []):
        tgts.append({"gene": t.get("gene_name"), "uniprot": t.get("uniprot_id"), "name": t.get("target_name"),
                     "prob": t.get("probability"), "kind": "predicha"})
    for t in (net.get("consensus_targets") or []):
        tgts.append({"gene": t.get("gene"), "uniprot": t.get("uniprot"), "name": t.get("name"),
                     "shared": t.get("shared"), "kind": "consenso"})
    # dedup por gen
    seen, targets = set(), []
    for t in tgts:
        g = (t.get("gene") or "").upper()
        if g and g not in seen:
            seen.add(g); targets.append(t)

    genes = [t["gene"] for t in targets if t.get("gene")][:6]

    # KEGG pathways de las dianas
    pathways = {}
    try:
        from config.services.kegg_service import pathways_for_targets
        pk = pathways_for_targets([{"gene_name": t.get("gene"), "uniprot_id": t.get("uniprot")}
                                   for t in targets[:5] if t.get("gene")])
        pathways = pk if isinstance(pk, dict) else {}
    except Exception as exc:
        log.debug("dossier kegg error: %s", exc)

    # Cascada (difusión) desde las dianas
    cascade = []
    try:
        from config.services import propagation_service
        c = propagation_service.propagate(genes, top_n=10)
        cascade = c.get("results", c) if isinstance(c, dict) else c
    except Exception as exc:
        log.debug("dossier cascade error: %s", exc)

    # Especie de las dianas (organism en Neo4j)
    species = []
    try:
        from config.services.neo4j_service import _session
        with _session() as s:
            species = [r["org"] for r in s.run(
                "MATCH (t:Target) WHERE t.organism IS NOT NULL RETURN DISTINCT t.organism AS org LIMIT 5").data()]
    except Exception:
        pass

    smiles = base.get("smiles")

    # Toxicidad GNN (Chemprop) — todo el servicio
    chemprop_tox = None
    try:
        from config.services import chemprop_service
        ct = chemprop_service.predict(smiles)
        if ct.get("available"):
            chemprop_tox = [{"assay": p["assay"], "prob": p["probability"]} for p in ct.get("predictions", [])[:6]]
    except Exception as exc:
        log.debug("dossier chemprop error: %s", exc)

    # Docking + FUNNEL (RMSD vs poses) contra la diana principal con UniProt
    docking = None
    funnel_plot = None
    try:
        from config.services import docking_service as dsv
        if include_docking and dsv.DOCKING_OK:
            top = next((t for t in targets if t.get("uniprot")), None)
            if top:
                fn = dsv.pose_funnel(smiles, target=dsv.ensure_receptor(top["uniprot"], name=top.get("gene", "")),
                                     exhaustiveness=6)
                if fn.get("available"):
                    funnel_plot = fn.get("plot_png")
                    docking = {"target_gene": top.get("gene"), "uniprot": top.get("uniprot"),
                               "recommended_pose": fn.get("recommended_pose"),
                               "n_reference_actives": fn.get("n_reference_actives"),
                               "poses": fn.get("points")}
    except Exception as exc:
        log.debug("dossier docking/funnel error: %s", exc)

    return {
        "available": True, "smiles": smiles, "drug_id": base.get("drug_id"),
        "properties": base.get("properties"), "neighbors": base.get("neighbors"),
        "pharmacophore_families": (base.get("pharmacophore") or {}).get("feature_counts"),
        "chemical_space": base.get("chemical_space"),
        "admet": (base.get("admet") or {}).get("predictions") if isinstance(base.get("admet"), dict) else base.get("admet"),
        "chemprop_toxicity": chemprop_tox,
        "targets": targets[:12], "pathways": pathways,
        "cascade": cascade, "repurposing": net.get("repurposing") or net.get("consensus_diseases"),
        "docking": docking, "species": species,
        "_funnel_plot": funnel_plot,   # imagen, no va al prompt de Gemini (se muestra aparte)
        "note_homology": "Homología cross-especies: ver Tier de homología (uso veterinario).",
    }


def build(query: str, style: str = "scientific", model: str | None = None,
          include_docking: bool = True) -> dict:
    """Genera el informe integral con Gemini. Degrada 503 si Gemini/datos no están."""
    from config.services import gemini_service
    if not gemini_service.is_configured():
        return {"available": False,
                "reason": "GEMINI_API_KEY no configurada — pon tu key en backend/.env (GEMINI_API_KEY=...)."}

    data = _gather(query, include_docking=include_docking)
    if not data.get("available"):
        return {"available": False, "reason": data.get("reason", "Sin datos para la molécula.")}

    funnel_plot = data.pop("_funnel_plot", None)   # imagen: no va al prompt del LLM
    prompt = (f"{SECTIONS}\n\nDATOS (JSON) de la molécula:\n```json\n"
              f"{json.dumps(data, ensure_ascii=False, default=str)[:14000]}\n```\n"
              f"Estilo de redacción: {style}.")
    try:
        report_md = gemini_service.generate(prompt, model=model, system_instruction=SYSTEM,
                                            temperature=0.2)
    except gemini_service.GeminiUnavailable as exc:
        return {"available": False, "reason": str(exc)}
    except Exception as exc:
        log.error("dossier gemini error: %s", exc)
        return {"available": False, "reason": f"Error de Gemini: {exc}"}

    return {"available": True, "query": query, "drug_id": data.get("drug_id"),
            "smiles": data.get("smiles"), "report_markdown": report_md,
            "funnel_plot": funnel_plot, "data_used": data,
            "model": gemini_service.resolve_model(model),
            "disclaimer": "Informe generado por IA a partir de predicciones in silico; hipótesis, "
                          "no validación experimental."}
