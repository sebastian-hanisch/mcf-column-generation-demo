"""Jede Zahl, die README und Hilfetexte nennen, ist hier belegt (Standardeinstellungen, 100 feste Netze, Seeds 100000-100099).
Netz-, Pfad- und Variablenzahlen sind ganzzahlig und exakt; Runden, Spalten und Iterationen hängen vom LP-Löser ab (degenerierte Duallösungen) und werden mit Bändern geprüft."""

import pytest

import mcg_constants as C
import mcg_evaluation as ev
import mcg_model as md
import mcg_paths as pa

P = ev.DEFAULT_PARAMS
GRID = P._replace(net="grid", k=4)


@pytest.fixture(scope="module")
def dist():
    return ev.distribution(P)


@pytest.fixture(scope="module")
def gdist():
    return ev.distribution(GRID)


def _paths(params, n):
    total = []
    for seed in C.DIST_SEEDS[:n]:
        mcf = ev.build(ev.with_seed(params, seed))
        counts = [pa.count_paths(mcf, k, 10 ** 6, 3 * 10 ** 7) for k in range(mcf.K)]
        assert all(exact for _, exact in counts)
        total.append(sum(c for c, _ in counts))
    return total


def test_column_generation_always_ends_in_the_edge_lp_optimum():
    """0 Abweichungen in 100 + 100 Netzen für 2, 3, 4 und 5 Güter - im Distributionsnetz und im Streckennetz."""
    for base in (P, GRID):
        for K in (2, 3, 4, 5):
            d = ev.distribution(base._replace(k=K))
            assert d["share_exact"] == 1.0 and d["n_seeds"] == 100 and d["share_stuck"] == 0.0


def test_columns_against_variables_and_paths(dist, gdist):
    """Distributionsnetz (drei Güter): 103 Variablen, 52,1 mögliche Pfade (17 bis 111), im Mittel etwa 28 Spalten, etwa 21 mit Fluss. Streckennetz 5x4 (vier Güter): 252 Variablen, 494 mögliche Pfade (30 bis 2666), etwa 14 Spalten, etwa 6 mit Fluss."""
    assert round(dist["vars_mean"]) == 103 and round(gdist["vars_mean"]) == 252
    assert 26 <= dist["columns_mean"] <= 31 and 19 <= dist["used_mean"] <= 23 and 12 <= gdist["columns_mean"] <= 17 and 5 <= gdist["used_mean"] <= 7.5
    d, g = _paths(P, 100), _paths(GRID, 100)
    assert (round(sum(d) / 100, 1), min(d), max(d)) == (52.1, 17, 111) and (round(sum(g) / 100, 2), min(g), max(g)) == (493.96, 30, 2666)


def test_rounds_by_number_of_goods():
    """Etwa 11 Runden im Distributionsnetz (2 / 3 / 4 / 5 Güter: etwa 11,1 / 11,4 / 10,9 / 10,3) und etwa 5 im Streckennetz (4,3 / 4,5 / 4,9 / 5,2); die Spalten wachsen mit K, die Runden nicht."""
    dr = [ev.distribution(P._replace(k=K)) for K in (2, 3, 4, 5)]
    gr = [ev.distribution(GRID._replace(k=K)) for K in (2, 3, 4, 5)]
    assert all(9.5 <= d["rounds_mean"] <= 13 for d in dr) and all(3.6 <= d["rounds_mean"] <= 6.2 for d in gr)
    assert [d["columns_mean"] for d in dr] == sorted(d["columns_mean"] for d in dr) and [d["columns_mean"] for d in gr] == sorted(d["columns_mean"] for d in gr)
    assert [round(d["vars_mean"]) for d in dr] == [69, 103, 137, 172] and [round(d["vars_mean"]) for d in gr] == [118, 183, 252, 325]


def test_first_round_delivers_little(dist):
    """Nach dem ersten Pricing (jedes Gut allein) liefert der Master im Mittel erst etwa 9,8 von 64,3 Einheiten des Optimums."""
    assert round(dist["lp_delivered_mean"], 2) == 64.31 and round(dist["demand_mean"], 2) == 75.83
    assert 8 <= dist["first_delivered_mean"] <= 12


def test_iterations_against_the_edge_lp(dist, gdist):
    """Distributionsnetz: die Column Generation braucht mit allen Runden mehr Simplex-Iterationen als das Kanten-LP (etwa 81 gegen 23); im kleinen Streckennetz weniger (etwa 25 gegen 74)."""
    assert dist["cg_iterations_mean"] > 2 * dist["lp_iterations_mean"]
    assert gdist["cg_iterations_mean"] < 0.6 * gdist["lp_iterations_mean"]


def test_the_gap_closes_late_not_early(dist):
    """Kein Tailing-off: die 5-%-Lücke steht erst nach etwa 87 % der Runden (Distributionsnetz, 9,9 von 11,4), die 1-%-Lücke nach etwa 88 %; bis zum Optimum sind es 11,4."""
    n = dist["n_seeds"]
    r = {tol: sum(dist["gap_rounds"][tol]) / n for tol in (0.05, 0.01, 0.001, 0.0)}
    assert r[0.05] <= r[0.01] <= r[0.001] <= r[0.0] and r[0.05] / dist["rounds_mean"] > 0.8 and r[0.0] == pytest.approx(dist["rounds_mean"], abs=1e-9)
    assert r[0.01] / dist["rounds_mean"] > 0.85 and r[0.001] / dist["rounds_mean"] > 0.93


def test_option_results():
    """Alle Güter je Runde etwa 11,4 Runden, nur der beste Pfad etwa 26; Start aus Nacheinander etwa 5,5; Glättung hilft nicht (etwa 11,8 bzw. 12,3) und sieht mehr Kanten an; ohne die Preise der Gut-Obergrenzen 0 % im Optimum (Distributionsnetz) bzw. etwa 20 % (Streckennetz)."""
    for params, neg_low, neg_high in ((P, 0.0, 0.0), (GRID, 0.1, 0.3)):
        base, one, warm, a5, a8, neg = ev.options_table(params)
        assert one["rounds"] > 2 * base["rounds"] * 0.9 and warm["rounds"] < 0.75 * base["rounds"]
        assert a5["rounds"] >= base["rounds"] - 0.3 and a8["rounds"] >= base["rounds"] - 0.3 and a5["scans"] > 1.2 * base["scans"] and a8["scans"] > 1.2 * base["scans"]
        assert base["exact"] == one["exact"] == warm["exact"] == a5["exact"] == a8["exact"] == 1.0 and neg_low <= neg["exact"] <= neg_high
        assert neg["stuck"] >= 1 - neg_high - 0.01 and a5["misprices"] < 0.1 and a8["misprices"] < 0.1
    base, one, warm, a5, a8, neg = ev.options_table(P)
    assert 24 <= one["rounds"] <= 29 and 4.5 <= warm["rounds"] <= 7 and 10 <= base["rounds"] <= 13
    assert one["columns"] < base["columns"] and abs(warm["columns"] - base["columns"]) < 3 and abs(warm["iterations"] - base["iterations"]) < 0.2 * base["iterations"]
    assert 1.7 < a5["scans"] / base["scans"] < 2.3 and 1.7 < a8["scans"] / base["scans"] < 2.3 and neg["rounds"] <= 2


def test_path_table():
    """Volle Gitter mit drei Gütern (5 feste Netze je Größe): 3x3 28, 4x3 74, 5x4 1768, 6x4 8725, 6x5 142 473 mögliche Pfade - exakt gezählt; die Spalten bleiben bei etwa 10 bis 16, davon etwa 6 mit Fluss."""
    rows = ev.path_table()
    assert all(r["exact"] for r in rows) and [round(r["paths"]) for r in rows] == [28, 74, 1768, 8725, 142473] and [r["vars"] for r in rows] == [90, 120, 204, 246, 312]
    assert all(9 <= r["columns"] <= 18 and 4.5 <= r["used"] <= 8 for r in rows) and rows[-1]["paths"] > 5000 * rows[-1]["columns"]


def test_size_table():
    """Volle Gitter mit fünf Gütern (6 feste Netze je Größe): die Spalten sind ein Bruchteil der Variablen (6 % bei 5x4, 4 % bei 16x10), die Runden wachsen mit der Größe (etwa 6 auf 34); Simplex-Iterationen gesamt: bei 5x4 weniger als das Kanten-LP (etwa 57 gegen 117), ab 8x6 mehr (etwa 500 gegen 238, bei 16x10 etwa 2650 gegen 730)."""
    rows = ev.size_table()
    assert all(r["exact"] for r in rows) and [round(r["vars"]) for r in rows] == [360, 870, 1090, 1770, 2990]
    assert all(r["columns"] / r["vars"] < 0.08 for r in rows) and rows[-1]["columns"] / rows[-1]["vars"] < 0.05
    assert rows[-1]["rounds"] > 3 * rows[0]["rounds"] and rows[0]["cg_iterations"] < 0.8 * rows[0]["lp_iterations"]
    assert all(r["cg_iterations"] > 1.5 * r["lp_iterations"] for r in rows[1:]) and rows[-1]["cg_iterations"] > 2.5 * rows[-1]["lp_iterations"]
    assert all(r["t_cg"] > r["t_lp"] for r in rows)                                                        # nur zur Information, aber in jeder Größe langsamer


def test_seed_155_numbers():
    """Beispielnetz (Seed 155, drei Güter): 67 von 76 Einheiten für 1548, 114 Variablen, 79 mögliche Pfade, etwa 14 Runden mit etwa 31 Spalten (etwa 20 mit Fluss), 5 bindende Kanten; erste Runde etwa 9 Einheiten. Start aus Nacheinander: etwa 6 Runden, erste Runde schon 67 Einheiten (= Nacheinander)."""
    a = ev.analyse(P)
    _, code, d = ev.verdict(a)
    assert (code, d["lp_delivered"], d["demand"], d["lp_cost"], d["lp_vars"], d["paths"], d["n_binding"]) == ("optimal", 67.0, 76, 1548.0, 114, 79, 5)
    assert 11 <= d["rounds"] <= 17 and 28 <= d["columns"] <= 34 and 17 <= d["used"] <= 23 and 7 <= d["first_delivered"] <= 12
    w = ev.verdict(ev.analyse(P, ev.DEFAULT_OPTS._replace(start="nacheinander")))[2]
    assert w["rounds"] <= 8 and w["first_delivered"] == pytest.approx(67.0)
    n = ev.verdict(ev.analyse(P, ev.DEFAULT_OPTS._replace(ignore_mu=True)))[2]
    assert n["cg_delivered"] < 30 and n["lp_delivered"] - n["cg_delivered"] > 30


def test_the_streckennetz_and_teaching_nets():
    """Streckennetz (5x4, 4 Güter, Seed 7): 7 von 12 Einheiten für 105, 256 Variablen, 242 mögliche Pfade. Preis-Wende: 2 Runden, Preis 3 an der Direktstrecke; Runde 1 liefert nur 1 Einheit und der Preis liegt nahe M. Frachtnetz mit Bruch: 1,5 Einheiten für 24, 4 Pfade, gebrochene Pfadmengen."""
    _, code, d = ev.verdict(ev.analyse(GRID))
    assert (code, d["lp_delivered"], d["demand"], d["lp_cost"], d["lp_vars"], d["paths"]) == ("optimal", 7.0, 12, 105.0, 256, 242)
    pr = ev.analyse(ev.normalise(P._replace(net="preis")))
    assert pr.cg.n_rounds == 2 and pr.cg.rounds[1].lam[0] > 900 and abs(pr.cg.rounds[-1].lam[0] - 3.0) < 1e-6 and sum(pr.cg.rounds[1].delivered) == pytest.approx(1.0)
    gp = ev.analyse(ev.normalise(P._replace(net="gap")))
    _, code, d = ev.verdict(gp)
    assert (d["cg_delivered"], d["cg_cost"], d["paths"], d["fractional"]) == (1.5, 24.0, 4, True) and any(abs(x - round(x)) > 1e-6 for x in gp.cg.amounts)


def test_dense_streckennetz_preset():
    """Volles Gitter 8x5, fünf Güter (Seed 7): 720 Variablen, mindestens 28 000 mögliche Pfade (die Zählung bricht ab), etwa 32 Spalten mit etwa 9 mit Fluss in etwa 12 Runden."""
    p = C.PRESETS["🕸️ Dichtes Streckennetz"]
    params = ev.NetParams("grid", p["k"], p["p"], p["d"], p["s"], p["density"], p["spread"], p["load"], p["seed"], p["gw"], p["gh"], p["gdensity"], p["gcap"], p["gdem"], p["gseed"])
    d = ev.verdict(ev.analyse(params))[2]
    assert d["lp_vars"] == 720 and not d["paths_exact"] and d["paths"] >= 20000 and d["columns"] <= 45 and 7 <= d["used"] <= 12 and 8 <= d["rounds"] <= 16
    assert (d["lp_delivered"], d["demand"], d["lp_cost"]) == (10.0, 11, 239.0) and d["paths"] >= 28000
