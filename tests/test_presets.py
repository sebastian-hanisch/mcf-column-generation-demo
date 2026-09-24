"""Presets: vollständig, in den Grenzen, und jedes Beispielnetz zeigt, was sein Hilfetext behauptet."""

import pytest

import mcg_constants as C
import mcg_evaluation as ev
import mcg_presets as P

KEYS = set(P.PRESET_KEYS)


def _analyse(p):
    params = ev.normalise(ev.NetParams(p["net"], p["k"], p["p"], p["d"], p["s"], p["density"], p["spread"], p["load"], p["seed"], p["gw"], p["gh"], p["gdensity"], p["gcap"], p["gdem"], p["gseed"]))
    return ev.analyse(params, ev.Opts(p["per_round"], p["start"], p["alpha"], p["gap"], p["ignore_mu"]))


def test_every_preset_has_help_and_all_keys():
    assert set(C.PRESETS) == set(C.PRESET_HELP) and len(C.PRESETS) == 8
    assert all(C.PRESET_HELP[name].strip() for name in C.PRESETS)
    for name, p in C.PRESETS.items():
        assert set(p) == KEYS, name


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_preset_values_are_inside_the_bounds_and_on_the_step_grid(name):
    p = C.PRESETS[name]
    assert p["net"] in C.NETS and p["per_round"] in C.PER_ROUND and p["start"] in C.START and p["alpha"] in C.ALPHAS and p["gap"] in C.GAPS and isinstance(p["ignore_mu"], bool)
    for key, state_key in P.PRESET_KEYS.items():
        spec = P.SETTING_SPECS[state_key]
        if spec.lo is not None:
            assert spec.lo <= p[key] <= spec.hi, (name, key)
    assert (p["density"] - C.DENSITY_MIN) % 10 == 0 and p["spread"] % 25 == 0 and (p["load"] - C.LOAD_MIN) % 10 == 0 and (p["gdensity"] - C.GDENSITY_MIN) % 10 == 0


def test_setting_specs_have_room_to_move():
    """Ein Regler mit lo == hi würde Streamlit abstürzen lassen."""
    assert all(spec.lo < spec.hi for spec in P.SETTING_SPECS.values() if spec.lo is not None)


def test_presets_use_seeds_outside_the_distribution_set():
    for name, p in C.PRESETS.items():
        assert p["seed"] not in C.DIST_SEEDS and p["gseed"] not in C.DIST_SEEDS, name


def test_defaults_equal_the_random_net_preset():
    p = C.PRESETS["🚚 Zufallsnetz"]
    assert p == {**C._BASE} and p["net"] == C.DEFAULT_NET and (p["k"], p["seed"], p["gseed"]) == (C.DEFAULT_K, C.DEFAULT_SEED, C.DEFAULT_GSEED)
    assert ev.DEFAULT_PARAMS.net == p["net"] and ev.DEFAULT_OPTS == ev.Opts(p["per_round"], p["start"], p["alpha"], p["gap"], p["ignore_mu"])


def test_the_variant_presets_change_only_what_their_name_says():
    base = C.PRESETS["🚚 Zufallsnetz"]
    for name, changed in (("🚀 Start aus Nacheinander", ("start",)), ("🐢 Eine Spalte je Runde", ("per_round",)), ("🚫 Negativkontrolle", ("ignore_mu",))):
        assert all(C.PRESETS[name][k] == base[k] for k in base if k not in changed), name
        assert all(C.PRESETS[name][k] != base[k] for k in changed)


def test_fixed_presets_hide_the_random_controls():
    assert {n for n, p in C.PRESETS.items() if p["net"] in C.FIXED_NETS} == {"🔀 Preis-Wende", "🧩 Frachtnetz mit Bruch"}


def test_each_preset_shows_what_its_help_text_says():
    v = {name: ev.verdict(_analyse(p)) for name, p in C.PRESETS.items()}
    lvl, code, d = v["🚚 Zufallsnetz"]
    assert (code, d["lp_delivered"], d["demand"], d["lp_cost"], d["lp_vars"], d["paths"], d["paths_exact"]) == ("optimal", 67.0, 76, 1548.0, 114, 79, True)
    assert 10 <= d["rounds"] <= 18 and 28 <= d["columns"] <= 34 and 17 <= d["used"] <= 23
    _, code, d = v["🗺️ Streckennetz"]
    assert (code, d["paths"], d["paths_exact"], d["lp_vars"]) == ("optimal", 242, True, 256) and 4 <= d["rounds"] <= 7 and 13 <= d["columns"] <= 19 and 5 <= d["used"] <= 9
    _, code, d = v["🔀 Preis-Wende"]
    assert (code, d["rounds"], d["columns"], d["cg_delivered"], d["cg_cost"], d["n_binding"]) == ("optimal", 2, 4, 2.0, 5.0, 1)
    _, code, d = v["🧩 Frachtnetz mit Bruch"]
    assert (code, d["cg_delivered"], d["fractional"], d["paths"]) == ("optimal", 1.5, True, 4)
    _, code, d = v["🚀 Start aus Nacheinander"]
    assert code == "optimal" and d["rounds"] <= 8 and d["rounds"] < v["🚚 Zufallsnetz"][2]["rounds"] * 0.7
    _, code, d = v["🐢 Eine Spalte je Runde"]
    assert code == "optimal" and d["rounds"] > 2 * v["🚚 Zufallsnetz"][2]["rounds"] * 0.9 and d["rounds"] == d["columns"]
    _, code, d = v["🕸️ Dichtes Streckennetz"]
    assert (code, d["lp_vars"], d["paths_exact"]) == ("optimal", 720, False) and d["paths"] >= 20000 and d["columns"] <= 45 and d["used"] <= 12
    _, code, d = v["🚫 Negativkontrolle"]
    assert code == "stuck" and d["cg_delivered"] < d["lp_delivered"] - 30


def test_the_presets_show_both_good_and_bad_news():
    """Gute Nachricht: fast immer optimal mit wenigen Spalten; schlechte: ohne Preise der Gut-Obergrenzen hält das Verfahren mit falschem Wert an."""
    codes = [ev.verdict(_analyse(p))[1] for p in C.PRESETS.values()]
    assert codes.count("optimal") == 7 and codes.count("stuck") == 1
