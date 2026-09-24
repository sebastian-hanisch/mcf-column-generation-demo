"""Pfad-Formulierung und Column Generation - nur die Pfade, die sich lohnen - interaktive Konzept-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Anders als die Fall-Demos im Portfolio (ein Anwendungsfall, mehrere Verfahren im Vergleich) zeigt diese Demo EIN Verfahren - die Column Generation für den Mehrgüterfluss - und lässt stattdessen das Beispiel wachsen.
Achtes Stück der Netzwerkfluss-Linie der "Konzepte"-Reihe, zweites im Mehrgüter-Ast: es setzt am Kanten-LP des Vorgängers an (K·m Variablen) und ersetzt es durch ein LP über Pfade, die erst bei Bedarf entstehen.
Siehe README für die Einordnung.

Lauffähig mit: streamlit run app.py
"""

import time

import streamlit as st

import mcg_constants as C
import mcg_evaluation as ev
import mcg_cg as cg
from mcg_presets import (
    KEPT,
    apply_preset,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    seed_widget,
    sync_query_params,
)
from mcg_visualization import (
    build_cg,
    build_columns,
    build_convergence,
    build_options,
    build_paths,
    build_rounds_hist,
    build_size,
)

st.set_page_config(page_title="Column Generation – Sebastian Hanisch", layout="wide")


def _pct(x, digits=1):
    return "–" if x is None else f"{x:.{digits}f} %".replace(".", ",")


def _share(x):
    """Anteil (0..1) als 'nn %'."""
    return f"{100 * x:.0f} %"


def _f(x, digits=1):
    return "–" if x is None else f"{x:.{digits}f}".replace(".", ",")


def _u(x):
    """Menge: ganze Zahl ohne Nachkommastellen, sonst eine."""
    return f"{round(x)}" if abs(x - round(x)) < 1e-6 else _f(x, 1)


def _n(x):
    """Ganze Zahl mit Tausendertrennung."""
    return f"{int(round(x)):,}".replace(",", " ")


def _edges(n):
    return "1 Kante" if n == 1 else f"{n} Kanten"


@st.cache_resource(show_spinner=False, max_entries=48)
def _analysis(params, opts):
    return ev.analyse(params, opts)


@st.cache_resource(show_spinner=False, max_entries=8)
def _all_paths(params):
    a = ev.analyse(params, ev.DEFAULT_OPTS)
    return cg.solve_all_paths(a.mcf, limit=C.PATH_LIMIT)


st.title("🛤️ Column Generation – nur die Pfade, die sich lohnen")
st.markdown(
    """
Im Vorgänger stand der Mehrgüterfluss als **Kanten-LP**: eine Variable je Gut und Kante, $K\\cdot m$ Stück. Hier bekommt jedes Gut stattdessen **Pfade** - ein Pfad von seinem Start zu seinem Ziel ist eine Variable, deren Wert angibt, wie viel auf ihm fährt.
Es gibt exponentiell viele Pfade, aber der Master kennt zu Beginn keinen. Er löst sein LP über die bekannten Pfade und gibt die **Preise** der gemeinsamen Kapazitäten weiter; das **Pricing** ist ein gewöhnlicher **kürzester Weg** (Dijkstra) mit Kantenlänge = Kosten + Preis.
Ist der kürzeste Weg eines Guts billiger als das, was eine Einheit einbringt, ist er ein Pfad, der den Master verbessert - er kommt als **Spalte** dazu. Findet kein Gut mehr einen solchen Weg, ist der Master **exakt das Kanten-LP-Optimum**, ohne dass man je alle Pfade gesehen hat.
Diese Demo lässt die Runden einzeln durchlaufen, zeigt die obere und die untere Schranke und misst, wann das lohnt - und wann nicht.
"""
)
st.caption(
    "Anders als die Fall-Demos im Portfolio, die an einem Anwendungsfall mehrere Verfahren vergleichen, zeigt diese Demo - achtes Stück der Netzwerkfluss-Linie der \"Konzepte\"-Reihe, zweites im Mehrgüter-Ast - **ein** Verfahren an einem wachsenden Beispiel. "
    "Die Folgestücke: **Garg–Könemann** (dieselben Kürzeste-Wege-Orakel, aber ohne LP-Löser und mit Garantie) und das **Netzwerkdesign mit Fixkosten** (Benders-Zerlegung, Slope Scaling)."
)

with st.expander("So funktioniert Column Generation", expanded=True):
    st.markdown(
        r"""
1. **Master:** $\min\ \sum_c (\text{Kosten}_c - M)\,x_c$ über den bekannten Pfaden $c$ (jeder Pfad gehört zu einem Gut und endet auf einer Nachfragekante, $M$ = Belohnung je gelieferter Einheit). Nebenbedingungen: je gemeinsame Kante die Summe aller Pfade über sie $\le u_e$, je Gut und Angebots- bzw. Nachfragekante $\le \text{ub}_{k,e}$.
2. **Preise:** die Duallösung des Masters: $\lambda_e\ge 0$ auf den gemeinsamen Kanten, $\mu_{k,e}\ge 0$ auf den gutspezifischen Obergrenzen. Bindende Kanten sind die Engstellen; ein Preis ist der Wert einer zusätzlichen Einheit Kapazität.
3. **Pricing:** für jedes Gut ein kürzester Weg von $S$ nach $T$ mit Kantenlänge $\text{Kosten}+\lambda_e+\mu_{k,e}$ (Dijkstra, alle Längen $\ge 0$). Die reduzierten Kosten des Weges sind Länge $- M$. Ist sie negativ, lohnt sich der Weg als neue Spalte.
4. **Abbruch:** kein Gut hat einen Weg mit negativen reduzierten Kosten - dann ist das Pfad-LP mit **allen** Pfaden optimal. Der Wert ist derselbe wie im Kanten-LP.
5. **Schranke:** für beliebige Preise gilt eine untere Schranke (Farley): Master-Wert plus für jedes Gut seine Gesamtnachfrage mal die kleinste reduzierte Kosten (höchstens 0). So sieht man, wie weit man vom Optimum noch entfernt sein kann.
6. **Zusammenhang zum Vorgänger:** dort entkoppelten die Preise die Güter - der Wert stimmte, die Flüsse überlasteten Kanten. Jeder dieser Einzelflüsse ist ein Pfad; der Master mischt sie zu einer zulässigen Lösung.
        """
    )

st.caption("🎯 Schnellstart – ein Beispielnetz laden:")
names = list(C.PRESETS.keys())
for row in range(0, len(names), 4):
    preset_cols = st.columns(4)
    for col, name in zip(preset_cols, names[row:row + 4]):
        with col:
            st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP[name])

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()


def _kept(key, default):
    return int(st.session_state.get(KEPT[key], default))


def _slider(label, key, help, step=None):
    kw = {"step": step} if step else {}
    seed_widget(key)
    value = st.slider(label, *bounds(key), key=key, help=help, **kw)
    st.session_state[KEPT[key]] = value
    return value


with st.sidebar:
    st.header("⚙️ Einstellungen")
    net_key = st.selectbox(
        "Netz", list(C.NETS), key="net_select", format_func=lambda k: C.NETS[k],
        help="Das Distributionsnetz des Vorgängers (dreistufig, wenige Pfade), ein Streckennetz (Gitter mit Start-Ziel-Aufträgen, viele Pfade) oder eines von zwei festen Lehrnetzen: die Preis-Wende und das Frachtnetz, dessen LP gebrochen ist.",
    )
    show_dist, show_grid = net_key == "random", net_key == "grid"
    if show_dist or show_grid:
        K = _slider("Zahl der Güter", "k_slider", "Frische, Trocken, Kühl, Getränke, Tiefkühl (in dieser Reihenfolge). Im Distributionsnetz stellt jedes Werk ein Gut mit 70 % Wahrscheinlichkeit her; im Streckennetz hat jedes Gut einen eigenen Start und ein eigenes Ziel.")
    else:
        K = _kept("k_slider", C.DEFAULT_K)
    if show_dist:
        p = _slider("Werke", "p_slider", "Anzahl der Werke (oben im Netz).")
        d = _slider("Verteilzentren", "d_slider", "Anzahl der Verteilzentren; Durchsatz gemeinsam für alle Güter.")
        s = _slider("Filialen", "s_slider", "Anzahl der Filialen (unten im Netz).")
        density = _slider("Netzdichte [%]", "density_slider", "Anteil der möglichen Lanes, die es gibt.", step=10)
        spread = _slider("Streuung der Lane-Breiten [%]", "spread_slider", "0 = alle Lanes einer Stufe gleich breit, 100 = Kapazitäten gleichverteilt von 1 bis zum Doppelten der Grundbreite.", step=25)
        load = _slider("Auslastung [% der Werkskapazität]", "load_slider", "Gesamtnachfrage der Filialen (alle Güter zusammen) in Prozent der Werkskapazität.", step=10)
        seed_widget("seed_input")
        seed = st.number_input("Zufalls-Seed", *bounds("seed_input"), key="seed_input", step=1)
        st.session_state[KEPT["seed_input"]] = seed
        st.button("🎲 Neues Netz generieren", width="stretch", on_click=randomize_seed, args=("seed_input",), help="Würfelt einen neuen Zufalls-Seed. Die Verteilungen über 100 feste Netze weiter unten ändern sich dabei nicht - nur die Marke „Ihre Ziehung“.")
    else:
        p, d, s = _kept("p_slider", C.DEFAULT_P), _kept("d_slider", C.DEFAULT_D), _kept("s_slider", C.DEFAULT_S)
        density, spread, load, seed = _kept("density_slider", C.DEFAULT_DENSITY), _kept("spread_slider", C.DEFAULT_SPREAD), _kept("load_slider", C.DEFAULT_LOAD), _kept("seed_input", C.DEFAULT_SEED)
    if show_grid:
        gw = _slider("Breite des Gitters", "gw_slider", "Knoten je Zeile.")
        gh = _slider("Höhe des Gitters", "gh_slider", "Knoten je Spalte.")
        gdensity = _slider("Anteil der Gitterkanten [%]", "gdensity_slider", "Ein zufälliger Spannbaum hält das Netz zusammenhängend; jede weitere Gitterkante gibt es mit diesem Anteil. 100 % = volles Gitter mit den meisten Pfaden.", step=10)
        gcap = _slider("Größte Kapazität je Kante", "gcap_slider", "Jede Kante trägt in beide Richtungen 1 bis zu diesem Wert, gemeinsam für alle Güter.")
        gdem = _slider("Größte Menge je Gut", "gdem_slider", "Jedes Gut fährt 1 bis zu diesem Wert von seinem Start zu seinem Ziel.")
        seed_widget("gseed_input")
        gseed = st.number_input("Zufalls-Seed (Streckennetz)", *bounds("gseed_input"), key="gseed_input", step=1)
        st.session_state[KEPT["gseed_input"]] = gseed
        st.button("🎲 Neues Netz generieren", width="stretch", on_click=randomize_seed, args=("gseed_input",), key="rand_grid", help="Würfelt einen neuen Zufalls-Seed für das Streckennetz.")
    else:
        gw, gh, gdensity = _kept("gw_slider", C.DEFAULT_GW), _kept("gh_slider", C.DEFAULT_GH), _kept("gdensity_slider", C.DEFAULT_GDENSITY)
        gcap, gdem, gseed = _kept("gcap_slider", C.DEFAULT_GCAP), _kept("gdem_slider", C.DEFAULT_GDEM), _kept("gseed_input", C.DEFAULT_GSEED)
    if not (show_dist or show_grid):
        st.caption("Dieses Netz ist fest - es gibt nichts zu erzeugen. Die Regler für Güter, Größe und Seed gehören zu den zufälligen Netzen.")
    st.subheader("Column Generation")
    per_round = st.radio("Spalten je Runde", list(C.PER_ROUND), key="per_round_radio", format_func=lambda k: C.PER_ROUND[k],
                         help="Nach jedem Pricing nimmt der Master entweder den besten Pfad jedes Guts auf oder nur den einen insgesamt besten.")
    start = st.radio("Start", list(C.START), key="start_radio", format_func=lambda k: C.START[k],
                     help="Leer: der Master beginnt ohne Pfade. Aus dem Nacheinander-Fahren: er beginnt mit den Pfaden, die der Vorgänger beim Nacheinander-Fahren der Güter gefunden hat.")
    alpha = st.radio("Glättung der Preise (α)", list(C.ALPHAS), key="alpha_radio", format_func=lambda a: "aus" if a == 0 else f"{a:g}".replace(".", ","),
                     help="Wentges: das Pricing benutzt eine Mischung aus den besten bisherigen Preisen (Gewicht α) und den aktuellen. Beruhigt oft das Zappeln der Preise - hier kaum, siehe Experiment.")
    gap = st.radio("Abbruch bei Lücke", list(C.GAPS), key="gap_radio", format_func=lambda g: "bis zum Optimum" if g == 0 else f"{g * 100:g} %".replace(".", ","),
                   help="Anhalten, sobald obere und untere Schranke höchstens so weit auseinanderliegen (bezogen auf den Betrag des Zielwerts, in dem eine Lieferung 1000 wiegt).")
    ignore_mu = st.toggle("Negativkontrolle: Preise der Gut-Obergrenzen ignorieren", key="ignore_mu_toggle",
                          help="Das Pricing vergisst die Preise der Werks- und Nachfragekanten je Gut. Es findet dann nur schon bekannte Pfade und hält mit einem falschen Wert an.")

sync_query_params({"net_select": net_key, "k_slider": int(K), "p_slider": int(p), "d_slider": int(d), "s_slider": int(s), "density_slider": int(density), "spread_slider": int(spread),
                   "load_slider": int(load), "seed_input": int(seed), "gw_slider": int(gw), "gh_slider": int(gh), "gdensity_slider": int(gdensity), "gcap_slider": int(gcap),
                   "gdem_slider": int(gdem), "gseed_input": int(gseed), "per_round_radio": per_round, "start_radio": start, "alpha_radio": alpha, "gap_radio": gap, "ignore_mu_toggle": bool(ignore_mu)})

params = ev.normalise(ev.NetParams(net_key, int(K), int(p), int(d), int(s), int(density), int(spread), int(load), int(seed), int(gw), int(gh), int(gdensity), int(gcap), int(gdem), int(gseed)))
opts = ev.Opts(per_round, start, float(alpha), float(gap), bool(ignore_mu))
with st.spinner("Rechne..."):
    a = _analysis(params, opts)
mcf, lp, res = a.mcf, a.lp, a.cg
level, code, dat = ev.verdict(a)
K = mcf.K
is_fixed = net_key in C.FIXED_NETS
rounds = res.rounds
M = mcf.M


def _pt(k, edges):
    return f"{mcf.names[k]}: {ev.path_label(mcf, edges)}"


# --- Runden -------------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Runde für Runde zum Optimum")
owner = (params, opts)
if st.session_state.get("cg_owner") != owner:
    st.session_state["cg_round"] = len(rounds) - 1
    st.session_state["cg_owner"] = owner
step_col, play_col = st.columns([5, 2])
with step_col:
    if len(rounds) > 1:
        rd_no = st.slider("Runde", 0, len(rounds) - 1, key="cg_round", help="Runde 0: der Master vor dem ersten Pricing; danach je Runde: Master lösen, Preise weitergeben, Pfade suchen. Die letzte Runde ist das Optimum.")
    else:
        rd_no = 0
        st.caption("In diesem Netz gibt es nur eine Runde.")
with play_col:
    auto_play = st.button("▶️ Abspielen", width="stretch")
view_slot = st.empty()


def _caption(i):
    rd = rounds[i]
    head = f"**Runde {i}:** "
    if i == 0 and start == "leer":
        head += "Der Master hat noch keine Pfade und keine Preise; das Pricing sucht für jedes Gut den billigsten Weg - das ist \"jedes Gut allein\" aus dem Vorgänger. "
    elif i == 0:
        head += f"Der Master startet mit {rd.n_columns} Pfaden aus dem Nacheinander-Fahren des Vorgängers: {_u(sum(rd.delivered))} von {dat['demand']} Einheiten für {_u(rd.cost)}. "
    else:
        head += f"Der Master kennt {rd.n_columns} Pfade und liefert {_u(sum(rd.delivered))} von {dat['demand']} Einheiten für {_u(rd.cost)}. "
    priced = [e for e in range(mcf.m) if mcf.joint[e] and rd.lam[e] > 1e-6]
    if priced:
        top = max(rd.lam[e] for e in priced)
        head += f"{_edges(len(priced))} {'hat' if len(priced) == 1 else 'haben'} einen Preis (höchster {_f(top, 0 if top >= 10 else 1)})"
        head += " - ein Preis nahe M = 1000 heißt: die Kante begrenzt die Lieferung selbst (eine Einheit Kapazität mehr brächte eine ganze Lieferung); kleine Preise heißen: sie verteuert nur. " if top > M / 2 else ". "
    if rd.new:
        found = "; ".join(_pt(res.columns[j].k, res.columns[j].edges) for j in rd.new[:4]) + (" ..." if len(rd.new) > 4 else "")
        best = min(rd.rc)
        head += f"Das Pricing findet {len(rd.new)} lohnende Pfade (kleinste reduzierte Kosten {_f(best, 1)}) und nimmt sie auf: {found}."
    elif i == len(rounds) - 1 and res.optimal:
        best = min(v for v in rd.rc if v != float("inf")) if any(v != float("inf") for v in rd.rc) else None
        head += ("Kein Gut hat mehr einen Pfad mit negativen reduzierten Kosten" + (f" (kleinster Wert {_f(best, 1)})" if best is not None else "")
                 + f": das Pfad-LP mit allen {_n(dat['paths'])}{'' if dat['paths_exact'] else ' und mehr'} Pfaden hat denselben Wert - optimal.")
    elif i == len(rounds) - 1 and res.gap_stop:
        head += f"Angehalten: die Lücke zwischen Master und Schranke beträgt {_pct(100 * ev.gap_of(rd), 2)}."
    elif i == len(rounds) - 1 and res.stuck:
        head += "Das Pricing (ohne die Preise der Gut-Obergrenzen) kennt keinen neuen Pfad mehr - der Master hält an, obwohl das LP-Optimum besser wäre."
    if rd.misprice:
        head += " (Das geglättete Pricing fand nichts, es wurde mit den echten Preisen neu bewertet.)"
    return head


def _render(i):
    with view_slot.container():
        rd = rounds[i]
        c1, c2 = st.columns(2)
        c1.markdown(f"**Runde {i}:** Master mit {rd.n_columns} Pfaden, Preise und neu gefundene Pfade")
        c2.markdown(f"**Wert und Schranken** - Master {_u(sum(rd.delivered))} von {dat['demand']} Einheiten, Kosten {_u(rd.cost)}")
        c1.plotly_chart(build_cg(mcf, rd, res.columns), width="stretch", key=f"cg_map_{i}")
        c2.plotly_chart(build_convergence(res, i, lp.objective, M), width="stretch", key=f"conv_chart_{i}")
        c2.plotly_chart(build_columns(res, i, dat["lp_vars"], dat["paths"], dat["paths_exact"]), width="stretch", key=f"cols_chart_{i}")
        st.caption(_caption(i))


if auto_play:
    for i in range(len(rounds)):
        _render(i)
        time.sleep(min(0.9, 8.0 / max(len(rounds), 1)))
    rd_no = len(rounds) - 1
else:
    _render(rd_no)

st.caption("Links: je Gut eine Farbe, Breite ~ Fluss im Master; orange Unterlage = Kante mit positivem Preis λ (Beschriftung); schwarz gestrichelt = die in dieser Runde gefundenen Pfade. Im Streckennetz sind Start (Raute) und Ziel (Stern) jedes Guts mit seiner Nummer markiert. "
           "Rechts oben der Wert −Z/M (Einheiten Lieferung, Kosten zählen 1/1000): der Master steigt, die untere Schranke sinkt, gestrichelt das Optimum des Kanten-LP. Rechts unten die Spalten je Runde (logarithmisch) gegen die Variablen des Kanten-LP und alle möglichen Pfade.")

with st.expander("Die Pfade im Master (Runde " + str(rd_no) + ")"):
    rd = rounds[rd_no]
    rows = [(j, col) for j, col in enumerate(res.columns) if j < rd.n_columns]
    since = ev.column_rounds(res)
    st.dataframe({"Gut": [mcf.names[c.k] for _, c in rows], "Pfad": [ev.path_label(mcf, c.edges) for _, c in rows], "Kosten je Einheit": [_u(c.cost) for _, c in rows],
                  "Menge im Master": [_u(float(rd.amounts[j])) for j, _ in rows], "seit Runde": [since[j] for j, _ in rows]}, hide_index=True, width="stretch")
    st.caption("Die Menge 0 heißt: der Pfad ist bekannt, aber der Master braucht ihn im Moment nicht. Fließen Bruchteile, ist das LP gebrochen - ganzzahlig bräuchte man Branch-and-Price.")

st.markdown("---")

# --- Kernfrage ---------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Was spart die Column Generation?")
st.caption("**Spalten** = Pfade im Master am Ende; **Variablen** = so viele hätte das Kanten-LP des Vorgängers (K·m); **mögliche Pfade** = alle einfachen Wege der Güter (im Streckennetz bei großen Netzen nur „mindestens“); **Iterationen** = Schritte des HiGHS-Lösers, alle Runden zusammen.")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Wert", "= Kanten-LP" if abs(dat["value_diff"]) < 1e-6 else "weicht ab", delta=f"{_u(dat['cg_delivered'])} von {dat['demand']} Einheiten", delta_color="off", help=f"Column Generation liefert {_u(dat['cg_delivered'])} Einheiten für {_u(dat['cg_cost'])}; das Kanten-LP {_u(dat['lp_delivered'])} für {_u(dat['lp_cost'])}.")
m2.metric("Runden", f"{dat['rounds']}", delta=f"{dat['lp_solves']} Master-Läufe", delta_color="off", help="Runde = Master lösen, Preise weitergeben, Pfade suchen. Runde 0 zählt nicht.")
m3.metric("Spalten", f"{dat['columns']}", delta=f"{dat['used']} mit Fluss, Kanten-LP {dat['lp_vars']} Variablen", delta_color="off", help=f"Mögliche Pfade: {_n(dat['paths'])}{'' if dat['paths_exact'] else ' oder mehr (Zählung abgebrochen)'}.")
m4.metric("Iterationen", _n(dat["iterations"]), delta=f"Kanten-LP {_n(dat['lp_iterations'])}", delta_color="off", help="Simplex-Iterationen aller Master-Läufe zusammen gegen die des einen Kanten-LP-Laufs. scipy startet jeden Master neu (kein Warmstart).")

if code == "optimal":
    st.success(f"✅ Column Generation endet im LP-Optimum: {_u(dat['cg_delivered'])} von {dat['demand']} Einheiten für {_u(dat['cg_cost'])}, nach {dat['rounds']} Runden mit {dat['columns']} Spalten "
               f"({dat['used']} mit Fluss). Das Kanten-LP braucht {dat['lp_vars']} Variablen, möglich wären {_n(dat['paths'])}{'' if dat['paths_exact'] else ' oder mehr'} Pfade."
               + (f" Die Lösung ist gebrochen ({_u(dat['lp_delivered'])} Einheiten): ganzzahlig ginge weniger." if dat["fractional"] else ""))
elif code == "gap":
    st.info(f"Angehalten bei einer Lücke von {_pct(100 * dat['gap'], 2)}: {_u(dat['cg_delivered'])} Einheiten für {_u(dat['cg_cost'])} statt {_u(dat['lp_delivered'])} für {_u(dat['lp_cost'])} im Optimum - nach {dat['rounds']} von {ev.analyse(params, ev.DEFAULT_OPTS).cg.n_rounds} Runden.")
elif code == "stuck":
    st.error(f"❌ Falscher Wert: ohne die Preise der Gut-Obergrenzen findet das Pricing nur schon bekannte Pfade und hält nach {dat['rounds']} Runden an - {_u(dat['cg_delivered'])} statt {_u(dat['lp_delivered'])} Einheiten. "
             "Die Preise sind kein Beiwerk: erst mit allen Preisen ist \"kein Pfad lohnt sich\" ein Beweis.")
else:
    st.warning("⚠️ Es kommt gar nichts an: kein Gut kann von seinem Start zu seinem Ziel gelangen. Der Master bleibt leer.")

if is_fixed:
    st.info("Festes Netz: es gibt nur diese eine Ziehung. Für die Verteilungen über viele Netze ein zufälliges Netz wählen.")
    dist = None
else:
    dist = ev.distribution(params, opts)
    kind = "Streckennetze" if net_key == "grid" else "Distributionsnetze"
    st.markdown(f"**Nicht nur dieses eine Netz:** {len(C.DIST_SEEDS)} feste {kind} mit denselben Einstellungen (Güter {K}), getrennt vom Seed oben.")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Im Optimum", _share(dist["share_exact"]), delta=f"Wert = Kanten-LP in {sum(dist['cols']['exact'])} von {dist['n_seeds']}", delta_color="off", help="Anteil der Netze, in denen die Column Generation im Optimum des Kanten-LP endet.")
    p2.metric("Runden", _f(dist["rounds_mean"], 1), delta=f"{_f(dist['columns_mean'], 1)} Spalten im Mittel", delta_color="off", help="Mittel über die Netze.")
    p3.metric("Spalten gegen Variablen", _pct(100 * dist["columns_mean"] / dist["vars_mean"], 0), delta=f"{_f(dist['columns_mean'], 0)} gegen {_f(dist['vars_mean'], 0)}", delta_color="off", help="Spalten der Column Generation im Verhältnis zu den Variablen des Kanten-LP.")
    p4.metric("Iterationen", _f(dist["cg_iterations_mean"], 0), delta=f"Kanten-LP {_f(dist['lp_iterations_mean'], 0)}", delta_color="off", help="Simplex-Iterationen im Mittel, Column Generation (alle Runden) gegen ein Kanten-LP.")
    st.plotly_chart(build_rounds_hist(dist["cols"]["rounds"], current=dat["rounds"]), width="stretch", key="rounds_hist")
    st.caption(f"Über {len(C.DIST_SEEDS)} feste Netze braucht die Column Generation im Mittel {_f(dist['rounds_mean'], 1)} Runden und {_f(dist['columns_mean'], 1)} Spalten ({_f(dist['used_mean'], 1)} mit Fluss); das Kanten-LP hat {_f(dist['vars_mean'], 0)} Variablen. "
               f"Die erste Runde liefert im Mittel erst {_f(dist['first_delivered_mean'], 1)} von {_f(dist['lp_delivered_mean'], 1)} Einheiten.")

st.markdown("---")

# --- Vergleich -----------------------------------------------------------------------------------------------------------------------------

with st.expander("🔧 Wie wir das erreichen – drei Wege zum selben Wert"):
    all_rows = [("Kanten-LP (Vorgänger)", f"{dat['lp_vars']} Variablen", _u(dat["lp_cost"]), _u(dat["lp_delivered"]), _n(dat["lp_iterations"]))]
    if dat["paths_exact"] and dat["paths"] <= 3000 and not opts.ignore_mu:
        obj_all, n_all = _all_paths(params)
        all_rows.append(("Pfad-LP mit allen Pfaden", f"{n_all} Spalten", "–", "–", f"Wert = Kanten-LP: {'ja' if abs(obj_all - lp.objective) < 1e-6 else 'nein'}"))
    all_rows.append(("Column Generation", f"{dat['columns']} Spalten", _u(dat["cg_cost"]), _u(dat["cg_delivered"]), _n(dat["iterations"])))
    st.table({"Verfahren": [r[0] for r in all_rows], "Umfang": [r[1] for r in all_rows], "Kosten": [r[2] for r in all_rows], "Lieferung": [r[3] for r in all_rows], "Iterationen": [r[4] for r in all_rows]})
    st.caption("Das Pfad-LP mit allen Pfaden (Aufzählung, nur bei höchstens 3000 Pfaden) bestätigt, dass die Column Generation nichts verpasst: derselbe Wert wie das Kanten-LP, ohne dass sie je alle Pfade gesehen hat. "
               "Die Column Generation gewinnt bei der Zahl der Spalten, nicht bei den Iterationen: jede Runde löst das Master-LP neu.")
    st.markdown("**Was die Runden gekostet haben**")
    st.table({"Runde": [str(rd.r) for rd in rounds], "Spalten": [str(rd.n_columns) for rd in rounds], "Simplex-Iterationen": [str(rd.iterations) for rd in rounds], "im Pricing angesehene Kanten": [str(rd.scans) for rd in rounds]})

st.markdown("---")

# --- Experimente -----------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 Wie schnell schließt sich die Lücke?")
st.caption("Obere Schranke = der Master (erreichbar), untere = Farley-Schranke (nicht besser möglich). Beim Ein-Gut-Fluss oder Cutting-Stock kennt man das Tailing-off: die letzten Prozent kosten viele Runden. Wie ist es hier?")
if dist is None:
    st.info("Für die Verteilung über viele Netze ein zufälliges Netz wählen.")
else:
    n_d = dist["n_seeds"]
    rows = []
    for tol, label in ((0.05, "höchstens 5 %"), (0.01, "höchstens 1 %"), (0.001, "höchstens 0,1 %"), (0.0, "Optimum")):
        r_mean = sum(dist["gap_rounds"][tol]) / n_d
        rows.append((label, _f(r_mean, 1), _share(r_mean / dist["rounds_mean"])))
    st.table({"Lücke": [r[0] for r in rows], "Runden (Mittel)": [r[1] for r in rows], "Anteil aller Runden": [r[2] for r in rows]})
    st.caption(f"Über {n_d} feste Netze. Die Schranke ist erst spät brauchbar: solange ein Gut noch keinen Pfad hat, steht in der Schranke seine ganze Nachfrage mal M (das Tausendfache einer Einheit Kosten) - das Optimum wird kaum später erreicht als die enge Lücke.")

st.subheader("🔬 Welche Option hilft?")
st.caption("Vier Stellschrauben der Column Generation, über 100 feste Netze mit den Einstellungen oben: ein oder alle Güter je Runde, Start aus dem Nacheinander-Fahren, Glättung der Preise - und die Negativkontrolle ohne die Preise der Gut-Obergrenzen.")
if dist is None:
    st.info("Für dieses Experiment ein zufälliges Netz wählen.")
else:
    if st.button("Alle Optionen über 100 Netze durchrechnen", key="options_start"):
        st.session_state["options_on"] = True
    if st.session_state.get("options_on"):
        ot = ev.options_table(params)
        st.plotly_chart(build_options(ot), width="stretch", key="options_chart")
        st.table({"Option": [r["name"] for r in ot], "Runden": [_f(r["rounds"], 1) for r in ot], "Spalten": [_f(r["columns"], 1) for r in ot], "Iterationen": [_f(r["iterations"], 0) for r in ot],
                  "im Optimum": [_share(r["exact"]) for r in ot]})
        base, one, warm, a5, a8, neg = ot
        st.caption(f"Mittel über 100 feste Netze. Alle Güter je Runde: {_f(base['rounds'], 1)} Runden gegen {_f(one['rounds'], 1)} bei nur einem Pfad je Runde. Der Start aus dem Nacheinander-Fahren: {_f(warm['rounds'], 1)} Runden. "
                   f"Die Glättung hilft nicht ({_f(a5['rounds'], 1)} bzw. {_f(a8['rounds'], 1)} Runden gegen {_f(base['rounds'], 1)}). Ohne die Preise der Gut-Obergrenzen enden nur {_share(neg['exact'])} der Netze im Optimum.")

st.subheader("🔬 Spalten gegen mögliche Pfade")
st.caption("Im dreistufigen Distributionsnetz gibt es je Gut nur wenige Dutzend Pfade. Ein Gitter hat exponentiell viele: hier das volle Gitter (jede Kante da) mit drei Gütern, 5 feste Netze je Größe.")
if st.button("Gitter von 3 × 3 bis 6 × 5 durchrechnen", key="paths_start"):
    st.session_state["paths_on"] = True
if st.session_state.get("paths_on"):
    pt = ev.path_table()
    st.plotly_chart(build_paths(pt), width="stretch", key="paths_chart")
    st.table({"Gitter": [f"{r['size'][0]} × {r['size'][1]}" for r in pt], "mögliche Pfade": [("" if r["exact"] else "≥ ") + _n(r["paths"]) for r in pt], "Variablen": [_n(r["vars"]) for r in pt],
              "Spalten": [_f(r["columns"], 1) for r in pt], "mit Fluss": [_f(r["used"], 1) for r in pt], "Runden": [_f(r["rounds"], 1) for r in pt]})
    st.caption("Mittel über 5 feste Netze je Größe (Kapazität bis 2, Menge bis 4, drei Güter); die Pfade sind exakt gezählt (Tiefensuche). "
               "Die Pfade wachsen explosionsartig, die Spalten der Column Generation und erst recht die Spalten mit Fluss nur langsam.")

st.subheader("🔬 Wann gewinnt Column Generation gegen das Kanten-LP?")
st.caption("Spalten sind weniger als Variablen - aber jede Runde löst den Master neu. Gemessen in Simplex-Iterationen gesamt (Sekunden nur zur Information): volle Gitter von 5 × 4 bis 16 × 10 mit fünf Gütern, 6 feste Netze je Größe.")
if st.button("Gitter von 5 × 4 bis 16 × 10 durchrechnen", key="size_start"):
    st.session_state["size_on"] = True
if st.session_state.get("size_on"):
    sz = ev.size_table()
    st.plotly_chart(build_size(sz), width="stretch", key="size_chart")
    st.table({"Gitter": [f"{r['size'][0]} × {r['size'][1]}" for r in sz], "Variablen": [_n(r["vars"]) for r in sz], "Spalten": [_f(r["columns"], 1) for r in sz], "Runden": [_f(r["rounds"], 1) for r in sz],
              "Iterationen Kanten-LP": [_n(r["lp_iterations"]) for r in sz], "Iterationen CG": [_n(r["cg_iterations"]) for r in sz],
              "Zeit Kanten-LP [ms]": [_f(1000 * r["t_lp"], 0) for r in sz], "Zeit CG [ms]": [_f(1000 * r["t_cg"], 0) for r in sz]})
    st.caption("Median der Sekunden über die Netze, nur zur Information (Python-Pricing und ein neuer scipy-Aufruf je Runde gegen einen einzigen HiGHS-Lauf); die Aussage steht in den Iterationen. "
               "Im gemessenen Bereich gewinnt die Column Generation bei den Spalten (Bruchteil der Variablen), nicht bei der Lösezeit - der Kreuzungspunkt liegt jenseits davon.")

st.markdown("---")

# --- Grenzen -----------------------------------------------------------------------------------------------------------------------------

st.subheader("🚧 Wo die Annahmen enden")
st.markdown(
    """
| Annahme | Was passiert, wenn sie verletzt ist - und wer setzt an |
|---|---|
| **Das LP genügt** | Die Pfad-Mengen dürfen Bruchteile sein. Ganzzahlige Pfade brauchen **Branch-and-Price** (Verzweigen im Master, Pricing bleibt kürzester Weg mit angepassten Längen) - hier nicht gebaut. |
| **Ein exaktes LP ist nötig** | Für sehr große Netze genügt oft ein guter Fluss mit Garantie und ganz ohne LP-Löser. **Ansatzpunkt: Garg–Könemann** (nächstes Stück): dieselben Kürzeste-Wege-Orakel, multiplikative Gewichte statt Duallösung. |
| **Pfade sind billig zu beschreiben** | Pfadlängen, Fahrzeitfenster oder Umschlagszahlen je Pfad machen das Pricing zum beschränkten kürzesten Weg - schwerer, aber genau dafür ist die Pfad-Formulierung da. Hier: nur Kosten. |
| **Die Kanten stehen fest** | Hier gibt es die Kanten; wer sie erst bauen muss, zahlt Fixkosten. **Ansatzpunkt:** Netzwerkdesign mit Fixkosten (Benders-Zerlegung, Slope Scaling). |
| **Der Master ist billig** | scipy startet jeden Master neu (kein Warmstart), Preise zappeln bei degenerierten LPs. Produktive Löser warmstarten und stabilisieren die Preise; hier zeigt das Experiment, dass die Glättung nicht hilft. |
| **Keine Zeit** | Ein Fluss ist eine Momentaufnahme. **Ansatzpunkt:** Zeit-Raum-Netz in der Demo „leercontainer-demo“. |
"""
)
st.caption("Die Netzwerkfluss-Linie ist als Ganzes geplant: Edmonds-Karp, Dinic, Push-Relabel, Successive Shortest Paths, Cycle-Canceling, Cost Scaling, Mehrgüterfluss (gebaut), Column Generation (dieses Stück), Garg-Könemann, Fixkosten-Netzwerkdesign, Benders-Zerlegung und Slope Scaling - bisher sind die ersten acht gebaut.")

st.markdown("---")

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Pfad-Formulierung.** Für Gut $k$ sei $P_k$ die Menge der einfachen $S$-$T$-Pfade im Netz seiner erlaubten Kanten (jeder Pfad enthält genau eine Nachfragekante). Variable $x_p\ge 0$ = Menge auf Pfad $p$, Kosten $c_p=\sum_{e\in p}c_{k,e}$:
$$\min\ \sum_{k}\sum_{p\in P_k}(c_p-M)\,x_p\quad\text{u.d.N.}\quad \sum_{k}\sum_{p\ni e}x_p\le u_e\ \ (e\in E_J),\qquad \sum_{p\in P_k,\,p\ni e}x_p\le b_{k,e}\ \ (k,e\ \text{mit endlicher Grenze}).$$
Ein Kantenfluss zerfällt bei nichtnegativen Kosten in solche Pfade (Flusszerlegung); beide LPs haben denselben Optimalwert.

**Dual und Pricing.** Duale Variablen $\lambda_e\ge 0$ und $\mu_{k,e}\ge 0$. Die reduzierten Kosten von Pfad $p\in P_k$ sind
$$\bar c_p=c_p-M+\sum_{e\in p}\big(\lambda_e\,[e\in E_J]+\mu_{k,e}\big).$$
Der kleinste Wert über $P_k$ ist ein kürzester Weg mit Kantenlänge $c_{k,e}+\lambda_e+\mu_{k,e}\ge 0$ (Dijkstra) abzüglich $M$. Ist er für alle Güter $\ge 0$, erfüllt das Duale des Masters alle Nebenbedingungen des Duals über **allen** Pfaden: der Master ist optimal.

**Untere Schranke (Farley).** Kein Gut kann mehr als seine Gesamtnachfrage $D_k$ fahren. Deshalb gilt für beliebige Preise $\pi=(\lambda,\mu)\ge 0$ mit $\bar c_k^{\min}=\min_{p\in P_k}\bar c_p$:
$$z^\*\ \ge\ -\pi^\top b+\sum_k D_k\cdot\min\!\big(0,\ \bar c_k^{\min}\big),$$
bei den Preisen des Masters ist $-\pi^\top b$ gleich dem Master-Wert.

**Zusammenhang zur Dantzig-Wolfe-Zerlegung.** Die gemeinsamen Kapazitäten koppeln die Güter; ohne sie zerfällt das Problem in $K$ unabhängige Min-Cost-Flows. Column Generation über die Pfade der Güter ist die Dantzig-Wolfe-Zerlegung dieses Blockdiagonalproblems, und das Pricing ist genau der Ein-Gut-Fluss des Vorgängers mit Preisen.

**Glättung (Wentges).** Das Pricing benutzt $\tilde\pi=\alpha\,\hat\pi+(1-\alpha)\,\pi$ mit den Preisen $\hat\pi$ der bisher besten unteren Schranke; findet es damit keine lohnende Spalte, wird mit $\pi$ neu bewertet (Fehlgriff).

Implementiert in `mcg_cg.py` (Master, Pricing, Schranken), `mcg_paths.py` (Pfade zählen, aufzählen, zerlegen), `mcg_model.py` und `mcg_scenario.py` (Netze), `mcg_edge_lp.py` (Kanten-LP als Gegenprobe, HiGHS über `scipy`), `mcg_evaluation.py` (Kennzahlen, Verteilungen, Experimente).
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
