"""Kennzahlen, Urteil und Experimente der Demo (Spalten gegen mögliche Pfade, Konvergenz, Optionen der Column Generation, Größe und Kreuzungspunkt gegen das Kanten-LP).
Rechnet mit ganzen Zahlen (Netze) und HiGHS (Master, Kanten-LP); Vergleiche mit Toleranz."""

import time
from collections import namedtuple
from dataclasses import dataclass
from functools import lru_cache
from statistics import mean, median

import mcg_cg as cg
import mcg_constants as C
import mcg_edge_lp as el
import mcg_model as md
import mcg_paths as paths

TOL = 1e-6
NetParams = namedtuple("NetParams", "net k p d s density spread load seed gw gh gdensity gcap gdem gseed")
Opts = namedtuple("Opts", "per_round start alpha gap ignore_mu")
DEFAULT_OPTS = Opts(C.DEFAULT_PER_ROUND, C.DEFAULT_START, C.DEFAULT_ALPHA, C.DEFAULT_GAP, False)
DEFAULT_PARAMS = NetParams(C.DEFAULT_NET, C.DEFAULT_K, C.DEFAULT_P, C.DEFAULT_D, C.DEFAULT_S, C.DEFAULT_DENSITY, C.DEFAULT_SPREAD, C.DEFAULT_LOAD, C.DEFAULT_SEED,
                           C.DEFAULT_GW, C.DEFAULT_GH, C.DEFAULT_GDENSITY, C.DEFAULT_GCAP, C.DEFAULT_GDEM, C.DEFAULT_GSEED)


def pct(numerator, denominator, digits=1):
    return round(100.0 * numerator / denominator, digits)


def normalise(params):
    """Feste Netze ignorieren alle Zufallsregler: gleiche Netze unter demselben Schlüssel (sonst würden sie mehrfach berechnet)."""
    if params.net in C.FIXED_NETS:
        return DEFAULT_PARAMS._replace(net=params.net, k=0)
    return params


def build(params):
    if params.net == "gap":
        return md.gap_net()
    if params.net == "preis":
        return md.preis_net()
    if params.net == "grid":
        return md.generate_grid(params.gw, params.gh, params.gdensity, params.gcap, params.gdem, params.k, params.gseed)
    return md.generate_mcf(params.p, params.d, params.s, params.density, params.spread, params.load, params.seed, params.k)


def with_seed(params, seed):
    return params._replace(gseed=seed) if params.net == "grid" else params._replace(seed=seed)


@dataclass(frozen=True)
class Analysis:
    mcf: object
    lp: object             # Kanten-LP (Gegenprobe und Vergleich)
    cg: object             # CGResult
    paths: tuple           # ((Anzahl, exakt), ...) je Gut
    opts: Opts


def run_cg(mcf, opts):
    return cg.column_generation(mcf, per_round=opts.per_round, start=opts.start, alpha=opts.alpha, gap_tol=opts.gap, ignore_mu=opts.ignore_mu)


@lru_cache(maxsize=64)
def analyse(params, opts=DEFAULT_OPTS):
    mcf = build(params)
    lp = el.solve_lp(mcf)
    result = run_cg(mcf, opts)
    counts = tuple(paths.count_paths(mcf, k, C.PATH_LIMIT, C.PATH_BUDGET) for k in range(mcf.K))
    return Analysis(mcf, lp, result, counts, opts)


def gap_of(rd):
    """Relative Lücke (obere gegen untere Schranke) einer Runde, bezogen auf den Betrag des Master-Werts; unendlich, solange der Master leer ist."""
    return (rd.obj - rd.lb) / abs(rd.obj) if rd.obj < -TOL else float("inf")


def rounds_to_gap(result, tol):
    """Erste Runde, in der die relative Lücke höchstens `tol` beträgt (sonst die letzte)."""
    for rd in result.rounds:
        if gap_of(rd) <= tol + 1e-12:
            return rd.r
    return result.rounds[-1].r


def used_columns(result):
    return sum(1 for a in result.amounts if a > TOL)


def total_paths(counts):
    """(Summe der Pfade, alle exakt gezählt)."""
    return sum(n for n, _ in counts), all(e for _, e in counts)


def verdict(a):
    """(Stufe, Code, Daten): 'optimal' = Column Generation endet im LP-Optimum, 'gap' = angehalten bei vorgegebener Lücke, 'stuck' = das Pricing kennt keine neue Spalte, der Wert ist aber falsch (Negativkontrolle),
    'nothing' = nichts lieferbar."""
    mcf, lp, r = a.mcf, a.lp, a.cg
    demand = mcf.total_demand()
    last = r.rounds[-1]
    n_paths, exact = total_paths(a.paths)
    binding = [e for e in range(mcf.m) if mcf.joint[e] and last.lam[e] > TOL]
    data = {
        "K": mcf.K, "m": mcf.m, "demand": demand, "lp_delivered": lp.total_delivered, "lp_cost": lp.cost, "lp_obj": lp.objective, "lp_vars": lp.n_vars, "lp_iterations": lp.iterations,
        "cg_delivered": r.total_delivered, "cg_cost": r.cost, "cg_obj": r.obj, "value_diff": r.obj - lp.objective, "delivery_gap": lp.total_delivered - r.total_delivered,
        "rounds": r.n_rounds, "columns": r.n_columns, "used": used_columns(r), "iterations": r.iterations, "scans": r.scans, "misprices": r.misprices, "lp_solves": r.lp_solves,
        "paths": n_paths, "paths_exact": exact, "binding": binding, "n_binding": len(binding), "lb": r.rounds[-1].lb, "gap": gap_of(last),
        "fractional": lp.fractional, "share": pct(lp.total_delivered, demand) if demand else None, "first_delivered": float(sum(r.rounds[min(1, len(r.rounds) - 1)].delivered)),
        "column_share": pct(r.n_columns, lp.n_vars) if lp.n_vars else None,
    }
    if r.stuck:
        return "error", "stuck", data
    if lp.total_delivered < TOL:
        return "warning", "nothing", data
    if r.gap_stop and abs(r.obj - lp.objective) > TOL:
        return "info", "gap", data
    return "success", "optimal", data


# --- Verteilungen über feste Netze ---------------------------------------------------------------------------------------------------------

@lru_cache(maxsize=32)
def _runs(params, opts, seeds=C.DIST_SEEDS):
    out = []
    for seed in seeds:
        mcf = build(with_seed(params, seed))
        lp = el.solve_lp(mcf)
        r = run_cg(mcf, opts)
        out.append((mcf, lp, r))
    return out


def _row(mcf, lp, r):
    return {
        "rounds": r.n_rounds, "columns": r.n_columns, "used": used_columns(r), "vars": lp.n_vars, "cg_iterations": r.iterations, "lp_iterations": lp.iterations, "scans": r.scans, "misprices": r.misprices,
        "exact": bool(r.optimal and abs(r.obj - lp.objective) < TOL), "stuck": r.stuck, "delivered": r.total_delivered, "lp_delivered": lp.total_delivered, "demand": mcf.total_demand(),
        "first_delivered": float(sum(r.rounds[min(1, len(r.rounds) - 1)].delivered)),
    }


def distribution(params, opts=DEFAULT_OPTS, seeds=C.DIST_SEEDS):
    """Verteilungen über feste Netze mit den Einstellungen des Nutzers (nur der Seed wechselt). Rückgabe: Spalten je Kennzahl und Mittelwerte."""
    params = normalise(params)
    runs = _runs(params, opts, seeds)
    rows = [_row(*t) for t in runs]
    cols = {key: [r[key] for r in rows] for key in rows[0]}
    gaps = {tol: [rounds_to_gap(t[2], tol) for t in runs] for tol in (0.05, 0.01, 0.001, 0.0)}
    n = len(rows)
    return {
        "n_seeds": n, "cols": cols, "gap_rounds": gaps, "share_exact": sum(cols["exact"]) / n, "share_stuck": sum(cols["stuck"]) / n,
        "rounds_mean": mean(cols["rounds"]), "columns_mean": mean(cols["columns"]), "used_mean": mean(cols["used"]), "vars_mean": mean(cols["vars"]),
        "cg_iterations_mean": mean(cols["cg_iterations"]), "lp_iterations_mean": mean(cols["lp_iterations"]), "scans_mean": mean(cols["scans"]), "misprices_mean": mean(cols["misprices"]),
        "first_delivered_mean": mean(cols["first_delivered"]), "lp_delivered_mean": mean(cols["lp_delivered"]), "demand_mean": mean(cols["demand"]),
    }


# --- Experimente -----------------------------------------------------------------------------------------------------------------------------

VARIANTS = (
    ("Der beste Pfad je Gut, leer gestartet (Standard)", Opts("alle", "leer", 0.0, 0.0, False)),
    ("Nur der insgesamt beste Pfad je Runde", Opts("eine", "leer", 0.0, 0.0, False)),
    ("Start aus dem Nacheinander-Fahren", Opts("alle", "nacheinander", 0.0, 0.0, False)),
    ("Preise geglättet (α = 0,5)", Opts("alle", "leer", 0.5, 0.0, False)),
    ("Preise geglättet (α = 0,8)", Opts("alle", "leer", 0.8, 0.0, False)),
    ("Negativkontrolle: Preise der Gut-Obergrenzen ignoriert", Opts("alle", "leer", 0.0, 0.0, True)),
)


@lru_cache(maxsize=8)
def options_table(params):
    """Alle Optionen über 100 feste Netze mit denselben Netzeinstellungen: Runden, Spalten, Simplex-Iterationen, angesehene Kanten, Fehlgriffe des geglätteten Pricings, Anteil im Optimum."""
    params = normalise(params)
    rows = []
    for name, opts in VARIANTS:
        rs = [_row(*t) for t in _runs(params, opts)]
        n = len(rs)
        rows.append({"name": name, "opts": opts, "rounds": mean(r["rounds"] for r in rs), "columns": mean(r["columns"] for r in rs), "iterations": mean(r["cg_iterations"] for r in rs),
                     "scans": mean(r["scans"] for r in rs), "misprices": mean(r["misprices"] for r in rs), "exact": sum(r["exact"] for r in rs) / n, "stuck": sum(r["stuck"] for r in rs) / n})
    return rows


@lru_cache(maxsize=2)
def path_table(sizes=C.GRID_SIZES, K=3, seeds=C.PATH_SEEDS):
    """Volle Gitter (Dichte 100 %, Kapazität bis 2, Menge bis 4, drei Güter): mögliche Pfade gegen Spalten im Optimum."""
    rows = []
    for w, h in sizes:
        per = []
        for seed in seeds:
            mcf = md.generate_grid(w, h, 100, 2, 4, K, seed)
            r = cg.column_generation(mcf)
            counts = [paths.count_paths(mcf, k, C.TABLE_PATH_LIMIT, C.TABLE_PATH_BUDGET) for k in range(K)]
            per.append((total_paths(counts), r.n_columns, used_columns(r), r.n_rounds, el.solve_lp(mcf).n_vars))
        rows.append({"size": (w, h), "paths": mean(p[0][0] for p in per), "exact": all(p[0][1] for p in per), "columns": mean(p[1] for p in per), "used": mean(p[2] for p in per),
                     "rounds": mean(p[3] for p in per), "vars": mean(p[4] for p in per)})
    return rows


@lru_cache(maxsize=2)
def size_table(sizes=C.SCALE_SIZES, K=5, seeds=C.SIZE_SEEDS):
    """Volle Gitter wachsender Größe (Dichte 100 %, Kapazität bis 2, Menge bis 5): Variablen des Kanten-LP gegen Spalten, Simplex-Iterationen gesamt und Sekunden (nur zur Information)."""
    rows = []
    for w, h in sizes:
        per = []
        for seed in seeds:
            mcf = md.generate_grid(w, h, 100, 2, 5, K, seed)
            t = time.perf_counter()
            lp = el.solve_lp(mcf)
            t_lp = time.perf_counter() - t
            t = time.perf_counter()
            r = cg.column_generation(mcf)
            t_cg = time.perf_counter() - t
            per.append((lp.n_vars, r.n_columns, lp.iterations, r.iterations, r.n_rounds, t_lp, t_cg, abs(lp.objective - r.obj) < TOL))
        rows.append({"size": (w, h), "vars": mean(p[0] for p in per), "columns": mean(p[1] for p in per), "lp_iterations": mean(p[2] for p in per), "cg_iterations": mean(p[3] for p in per),
                     "rounds": mean(p[4] for p in per), "t_lp": median(p[5] for p in per), "t_cg": median(p[6] for p in per), "exact": all(p[7] for p in per)})
    return rows


# --- Anzeige-Helfer ---------------------------------------------------------------------------------------------------------------------------

def path_label(mcf, edges):
    """Knotenfolge eines Pfades ohne S und T, mit den Kurzbeschriftungen der Karte (im Streckennetz die Koordinaten)."""
    net = mcf.net
    out = []
    for v in paths.path_nodes(mcf, edges):
        if v in (net.s, net.t):
            continue
        out.append(net.labels[v] or net.names[v].replace("Knoten ", "").replace(" ", ""))
    return " → ".join(out)


def column_rounds(result):
    """Runde, in der jede Spalte in den Master kam (0 = Startspalten)."""
    first = {}
    for rd in result.rounds:
        for j in range(rd.n_columns):
            first.setdefault(j, rd.r)
    return [first[j] for j in range(len(result.columns))]
