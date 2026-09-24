"""Pfad-Formulierung und Column Generation für den Mehrgüterfluss.

**Master (Pfad-LP):** eine Variable x_c >= 0 je bekanntem Pfad c (= Spalte) eines Guts k. Zeilen: gemeinsame Kapazität je gemeinsamer Kante (Summe aller Pfade über die Kante <= u_e) und je (Gut, Kante)
mit endlicher Obergrenze (Angebots- und Nachfragekanten: Summe der Pfade von Gut k über die Kante <= ub[k][e]). Ziel: Kosten des Pfades minus M je Einheit Lieferung (jeder Pfad endet auf genau einer Nachfragekante).
Die leere Spaltenmenge (x = 0) ist zulässig; die Schattenpreise lambda_e (gemeinsame Kanten) und mu_{k,e} (Gut-Obergrenzen) sind die Duallösung der Zeilen.

**Pricing:** für jedes Gut ein kürzester Weg (Dijkstra) mit Kantenlänge cost(k, e) + lambda_e + mu_{k,e} (nichtnegativ). Die reduzierten Kosten des Pfades sind Länge - M; ist der kürzeste Weg kürzer als M,
lohnt sich der Pfad als neue Spalte. Ohne lohnenden Pfad in allen Gütern ist das Pfad-LP mit allen (exponentiell vielen) Pfaden optimal - ohne dass man sie je alle gesehen hat.

**Untere Schranke (Farley):** für beliebige Preise pi >= 0 gilt  z* >= -pi·b + sum_k D_k · min(0, kürzeste reduzierte Kosten von Gut k), D_k = Gesamtnachfrage von Gut k (mehr als D_k kann kein Gut fahren).
Bei den Preisen des Master-LP ist -pi·b gleich dem Master-Wert, die Schranke also Master-Wert + sum_k D_k · min(0, rc_k).

Optionen: Spalten je Runde (`per_round`: "alle" = der beste Pfad je Gut, "eine" = nur der insgesamt beste), Start (`start`: "leer" oder aus dem Nacheinander-Fahren), Glättung der Preise nach Wentges
(`alpha`: Preise für das Pricing = alpha · bester bisheriger Preisvektor + (1 - alpha) · aktuelle Preise; findet das Pricing damit nichts, wird mit den echten Preisen neu bewertet), Abbruch bei relativer Lücke
(`gap_tol`), und die Negativkontrolle `ignore_mu` (die Preise der Gut-Obergrenzen im Pricing weglassen).
"""

import heapq
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

import mcg_edge_lp as el
import mcg_paths as paths

BIG = 10 ** 6
RC_TOL = 1e-9


@dataclass(frozen=True)
class Column:
    k: int
    edges: tuple            # Kantenindizes von S bis T
    cost: float             # echte Kosten je Einheit (ohne Belohnung)


@dataclass
class Round:
    """Zustand nach dem Lösen des Masters einer Runde und das Ergebnis des Pricings mit den Preisen dieser Runde."""
    r: int
    obj: float                       # Master-Wert (obere Schranke)
    lb: float                        # beste untere Schranke bis einschließlich dieser Runde
    lb_here: float                   # untere Schranke mit den Preisen dieser Runde
    n_columns: int
    amounts: np.ndarray              # Menge je Spalte
    lam: np.ndarray                  # (m,) Preise der gemeinsamen Kanten
    mu: np.ndarray                   # (K, m) Preise der Gut-Obergrenzen
    x: np.ndarray                    # (K, m) Kantenfluss des Masters
    delivered: tuple
    cost: float
    rc: tuple                        # kürzeste reduzierte Kosten je Gut mit den Preisen des Masters (inf: kein Weg)
    new: tuple                       # Indizes der in dieser Runde gefundenen und aufgenommenen Spalten
    iterations: int                  # Simplex-Iterationen dieses Master-Laufs
    scans: int                       # in den Dijkstra-Läufen dieser Runde angesehene Kanten
    misprice: bool = False           # das geglättete Pricing fand nichts, es wurde mit den echten Preisen wiederholt


@dataclass
class CGResult:
    columns: list
    rounds: list
    optimal: bool                    # kein Pfad mit negativen reduzierten Kosten mehr
    stuck: bool                      # Negativkontrolle: das Pricing lieferte nur schon bekannte Spalten
    gap_stop: bool
    obj: float
    cost: float
    delivered: tuple
    x: np.ndarray
    amounts: np.ndarray
    lp_solves: int
    iterations: int
    scans: int
    misprices: int
    config: dict = field(default_factory=dict)

    @property
    def n_columns(self):
        return len(self.columns)

    @property
    def n_rounds(self):
        return len(self.rounds) - 1        # Runde 0 = Start (Master vor jedem Pricing)

    @property
    def total_delivered(self):
        return float(sum(self.delivered))


class Master:
    """Das Pfad-LP: Zeilen fest, Spalten wachsen."""

    def __init__(self, mcf):
        self.mcf = mcf
        K, m = mcf.K, mcf.m
        self.joint_rows = {e: i for i, e in enumerate(e for e in range(m) if mcf.joint[e])}
        self.ub_rows = {}
        for k in range(K):
            for e in range(m):
                if 0 < mcf.ub[k][e] < BIG:
                    self.ub_rows[(k, e)] = len(self.joint_rows) + len(self.ub_rows)
        self.b = np.array([float(mcf.net.arcs[e][2]) for e in self.joint_rows] + [float(mcf.ub[k][e]) for (k, e) in self.ub_rows], dtype=float)
        self.columns = []
        self.keys = set()

    def add(self, k, edges):
        key = (k, tuple(edges))
        if key in self.keys:
            return False
        self.keys.add(key)
        self.columns.append(Column(k, tuple(edges), float(paths.path_cost(self.mcf, k, edges))))
        return True

    def objective(self, col):
        return col.cost - self.mcf.M

    def solve(self):
        """Master lösen. Rückgabe (Menge je Spalte, Zielwert, lambda (m), mu (K, m), Iterationen)."""
        mcf = self.mcf
        lam = np.zeros(mcf.m)
        mu = np.zeros((mcf.K, mcf.m))
        if not self.columns:
            return np.zeros(0), 0.0, lam, mu, 0
        rows, cols = [], []
        for j, col in enumerate(self.columns):
            for e in col.edges:
                if mcf.joint[e]:
                    rows.append(self.joint_rows[e]); cols.append(j)
                key = (col.k, e)
                if key in self.ub_rows:
                    rows.append(self.ub_rows[key]); cols.append(j)
        a = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(self.b), len(self.columns))).tocsr()
        c = np.array([self.objective(col) for col in self.columns])
        res = linprog(c, A_ub=a, b_ub=self.b, bounds=(0, None), method="highs")
        if res.status != 0:
            raise RuntimeError(res.message)
        marg = np.maximum(0.0, -res.ineqlin.marginals)
        for e, i in self.joint_rows.items():
            lam[e] = marg[i]
        for (k, e), i in self.ub_rows.items():
            mu[k, e] = marg[i]
        amounts = np.where(np.abs(res.x) < 1e-9, 0.0, res.x)
        return amounts, float(res.fun), lam, mu, int(getattr(res, "nit", 0))

    def dual_bound(self, lam, mu):
        """-pi·b für Preise pi = (lambda, mu)."""
        total = 0.0
        for e, i in self.joint_rows.items():
            total += lam[e] * self.b[i]
        for (k, e), i in self.ub_rows.items():
            total += mu[k, e] * self.b[i]
        return -total


def price(mcf, adj, k, lam, mu, ignore_mu=False):
    """Dijkstra für Gut k mit Kantenlänge cost + lambda_e + mu_{k,e}. Rückgabe (kürzeste Länge, Kantentupel oder None, angesehene Kanten)."""
    net = mcf.net
    dist = {net.s: 0.0}
    prev = {}
    heap = [(0.0, net.s)]
    done = set()
    scans = 0
    while heap:
        d, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)
        if u == net.t:
            break
        for e, v in adj[u]:
            scans += 1
            length = mcf.cost(k, e) + (lam[e] if mcf.joint[e] else 0.0) + (0.0 if ignore_mu else mu[k, e])
            nd = d + length
            if nd < dist.get(v, float("inf")) - 1e-12:
                dist[v] = nd
                prev[v] = (u, e)
                heapq.heappush(heap, (nd, v))
    if net.t not in dist:
        return float("inf"), None, scans
    edges, v = [], net.t
    while v != net.s:
        u, e = prev[v]
        edges.append(e)
        v = u
    edges.reverse()
    return dist[net.t], tuple(edges), scans


def _lower_bound(master, mcf, lam, mu, dists):
    """Farley-Schranke für die Preise (lam, mu) mit den kürzesten Längen dists (je Gut)."""
    z = master.dual_bound(lam, mu)
    for k, dk in enumerate(dists):
        if dk != float("inf"):
            z += mcf.demand(k) * min(0.0, dk - mcf.M)
    return z


def _warm_columns(mcf):
    """Startspalten aus dem Nacheinander-Fahren: Pfadzerlegung des Flusses jedes Guts."""
    seq = el.solve_sequential(mcf)
    cols = []
    for k in range(mcf.K):
        for edges, _ in paths.decompose_flow(mcf, seq.x[k]):
            cols.append((k, edges))
    return cols


def column_generation(mcf, per_round="alle", start="leer", alpha=0.0, gap_tol=0.0, max_rounds=500, ignore_mu=False):
    master = Master(mcf)
    K = mcf.K
    adj = [paths.adjacency(mcf, k) for k in range(K)]
    if start == "nacheinander":
        for k, edges in _warm_columns(mcf):
            master.add(k, edges)
    rounds = []
    best_lb = -float("inf")
    center = None                      # Preise des besten Lagrange-Werts
    lp_solves = iterations = scans_total = misprices = 0
    optimal = stuck = gap_stop = False
    for r in range(max_rounds + 1):
        amounts, obj, lam, mu, nit = master.solve()
        lp_solves += 1
        iterations += nit
        x = np.zeros((K, mcf.m))
        for j, col in enumerate(master.columns):
            for e in col.edges:
                x[col.k, e] += amounts[j]
        delivered = tuple(float(sum(amounts[j] for j, col in enumerate(master.columns) if col.k == k)) for k in range(K))
        cost = float(sum(amounts[j] * col.cost for j, col in enumerate(master.columns)))
        # Pricing mit den echten Preisen des Masters (für Beweis, Schranke und Anzeige)
        found = [price(mcf, adj[k], k, lam, mu, ignore_mu) for k in range(K)]
        scans = sum(f[2] for f in found)
        rc = tuple(f[0] - mcf.M for f in found)
        lb_true = _lower_bound(master, mcf, lam, mu, [f[0] for f in found]) if not ignore_mu else -float("inf")
        best_lb = max(best_lb, lb_true)
        if lb_true >= best_lb - 1e-12:
            center = (lam.copy(), mu.copy())
        true_c = [(found[k][0] - mcf.M, k, found[k][1]) for k in range(K) if found[k][1] is not None and found[k][0] - mcf.M < -RC_TOL]
        misprice = False
        use = true_c
        if true_c and alpha > 0 and center is not None:
            lam_s = alpha * center[0] + (1 - alpha) * lam
            mu_s = alpha * center[1] + (1 - alpha) * mu
            found_s = [price(mcf, adj[k], k, lam_s, mu_s, ignore_mu) for k in range(K)]
            scans += sum(f[2] for f in found_s)
            lb_s = _lower_bound(master, mcf, lam_s, mu_s, [f[0] for f in found_s]) if not ignore_mu else -float("inf")
            if lb_s > best_lb:
                best_lb, center = lb_s, (lam_s.copy(), mu_s.copy())
            smooth_c = [(found_s[k][0] - mcf.M, k, found_s[k][1]) for k in range(K)
                        if found_s[k][1] is not None and found_s[k][0] - mcf.M < -RC_TOL and (k, found_s[k][1]) not in master.keys]
            if smooth_c:
                use = smooth_c
            else:
                misprice = True
                misprices += 1
        fresh = [c for c in use if (c[1], c[2]) not in master.keys]
        entry = Round(r, obj, best_lb, lb_true, len(master.columns), amounts, lam, mu, x, delivered, cost, rc, (), nit, scans, misprice)
        rounds.append(entry)
        scans_total += scans
        if not true_c:
            optimal = True
            break
        if not fresh:
            stuck = True
            break
        if gap_tol > 0 and obj < 0 and (obj - best_lb) <= gap_tol * abs(obj):
            gap_stop = True
            break
        if per_round == "eine":
            fresh = [min(fresh)]
        new = []
        for _, k, edges in fresh:
            if master.add(k, edges):
                new.append(len(master.columns) - 1)
        entry.new = tuple(new)
    else:
        stuck = True
    last = rounds[-1]
    return CGResult(master.columns, rounds, optimal, stuck, gap_stop, last.obj, last.cost, last.delivered, last.x, last.amounts,
                    lp_solves, iterations, scans_total, misprices, dict(per_round=per_round, start=start, alpha=alpha, gap_tol=gap_tol, ignore_mu=ignore_mu))


def solve_all_paths(mcf, limit=20000):
    """Gegenprobe: das Pfad-LP mit allen einfachen Pfaden aller Güter (Aufzählung) - nur für kleine Netze. Rückgabe (Zielwert, Anzahl Spalten)."""
    master = Master(mcf)
    for k in range(mcf.K):
        for edges in paths.enumerate_paths(mcf, k, limit):
            master.add(k, edges)
    _, obj, _, _, _ = master.solve()
    return obj, len(master.columns)
