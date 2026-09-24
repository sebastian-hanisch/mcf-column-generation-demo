"""Rauchtests der Streamlit-Oberfläche per AppTest: Standard, jedes Preset, alle Optionen, Randgrößen, Rundenregler, ausgeblendete Regler, Permalink, Experimente auf Abruf, Schlüssel und Achsensperre."""

import itertools
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import mcg_constants as C
from mcg_presets import PRESET_KEYS

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app.py"

# Anfang der Meldung zum gezeigten Netz (Streamlit legt das führende Emoji in `icon`, nicht in `value`); Runden und Spalten hängen vom LP-Löser ab und stehen nicht im Präfix
OPT = "Column Generation endet im LP-Optimum: "
EXPECTED = {
    "🚚 Zufallsnetz": OPT + "67 von 76 Einheiten für 1548, nach ",
    "🗺️ Streckennetz": OPT + "7 von 12 Einheiten für 105, nach ",
    "🔀 Preis-Wende": OPT + "2 von 2 Einheiten für 5, nach 2 Runden mit 4 Spalten (2 mit Fluss). Das Kanten-LP braucht 14 Variablen, möglich wären 4 Pfade.",
    "🧩 Frachtnetz mit Bruch": OPT + "1,5 von 2 Einheiten für 24, nach 2 Runden mit 3 Spalten (3 mit Fluss). Das Kanten-LP braucht 26 Variablen, möglich wären 4 Pfade. Die Lösung ist gebrochen (1,5 Einheiten): ganzzahlig ginge weniger.",
    "🚀 Start aus Nacheinander": OPT + "67 von 76 Einheiten für 1548, nach ",
    "🐢 Eine Spalte je Runde": OPT + "67 von 76 Einheiten für 1548, nach ",
    "🕸️ Dichtes Streckennetz": OPT + "10 von 11 Einheiten für 239, nach ",
    "🚫 Negativkontrolle": "Falscher Wert: ohne die Preise der Gut-Obergrenzen findet das Pricing nur schon bekannte Pfade und hält nach ",
}


def _run(setup=None, timeout=600):
    at = AppTest.from_file(str(APP), default_timeout=timeout)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    if setup is not None:
        setup(at)
        at.run()
        assert not at.exception, [e.value for e in at.exception]
    return at


def _apply(at, p):
    for key, state_key in PRESET_KEYS.items():
        at.session_state[state_key] = p[key]


def _labels(at):
    return {w.label for w in list(at.sidebar.slider) + list(at.sidebar.selectbox) + list(at.sidebar.number_input) + list(at.sidebar.radio)}


def _texts(at):
    return [e.value for e in list(at.success) + list(at.warning) + list(at.info) + list(at.error)]


def _has(at, prefix):
    return any(t.startswith(prefix) for t in _texts(at))


def _round(at):
    found = [s for s in at.slider if s.key == "cg_round"]
    return found[0] if found else None


def _metric(at, label):
    return [m.value for m in at.metric if m.label == label]


def _captions(at):
    return [c.value for c in at.caption]


OPTION_LABELS = {"Spalten je Runde", "Start", "Glättung der Preise (α)", "Abbruch bei Lücke"}


def test_default_renders_without_exception():
    at = _run()
    assert any("Runde für Runde zum Optimum" in m.value for m in at.markdown)
    assert _has(at, EXPECTED["🚚 Zufallsnetz"]) and not at.error
    assert _metric(at, "Wert")[0] == "= Kanten-LP" and _metric(at, "Spalten")[0] == str(int(_metric(at, "Spalten")[0])) and _metric(at, "Im Optimum")[0] == "100 %"
    assert _round(at).value == _round(at).max >= 8


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_renders_with_its_verdicts(name):
    at = _run(lambda a: _apply(a, C.PRESETS[name]))
    assert _has(at, EXPECTED[name]), _texts(at)
    if C.PRESETS[name]["net"] in C.FIXED_NETS:
        assert any(t.startswith("Festes Netz") for t in _texts(at))
    else:
        assert any(m.value.startswith("**Nicht nur dieses eine Netz:**") for m in at.markdown)
    if _round(at) is not None:
        assert _round(at).value == _round(at).max


@pytest.mark.parametrize("K", range(C.K_MIN, C.K_MAX + 1))
@pytest.mark.parametrize("net", ["random", "grid"])
def test_every_number_of_goods_renders(net, K):
    def setup(at):
        at.session_state["net_select"] = net
        at.session_state["k_slider"] = K
    at = _run(setup)
    assert not at.error and any(t.startswith(OPT) for t in _texts(at)) and _round(at).max >= 2


@pytest.mark.parametrize("per_round,start,alpha", list(itertools.product(C.PER_ROUND, C.START, C.ALPHAS)))
def test_every_option_combination_renders(per_round, start, alpha):
    def setup(at):
        at.session_state["per_round_radio"] = per_round
        at.session_state["start_radio"] = start
        at.session_state["alpha_radio"] = alpha
    at = _run(setup)
    assert not at.error and any(t.startswith(OPT) for t in _texts(at))


def test_a_gap_tolerance_stops_early_and_says_so():
    at = _run(lambda a: a.session_state.__setitem__("gap_radio", 0.05))
    assert any(t.startswith("Angehalten bei einer Lücke von") for t in _texts(at)) and any("Angehalten: die Lücke" in c for c in _captions(at))


def test_extreme_sizes_render():
    for net, vals in (("random", (("p_slider", C.P_MIN), ("d_slider", C.D_MIN), ("s_slider", C.S_MIN), ("density_slider", C.DENSITY_MIN), ("spread_slider", C.SPREAD_MIN), ("load_slider", C.LOAD_MIN), ("k_slider", C.K_MIN))),
                      ("random", (("p_slider", C.P_MAX), ("d_slider", C.D_MAX), ("s_slider", C.S_MAX), ("density_slider", C.DENSITY_MAX), ("spread_slider", C.SPREAD_MAX), ("load_slider", C.LOAD_MAX), ("k_slider", C.K_MAX))),
                      ("grid", (("gw_slider", C.GW_MIN), ("gh_slider", C.GH_MIN), ("gdensity_slider", C.GDENSITY_MIN), ("gcap_slider", C.GCAP_MIN), ("gdem_slider", C.GDEM_MIN), ("k_slider", C.K_MIN))),
                      ("grid", (("gw_slider", C.GW_MAX), ("gh_slider", C.GH_MAX), ("gdensity_slider", C.GDENSITY_MAX), ("gcap_slider", C.GCAP_MAX), ("gdem_slider", C.GDEM_MAX), ("k_slider", C.K_MAX)))):
        def setup(at, net=net, vals=vals):
            at.session_state["net_select"] = net
            for key, value in vals:
                at.session_state[key] = value
        at = _run(setup)
        assert not at.error


def test_a_net_where_nothing_arrives_renders_and_says_so():
    """Zwei Werke, sechs Verteilzentren, drei Filialen, dünnes Netz: kein Weg von S nach T, der Master bleibt leer, es gibt nur die Runde 0 (kein Regler mit min = max)."""
    def setup(at):
        for key, value in (("p_slider", 2), ("d_slider", 6), ("s_slider", 3), ("density_slider", 20), ("spread_slider", 50), ("load_slider", 90), ("seed_input", 8)):
            at.session_state[key] = value
    at = _run(setup)
    assert any("kommt gar nichts an" in t for t in _texts(at)) and _round(at) is None and any("nur eine Runde" in c for c in _captions(at))


def test_hidden_controls_follow_the_net():
    def labels_for(net):
        return _labels(_run(lambda a: a.session_state.__setitem__("net_select", net)))
    random_labels, grid, fixed = labels_for("random"), labels_for("grid"), labels_for("preis")
    assert {"Netz", "Zahl der Güter", "Werke", "Verteilzentren", "Filialen", "Netzdichte [%]", "Streuung der Lane-Breiten [%]", "Auslastung [% der Werkskapazität]", "Zufalls-Seed"} | OPTION_LABELS == random_labels
    assert {"Netz", "Zahl der Güter", "Breite des Gitters", "Höhe des Gitters", "Anteil der Gitterkanten [%]", "Größte Kapazität je Kante", "Größte Menge je Gut", "Zufalls-Seed (Streckennetz)"} | OPTION_LABELS == grid
    assert fixed == {"Netz"} | OPTION_LABELS                                                               # keine toten Regler bei festen Netzen


def test_hidden_slider_values_come_back_when_the_net_is_shown_again():
    at = _run(lambda a: (a.session_state.__setitem__("density_slider", 80), a.session_state.__setitem__("k_slider", 4)))
    at.session_state["net_select"] = "gap"
    at.run()
    at.session_state["net_select"] = "random"
    at.run()
    assert not at.exception and at.slider(key="density_slider").value == 80 and at.slider(key="k_slider").value == 4
    at = _run(lambda a: (a.session_state.__setitem__("net_select", "grid"), a.session_state.__setitem__("gcap_slider", 3)))
    at.session_state["net_select"] = "preis"
    at.run()
    at.session_state["net_select"] = "grid"
    at.run()
    assert not at.exception and at.slider(key="gcap_slider").value == 3


def test_round_slider_shows_every_round_with_its_caption():
    at = _run(lambda a: _apply(a, C.PRESETS["🔀 Preis-Wende"]))
    assert _round(at).max == 2
    needles = {0: "Der Master hat noch keine Pfade und keine Preise", 1: "Der Master kennt 2 Pfade und liefert 1 von 2 Einheiten für 1", 2: "Kein Gut hat mehr einen Pfad mit negativen reduzierten Kosten"}
    for k, needle in needles.items():
        _round(at).set_value(k)
        at.run()
        assert not at.exception and any(needle in c for c in _captions(at)), (k, needle)
    _round(at).set_value(1)
    at.run()
    assert any("ein Preis nahe M = 1000" in c for c in _captions(at)) and any("Das Pricing findet 2 lohnende Pfade" in c for c in _captions(at))
    at = _run(lambda a: _apply(a, C.PRESETS["🚀 Start aus Nacheinander"]))
    _round(at).set_value(0)
    at.run()
    assert any("startet mit" in c and "Pfaden aus dem Nacheinander-Fahren" in c for c in _captions(at))


def test_changing_the_net_resets_the_round_to_the_optimum():
    at = _run()
    _round(at).set_value(1)
    at.run()
    assert _round(at).value == 1
    at.session_state["k_slider"] = 5
    at.run()
    assert not at.exception and _round(at).value == _round(at).max


def test_play_runs_through_all_frames_without_duplicate_chart_keys():
    """Beim Abspielen entstehen in einem Lauf mehrere Diagramme mit demselben Namen - die Schlüssel tragen deshalb die Runde."""
    at = _run(lambda a: _apply(a, C.PRESETS["🗺️ Streckennetz"]))
    [b for b in at.button if b.label == "▶️ Abspielen"][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_permalink_parameters_are_clamped_and_snapped():
    at = AppTest.from_file(str(APP), default_timeout=600)
    at.query_params["density"] = "9999"
    at.query_params["spread"] = "abc"
    at.query_params["p"] = "-5"
    at.query_params["k"] = "9"
    at.run()
    assert not at.exception
    assert at.slider(key="density_slider").value == C.DENSITY_MAX and at.slider(key="spread_slider").value == C.DEFAULT_SPREAD and at.slider(key="p_slider").value == C.P_MIN and at.slider(key="k_slider").value == C.K_MAX
    at = AppTest.from_file(str(APP), default_timeout=600)
    at.query_params["net"] = "grid"
    at.query_params["gdensity"] = "63"
    at.query_params["alpha"] = "0.5"
    at.query_params["gap"] = "0.01"
    at.query_params["per_round"] = "eine"
    at.query_params["start"] = "nacheinander"
    at.query_params["ignore_mu"] = "1"
    at.run()
    assert at.slider(key="gdensity_slider").value == 60 and at.radio(key="alpha_radio").value == 0.5 and at.radio(key="gap_radio").value == 0.01
    assert at.radio(key="per_round_radio").value == "eine" and at.radio(key="start_radio").value == "nacheinander" and at.toggle(key="ignore_mu_toggle").value is True


def test_unknown_values_in_the_permalink_fall_back_to_the_defaults():
    at = AppTest.from_file(str(APP), default_timeout=600)
    at.query_params["net"] = "ring"
    at.query_params["per_round"] = "lifo"
    at.query_params["alpha"] = "0.3"
    at.query_params["ignore_mu"] = "vielleicht"
    at.query_params["k"] = "abc"
    at.run()
    assert not at.exception and at.selectbox(key="net_select").value == C.DEFAULT_NET and at.radio(key="per_round_radio").value == C.DEFAULT_PER_ROUND
    assert at.radio(key="alpha_radio").value == C.DEFAULT_ALPHA and at.toggle(key="ignore_mu_toggle").value is False and at.slider(key="k_slider").value == C.DEFAULT_K


def test_randomize_moves_the_seed_but_not_the_distribution():
    at = _run()
    labels = ("Im Optimum", "Spalten gegen Variablen")
    pick = lambda a: [_metric(a, label) for label in labels] + [_metric(a, "Runden")[1:], _metric(a, "Iterationen")[1:]]
    before = pick(at)
    seed_before = at.number_input(key="seed_input").value
    [b for b in at.sidebar.button if "Neues Netz" in b.label][0].click()
    at.run()
    assert not at.exception and at.number_input(key="seed_input").value != seed_before and pick(at) == before
    at.session_state["net_select"] = "grid"
    at.run()
    g_before = at.number_input(key="gseed_input").value
    at.button(key="rand_grid").click()
    at.run()
    assert not at.exception and at.number_input(key="gseed_input").value != g_before


def test_experiments_run_on_demand():
    at = _run()
    for text in ("Mittel über 100 feste Netze. Alle Güter je Runde", "Mittel über 5 feste Netze je Größe", "Median der Sekunden über die Netze"):
        assert not any(text in c for c in _captions(at))
    for key in ("options_start", "paths_start", "size_start"):
        at.button(key=key).click()
        at.run()
        assert not at.exception, [e.value for e in at.exception]
    text = " ".join(_captions(at))
    assert "Mittel über 100 feste Netze. Alle Güter je Runde" in text and "Mittel über 5 feste Netze je Größe" in text and "Median der Sekunden über die Netze" in text
    assert "Die Glättung hilft nicht" in text and "Ohne die Preise der Gut-Obergrenzen enden nur 0 % der Netze im Optimum" in text


def test_experiments_on_a_fixed_net_show_hints_instead_of_dead_controls():
    at = _run(lambda a: a.session_state.__setitem__("net_select", "gap"))
    assert not [b for b in at.button if b.key == "options_start"] and {b.key for b in at.button if b.key in ("paths_start", "size_start")} == {"paths_start", "size_start"}       # Gitter-Experimente brauchen kein Netz
    assert sum("zufälliges Netz wählen" in t for t in _texts(at)) >= 3


def _calls(src, name):
    """Der Text jedes Aufrufs `name(...)` einschließlich verschachtelter Klammern."""
    out = []
    for m in re.finditer(re.escape(name) + r"\(", src):
        depth, i = 1, m.end()
        while depth:
            depth += {"(": 1, ")": -1}.get(src[i], 0)
            i += 1
        out.append(src[m.start():i])
    return out


def test_every_plotly_chart_has_an_explicit_key_and_axes_are_locked():
    calls = _calls(APP.read_text(encoding="utf-8"), "plotly_chart")
    keys = [re.search(r'key=f?"([a-z_]+?)(?:_\{\w+\})?"', c).group(1) for c in calls]
    assert all(re.search(r'key=f?"[a-z_]+(_\{\w+\})?"', c) for c in calls), calls
    assert len(calls) == 7 and len(set(keys)) == 7 and keys[:3] == ["cg_map", "conv_chart", "cols_chart"]
    viz = (ROOT / "mcg_visualization.py").read_text(encoding="utf-8")
    bodies = [b for b in viz.split(chr(10) + "def ") if b.startswith("build_")]
    assert "fixedrange=True" in viz and len(bodies) == 7 and all("_base(" in b or "_layout(" in b for b in bodies)


def test_app_text_has_no_links_to_repository_files():
    assert not re.search(r"\]\(\w+\.py\)", APP.read_text(encoding="utf-8"))


def test_footer_is_verbatim():
    src = APP.read_text(encoding="utf-8")
    assert "https://sebastianhanisch.net/kontakt.html" in src and "Interesse an einer maßgeschneiderten Lösung für" in src and "Operations Research und Machine Learning" in src


def test_runtime_needs_scipy_but_never_networkx():
    """Der LP-Löser ist HiGHS über scipy (Laufzeit); networkx bleibt reines Testorakel."""
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "scipy" in req and "networkx" not in req
    for path in ROOT.glob("*.py"):
        assert not re.search(r"^\s*(import|from)\s+networkx\b", path.read_text(encoding="utf-8"), re.M), path.name
