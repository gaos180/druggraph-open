#!/usr/bin/env python3
"""
eval_docking.py — Validación del protocolo de docking (Tier 5.3, puerta de calidad).

Antes de confiar en los scores de docking hay que probar que el montaje (receptor + caja +
parámetros) distingue de verdad los inhibidores conocidos de los no-unidores. Protocolo estándar
de virtual screening:

  - ACTIVOS: inhibidores medidos de la diana (ChEMBL, pChEMBL ≥ umbral).
  - DECOYS: moléculas drug-like presuntamente no-unidoras, muestreadas del catálogo con MW
    similar a los activos (aprox. DUD-E; DUD-E no tiene NDM-1).
  - Se acoplan todos al receptor preparado y se mide si los activos sacan mejor afinidad:
    **ROC-AUC** y **Enrichment Factor (EF@1%, EF@5%)**.

Optimización: los mapas de Vina se calculan UNA vez por receptor y se reutilizan para todos los
ligandos (mismo patrón que usará el cribado batch). Salida en dataset_testing/docking/.
"""
import argparse
import csv
import json
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import numpy as np
import requests
from rdkit import Chem
from rdkit.Chem import Descriptors, AllChem
from sklearn.metrics import roc_auc_score, roc_curve
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.services import docking_service as dsv

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "dataset_testing", "docking")
NDM_TARGETS = ["CHEMBL4295540", "CHEMBL4295642", "CHEMBL1667695", "CHEMBL5465386"]


def _fetch_actives(chembl_targets, pchembl, cache):
    if os.path.exists(cache):
        return [l.strip() for l in open(cache) if l.strip()]
    smi = set()
    for t in chembl_targets:
        r = requests.get("https://www.ebi.ac.uk/chembl/api/data/activity",
                         params={"target_chembl_id": t, "pchembl_value__gte": pchembl,
                                 "limit": 1000, "format": "json"}, timeout=90)
        for a in r.json().get("activities", []):
            s = a.get("canonical_smiles")
            if s and Chem.MolFromSmiles(s):
                smi.add(s)
    with open(cache, "w") as fh:
        fh.write("\n".join(sorted(smi)))
    return sorted(smi)


def _sample_decoys(n, mw_lo, mw_hi, exclude):
    """Muestrea SMILES del catálogo con MW en [mw_lo, mw_hi] como no-unidores presuntos."""
    from config.services.mongo import get_db
    db = get_db()
    out, seen = [], set(exclude)
    cur = db.drugs.find({"smiles": {"$exists": True, "$ne": ""}}, {"smiles": 1}).limit(5000)
    rows = [d["smiles"] for d in cur if d.get("smiles")]
    import random
    random.Random(7).shuffle(rows)
    for s in rows:
        if s in seen:
            continue
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        mw = Descriptors.MolWt(m)
        if mw_lo <= mw <= mw_hi:
            out.append(s); seen.add(s)
        if len(out) >= n:
            break
    return out


def _dock_many(smiles_list, target, exhaustiveness):
    """Calcula los mapas de Vina UNA vez y acopla todos los ligandos. Devuelve {smiles: afinidad}."""
    from vina import Vina
    rec_path, box = dsv._receptor_paths(target)
    v = Vina(sf_name="vina", verbosity=0)
    v.set_receptor(rec_path)
    v.compute_vina_maps(center=box["center"], box_size=box["box_size"])
    res = {}
    for i, smi in enumerate(smiles_list):
        try:
            lig = dsv.prepare_ligand_pdbqt(smi)
            v.set_ligand_from_string(lig)
            v.dock(exhaustiveness=exhaustiveness, n_poses=1)
            res[smi] = round(float(v.energies(n_poses=1)[0][0]), 2)
        except Exception:
            res[smi] = None
        if (i + 1) % 20 == 0:
            print(f"  … {i+1}/{len(smiles_list)} acoplados")
    return res


def _enrichment(labels, scores, frac):
    """EF@frac: (activos en el top frac) / (activos esperados por azar)."""
    order = np.argsort(scores)          # más negativo = mejor → orden ascendente
    n = len(labels); k = max(1, int(n * frac))
    top = order[:k]
    n_act = int(np.sum(labels))
    if n_act == 0:
        return 0.0
    hit = int(np.sum(np.array(labels)[top]))
    return round((hit / k) / (n_act / n), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="ndm1", help="receptor preparado (models/docking/<target>)")
    ap.add_argument("--pchembl", type=float, default=5.0)
    ap.add_argument("--n-actives", type=int, default=30)
    ap.add_argument("--n-decoys", type=int, default=60)
    ap.add_argument("--exhaustiveness", type=int, default=8)
    args = ap.parse_args()

    if not dsv.DOCKING_OK:
        raise SystemExit("Docking no disponible (vina/meeko/openbabel).")
    os.makedirs(OUT, exist_ok=True)

    import random
    actives = _fetch_actives(NDM_TARGETS, args.pchembl, os.path.join(OUT, "actives_chembl.smi"))
    random.Random(7).shuffle(actives)
    actives = actives[: args.n_actives]
    mws = [Descriptors.MolWt(Chem.MolFromSmiles(s)) for s in actives]
    decoys = _sample_decoys(args.n_decoys, min(mws) - 50, max(mws) + 50, set(actives))
    print(f"Activos: {len(actives)} | decoys: {len(decoys)} | acoplando a '{args.target}'…")

    all_smi = actives + decoys
    labels = [1] * len(actives) + [0] * len(decoys)
    scores = _dock_many(all_smi, args.target, args.exhaustiveness)

    rows, y, s = [], [], []
    for smi, lab in zip(all_smi, labels):
        aff = scores.get(smi)
        rows.append([smi, "active" if lab else "decoy", "" if aff is None else aff])
        if aff is not None:
            y.append(lab); s.append(aff)

    with open(os.path.join(OUT, f"{args.target}_validation.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["smiles", "class", "affinity_kcal_mol"]); w.writerows(rows)

    # ROC/EF: score de ranking = -afinidad (más alto = mejor unión)
    rank = [-a for a in s]
    roc = float(roc_auc_score(y, rank)) if len(set(y)) == 2 else None
    ef1 = _enrichment(y, s, 0.01); ef5 = _enrichment(y, s, 0.05)
    metrics = {"target": args.target, "n_actives_docked": int(sum(y)),
               "n_decoys_docked": int(len(y) - sum(y)), "roc_auc": None if roc is None else round(roc, 4),
               "EF_1pct": ef1, "EF_5pct": ef5,
               "mean_affinity_active": round(float(np.mean([a for a, l in zip(s, y) if l])), 2),
               "mean_affinity_decoy": round(float(np.mean([a for a, l in zip(s, y) if not l])), 2)}
    with open(os.path.join(OUT, f"{args.target}_metrics.json"), "w") as fh:
        json.dump(metrics, fh, indent=2, ensure_ascii=False)

    # plots: ROC + distribución de afinidades
    fig, ax = plt.subplots(1, 2, figsize=(9, 4))
    if roc is not None:
        fpr, tpr, _ = roc_curve(y, rank)
        ax[0].plot(fpr, tpr, label=f"AUC={roc:.3f}"); ax[0].plot([0, 1], [0, 1], "k--", lw=0.7)
    ax[0].set_title(f"Docking ROC — {args.target}"); ax[0].set_xlabel("FPR"); ax[0].set_ylabel("TPR"); ax[0].legend()
    act = [a for a, l in zip(s, y) if l]; dec = [a for a, l in zip(s, y) if not l]
    ax[1].hist(dec, bins=20, alpha=0.5, label="decoys", color="gray")
    ax[1].hist(act, bins=20, alpha=0.6, label="activos", color="crimson")
    ax[1].set_title("Afinidad (kcal/mol)"); ax[1].set_xlabel("kcal/mol"); ax[1].legend()
    fig.tight_layout(); fig.savefig(os.path.join(OUT, f"{args.target}_validation.png"), dpi=110); plt.close(fig)

    print(f"[docking-eval] {metrics}")


if __name__ == "__main__":
    main()
