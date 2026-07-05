"""
test_ingest_transforms.py — Tests de las transformaciones PURAS del pipeline de
ingesta y de los helpers deterministas de los servicios de análisis.

Todo lo que se prueba aquí es SIN base de datos: normalizadores de CID, derivación
de signo de acción, estadística del modelo nulo de proximidad, binning de grado y el
Jaccard ponderado del reposicionamiento. Donde una función recibe una `session` de
Neo4j, se le pasa un DOBLE (mock) que devuelve conteos fijos — nunca se toca Neo4j.

Ejecutar:
    ./venv/bin/python manage.py test drugs.test_ingest_transforms -v 2
"""
import math

from django.test import SimpleTestCase

# Transformaciones de ingesta (fichero→fichero, sin BD)
from scripts.ingest.step04_ddi_open import _norm_cid
from scripts.ingest.prepare_ddi_stitch import stitch_to_cid

# Helpers deterministas de los servicios de análisis
from config.services.propagation_service import sign_for_action
from config.services.proximity_service import _zscore_pvalue, _degree_bins
from drugs.views.tools.repurposing import _weighted_jaccard, _specificity_weights


# ═════════════════════════════════════════════════════════════════════════════
# 1) Normalización de CIDs (step04_ddi_open._norm_cid)
# ═════════════════════════════════════════════════════════════════════════════
class NormCidTests(SimpleTestCase):
    def test_stitch_stereo_prefix(self):
        self.assertEqual(_norm_cid("CIDs00012345"), "12345")

    def test_stitch_flat_prefix(self):
        self.assertEqual(_norm_cid("CIDm12345"), "12345")

    def test_leading_zeros_collapsed(self):
        self.assertEqual(_norm_cid("000012345"), "12345")

    def test_plain_cid_no_prefix(self):
        self.assertEqual(_norm_cid("CID000123"), "123")

    def test_integer_input(self):
        self.assertEqual(_norm_cid(12345), "12345")

    def test_case_insensitive_prefix(self):
        self.assertEqual(_norm_cid("cids0007"), "7")

    def test_none_returns_none(self):
        self.assertIsNone(_norm_cid(None))

    def test_empty_returns_none(self):
        self.assertIsNone(_norm_cid("   "))

    def test_no_digits_returns_none(self):
        self.assertIsNone(_norm_cid("abc"))


# ═════════════════════════════════════════════════════════════════════════════
# 2) Normalización STITCH→CID (prepare_ddi_stitch.stitch_to_cid)
#    Misma semántica que _norm_cid; verificada contra la firma real del módulo.
# ═════════════════════════════════════════════════════════════════════════════
class StitchToCidTests(SimpleTestCase):
    def test_stereo_prefix(self):
        self.assertEqual(stitch_to_cid("CIDs00012345"), "12345")

    def test_flat_prefix(self):
        self.assertEqual(stitch_to_cid("CIDm12345"), "12345")

    def test_leading_zeros(self):
        self.assertEqual(stitch_to_cid("0000042"), "42")

    def test_plain_integer_string(self):
        self.assertEqual(stitch_to_cid("42"), "42")

    def test_none(self):
        self.assertIsNone(stitch_to_cid(None))

    def test_empty(self):
        self.assertIsNone(stitch_to_cid(""))

    def test_garbage(self):
        self.assertIsNone(stitch_to_cid("N/A"))


# ═════════════════════════════════════════════════════════════════════════════
# 3) Signo de acción del fármaco (propagation_service.sign_for_action)
# ═════════════════════════════════════════════════════════════════════════════
class SignForActionTests(SimpleTestCase):
    def test_inhibitor_negative(self):
        self.assertEqual(sign_for_action("inhibitor"), -1)

    def test_antagonist_negative(self):
        self.assertEqual(sign_for_action("antagonist"), -1)

    def test_agonist_positive(self):
        self.assertEqual(sign_for_action("agonist"), 1)

    def test_activator_positive(self):
        self.assertEqual(sign_for_action("activator"), 1)

    def test_case_and_whitespace_insensitive(self):
        self.assertEqual(sign_for_action("  Inhibitor "), -1)
        self.assertEqual(sign_for_action("AGONIST"), 1)

    def test_list_of_actions_consistent(self):
        self.assertEqual(sign_for_action(["inhibitor", "blocker"]), -1)
        self.assertEqual(sign_for_action(["agonist", "inducer"]), 1)

    def test_mixed_signs_ambiguous(self):
        self.assertIsNone(sign_for_action(["inhibitor", "agonist"]))

    def test_unknown_action(self):
        # "modulator" a secas no está en ninguno de los dos conjuntos.
        self.assertIsNone(sign_for_action("modulator"))

    def test_empty_and_none(self):
        self.assertIsNone(sign_for_action(None))
        self.assertIsNone(sign_for_action(""))
        self.assertIsNone(sign_for_action([]))


# ═════════════════════════════════════════════════════════════════════════════
# 4) Estadística del modelo nulo de proximidad (proximity_service._zscore_pvalue)
# ═════════════════════════════════════════════════════════════════════════════
class ZScorePValueTests(SimpleTestCase):
    def test_observed_much_smaller_than_null(self):
        # d_obs (2) muy por debajo del nulo (~10) ⇒ z<0 y p empírico bajo.
        null_vals = [10, 9, 11, 10, 12, 9, 10, 11, 10, 9,
                     11, 10, 12, 9, 10, 11, 10, 9, 11, 10]
        z, p, mu, sd = _zscore_pvalue(2.0, null_vals)
        self.assertIsNotNone(z)
        self.assertLess(z, 0)                 # cercanía significativa
        self.assertLess(p, 0.1)               # p-valor bajo (una cola)
        self.assertAlmostEqual(mu, 10.15, places=1)
        self.assertGreater(sd, 0)

    def test_pvalue_never_zero(self):
        # Aun con d_obs por debajo de todo el nulo, el p empírico usa +1/+1 (nunca 0).
        z, p, mu, sd = _zscore_pvalue(0.0, [5, 6, 7, 8])
        self.assertGreater(p, 0)
        self.assertAlmostEqual(p, 1 / 5, places=4)

    def test_none_observed(self):
        self.assertEqual(_zscore_pvalue(None, [1, 2, 3]), (None, None, None, None))

    def test_insufficient_null(self):
        # < 2 valores nulos válidos ⇒ no se puede estimar.
        self.assertEqual(_zscore_pvalue(1.0, [5]), (None, None, None, None))
        self.assertEqual(_zscore_pvalue(1.0, [None, None]), (None, None, None, None))

    def test_zero_variance_null_gives_zero_z(self):
        z, p, mu, sd = _zscore_pvalue(4.0, [4, 4, 4, 4])
        self.assertEqual(z, 0.0)
        self.assertEqual(sd, 0.0)


# ═════════════════════════════════════════════════════════════════════════════
# 5) Binning de grado para el muestreo emparejado (proximity_service._degree_bins)
# ═════════════════════════════════════════════════════════════════════════════
class DegreeBinsTests(SimpleTestCase):
    def test_all_genes_assigned_and_min_size(self):
        degrees = {f"g{i}": i for i in range(10)}   # grados distintos 0..9
        bins = _degree_bins(degrees, bin_min=3)
        # todos los genes reciben un bin
        self.assertEqual(set(bins), set(degrees))
        # ningún bin queda por debajo del mínimo (el último se fusiona)
        for genes in bins.values():
            self.assertGreaterEqual(len(genes), 3)

    def test_last_undersized_bin_merged(self):
        # 10 genes, bin_min=3 ⇒ bins [0,3)[3,6)[6,9) y un resto de 1 que se fusiona
        # con el anterior ⇒ el último bin tiene 4 genes.
        degrees = {f"g{i}": i for i in range(10)}
        bins = _degree_bins(degrees, bin_min=3)
        sizes = {len(v) for v in bins.values()}
        self.assertIn(4, sizes)   # bin fusionado

    def test_same_degree_not_split_across_bins(self):
        # a,b,c comparten grado 1: deben caer en el MISMO bin aunque el corte
        # nominal (bin_min=2) los partiría.
        degrees = {"a": 1, "b": 1, "c": 1, "d": 2, "e": 3}
        bins = _degree_bins(degrees, bin_min=2)
        self.assertEqual(set(bins["a"]), set(bins["b"]))
        self.assertEqual(set(bins["b"]), set(bins["c"]))
        # d y e quedan en el mismo bin (segundo), separados de los de grado 1
        self.assertNotIn("a", bins["d"])


# ═════════════════════════════════════════════════════════════════════════════
# 6) Reposicionamiento — Jaccard ponderado y pesos de especificidad
#    (repurposing._weighted_jaccard, _specificity_weights con session mock)
# ═════════════════════════════════════════════════════════════════════════════
class _FakeResult:
    """Doble de un resultado Neo4j: iterable + .single()."""

    def __init__(self, rows):
        self._rows = list(rows)

    def __iter__(self):
        return iter(self._rows)

    def single(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Doble de sesión Neo4j: devuelve resultados fijos en el orden de llamada.

    _specificity_weights hace exactamente 2 llamadas a session.run():
      1) conteo de fármacos por gen (se itera)
      2) tamaño del corpus N (se toma .single()["n"])
    """

    def __init__(self, gene_counts, n_total):
        self._results = [
            _FakeResult([{"gene": g, "drugs": c} for g, c in gene_counts.items()]),
            _FakeResult([{"n": n_total}]),
        ]
        self._i = 0

    def run(self, *args, **kwargs):
        res = self._results[self._i]
        self._i += 1
        return res


class WeightedJaccardTests(SimpleTestCase):
    def test_ratio_of_weights(self):
        w = {"A": 2.0, "B": 3.0, "C": 5.0}
        inter = {"A", "B"}
        union = {"A", "B", "C"}
        # (2+3) / (2+3+5) = 0.5
        self.assertAlmostEqual(_weighted_jaccard(inter, union, w), 0.5)

    def test_missing_weight_defaults_to_one(self):
        # genes sin peso conocido cuentan como 1.0
        w = {"A": 4.0}
        self.assertAlmostEqual(
            _weighted_jaccard({"A", "X"}, {"A", "X", "Y"}, w),
            (4.0 + 1.0) / (4.0 + 1.0 + 1.0),
        )

    def test_empty_union_is_zero(self):
        self.assertEqual(_weighted_jaccard(set(), set(), {}), 0.0)

    def test_equal_sets_are_one(self):
        w = {"A": 2.0, "B": 7.0}
        self.assertAlmostEqual(_weighted_jaccard({"A", "B"}, {"A", "B"}, w), 1.0)


class SpecificityWeightsTests(SimpleTestCase):
    def test_idf_formula_with_mock_session(self):
        # N=500 fármacos con diana. G1 raro (2 fármacos), G2 promiscuo (100).
        session = _FakeSession(gene_counts={"G1": 2, "G2": 100}, n_total=500)
        weights = _specificity_weights(session, {"G1", "G2"})
        self.assertAlmostEqual(weights["G1"], math.log2(501 / 3))
        self.assertAlmostEqual(weights["G2"], math.log2(501 / 101))
        # La diana rara pesa MÁS que la promiscua (mayor contenido de información).
        self.assertGreater(weights["G1"], weights["G2"])

    def test_gene_absent_from_counts_uses_zero(self):
        # G3 no aparece en el conteo ⇒ n_g=0 ⇒ log2((N+1)/1), el peso máximo.
        session = _FakeSession(gene_counts={"G1": 2}, n_total=500)
        weights = _specificity_weights(session, {"G1", "G3"})
        self.assertAlmostEqual(weights["G3"], math.log2(501 / 1))
        self.assertGreater(weights["G3"], weights["G1"])

    def test_empty_genes_short_circuits(self):
        # Sin genes no debe consultar la sesión en absoluto.
        session = _FakeSession(gene_counts={}, n_total=0)
        self.assertEqual(_specificity_weights(session, set()), {})
