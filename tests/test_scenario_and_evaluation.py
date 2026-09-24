"""Auswertung: Netzbau, Urteil, Verteilungen, Lücke und Runden, Optionen-, Pfad- und Größentabelle, Anzeige-Helfer."""

import pytest

import mcg_cg as cg
import mcg_constants as C
import mcg_evaluation as ev
import mcg_model as md

P = ev.DEFAULT_PARAMS
GRID = P._replace(net="grid", k=4)


def test_build_dispatches_on_the_net_and_ignores_the_random_settings_for_fixed_nets():
    assert ev.build(P._replace(net="gap")) == md.gap_net() and ev.build(P._replace(net="preis")) == md.preis_net()
    assert ev.build(P) == md.generate_mcf(3, 3, 8, 60, 50, 90, 155, 3)
    assert ev.build(GRID) == md.generate_grid(5, 4, 70, 2, 4, 4, 7)
    assert ev.normalise(P._replace(net="gap", k=5, seed=9, gw=7)) == ev.normalise(P._replace(net="gap"))       # gleiche Netze, gleicher Schlüssel


def test_with_seed_changes_only_the_seed_of_the_shown_vehicle():
    assert ev.with_seed(P, 5).seed == 5 and ev.with_seed(P, 5).gseed == P.gseed
    assert ev.with_seed(GRID, 5).gseed == 5 and ev.with_seed(GRID, 5).seed == P.seed


def test_verdict_codes_and_data():
    lvl, code, d = ev.verdict(ev.analyse(P))
    assert (lvl, code) == ("success", "optimal") and d["value_diff"] == pytest.approx(0, abs=1e-6) and d["rounds"] == d["lp_solves"] - 1
    assert d["columns"] < d["lp_vars"] and d["used"] <= d["columns"] and d["paths_exact"] and d["paths"] >= d["columns"] and d["n_binding"] == len(d["binding"])
    assert d["lb"] == pytest.approx(d["cg_obj"], abs=1e-6) and d["gap"] == pytest.approx(0, abs=1e-9)
    lvl, code, d = ev.verdict(ev.analyse(ev.normalise(P._replace(net="gap"))))
    assert (lvl, code) == ("success", "optimal") and d["fractional"] and d["lp_delivered"] == 1.5
    lvl, code, d = ev.verdict(ev.analyse(P, ev.DEFAULT_OPTS._replace(ignore_mu=True)))
    assert (lvl, code) == ("error", "stuck") and d["delivery_gap"] > 1
    lvl, code, d = ev.verdict(ev.analyse(P, ev.DEFAULT_OPTS._replace(gap=0.05)))
    assert (lvl, code) == ("info", "gap") and d["gap"] <= 0.05 and d["value_diff"] > 0
    lvl, code, d = ev.verdict(ev.analyse(P._replace(p=2, d=6, s=3, density=20, seed=8)))
    assert code in ("optimal", "nothing") and d["lp_delivered"] <= d["demand"]


def test_gap_and_rounds_to_gap():
    a = ev.analyse(P)
    r = a.cg
    assert ev.gap_of(r.rounds[0]) == float("inf") and ev.gap_of(r.rounds[-1]) == pytest.approx(0, abs=1e-9)
    assert ev.rounds_to_gap(r, 0.0) == r.n_rounds and ev.rounds_to_gap(r, 0.05) <= ev.rounds_to_gap(r, 0.01) <= ev.rounds_to_gap(r, 0.001) <= r.n_rounds
    assert ev.rounds_to_gap(r, 1e9) == 1                                                                   # Runde 0 (leerer Master) hat keine Lücke; Runde 1 ist die erste mit Wert


def test_distribution_is_consistent_with_single_runs():
    seeds = tuple(range(5))
    dist = ev.distribution(P, seeds=seeds)
    for i, seed in enumerate(seeds):
        a = ev.analyse(ev.with_seed(P, seed))
        assert dist["cols"]["rounds"][i] == a.cg.n_rounds and dist["cols"]["columns"][i] == a.cg.n_columns and dist["cols"]["vars"][i] == a.lp.n_vars
        assert dist["cols"]["exact"][i] and dist["gap_rounds"][0.0][i] == a.cg.n_rounds
    assert dist["n_seeds"] == 5 and dist["share_exact"] == 1.0 and dist["share_stuck"] == 0.0
    grid = ev.distribution(GRID, seeds=seeds)
    assert grid["cols"]["vars"][0] == ev.analyse(ev.with_seed(GRID, 0)).lp.n_vars


def test_options_table_has_one_row_per_variant_in_the_documented_order():
    rows = ev.options_table(P)
    assert [r["opts"] for r in rows] == [o for _, o in ev.VARIANTS] and len(rows) == 6
    assert rows[0]["exact"] == 1.0 and rows[-1]["stuck"] > 0.9 and rows[-1]["exact"] < 0.1


def test_path_table_counts_exactly():
    rows = ev.path_table(sizes=((3, 3), (4, 3)), K=2, seeds=C.PATH_SEEDS[:2])
    assert [r["size"] for r in rows] == [(3, 3), (4, 3)] and all(r["exact"] for r in rows)
    assert rows[0]["paths"] < rows[1]["paths"] and all(r["columns"] <= r["paths"] and r["used"] <= r["columns"] for r in rows)


def test_size_table_shapes_and_exactness():
    rows = ev.size_table(sizes=((3, 3), (4, 3)), K=3, seeds=C.SIZE_SEEDS[:2])
    assert [r["size"] for r in rows] == [(3, 3), (4, 3)] and all(r["exact"] and r["columns"] < r["vars"] for r in rows)
    assert rows[0]["vars"] < rows[1]["vars"]


def test_display_helpers():
    mcf = md.generate_grid(3, 3, 100, 2, 3, 2, 1)
    r = cg.column_generation(mcf)
    for c in r.columns:
        assert all(part.startswith("(") and part.endswith(")") for part in ev.path_label(mcf, c.edges).split(" → "))
    rounds = ev.column_rounds(r)
    assert rounds == sorted(rounds) and rounds[0] == 1 and rounds[-1] == r.n_rounds
    dist = md.generate_mcf(3, 3, 8, 60, 50, 90, 155, 3)
    label = ev.path_label(dist, cg.column_generation(dist).columns[0].edges)
    assert label.startswith("W") and label.split(" → ")[-1].startswith("F")
    assert ev.path_label(md.preis_net(), cg.column_generation(md.preis_net()).columns[0].edges) in ("A → D", "A → B → D")
