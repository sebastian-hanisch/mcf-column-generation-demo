"""Lösungswege für das Mehrgüter-Modell: jedes Gut allein, Güter nacheinander, das gemeinsame LP (HiGHS), das ganzzahlige Programm und die Entkopplung durch Preise.

Kanten-LP: Variablen x[k][e] >= 0 (K·m Stück). Nebenbedingungen: Flusserhaltung je Gut an jedem inneren Knoten, gemeinsame Kapazität sum_k x[k][e] <= u[e] auf den gemeinsamen Kanten, Obergrenzen ub[k][e].
Ziel: minimiere sum cost[k][e]·x[k][e] - M · (Lieferung). Die Schattenpreise lambda[e] >= 0 der gemeinsamen Kapazitäten sind die Duallösung.

Die Einzelgut-Verfahren (allein, nacheinander, Entkopplung) nutzen Successive Shortest Paths (`mcg_ssp.py`, Kopie der SSP-Demo): ein Gut ist ein gewöhnlicher Min-Cost-Flow;
weil die Wegpreise nicht fallen, ist der Fluss mit allen Runden, deren Preis unter M liegt, der beste Fluss unter der Belohnung M je Einheit (Belohnung = Weg lohnt sich, solange sein Preis < M).
"""

from dataclasses import dataclass
from fractions import Fraction
from math import lcm

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import coo_matrix

import mcg_scenario as sc
import mcg_ssp as ssp

FRACTION_TOL = 1e-6


@dataclass(frozen=True)
class Solution:
    x: np.ndarray            # (K, m) Fluss je Gut und Kante
    objective: float         # Kosten - M · Lieferung
    cost: float              # echte Kosten (ohne Belohnung)
    delivered: tuple         # Lieferung je Gut
    duals: np.ndarray        # (m,) Schattenpreise der gemeinsamen Kapazitäten (0 auf anderen Kanten); leer bei ILP
    iterations: int
    n_vars: int
    n_eq: int
    n_ub: int
    status: str

    @property
    def total_delivered(self):
        return float(sum(self.delivered))

    @property
    def max_fraction(self):
        return float(np.max(np.abs(self.x - np.round(self.x)))) if self.x.size else 0.0

    @property
    def fractional(self):
        return self.max_fraction > FRACTION_TOL

    @property
    def n_fractional(self):
        return int(np.sum(np.abs(self.x - np.round(self.x)) > FRACTION_TOL))


def _matrices(mcf):
    """Zielvektor, Gleichungen (Flusserhaltung je Gut), Ungleichungen (gemeinsame Kapazität), Grenzen."""
    K, m, net = mcf.K, mcf.m, mcf.net
    c = np.zeros(K * m)
    for k in range(K):
        for e in range(m):
            c[k * m + e] = -mcf.M if mcf.reward[e] else mcf.cost(k, e)
    inner = [v for v in range(net.n) if v not in (net.s, net.t)]
    row_of = {v: i for i, v in enumerate(inner)}
    rows, cols, vals = [], [], []
    for k in range(K):
        for e, (u, v, _, _, _) in enumerate(net.arcs):
            if v in row_of:
                rows.append(k * len(inner) + row_of[v]); cols.append(k * m + e); vals.append(1.0)
            if u in row_of:
                rows.append(k * len(inner) + row_of[u]); cols.append(k * m + e); vals.append(-1.0)
    a_eq = coo_matrix((vals, (rows, cols)), shape=(K * len(inner), K * m)).tocsr()
    joint = [e for e in range(m) if mcf.joint[e]]
    rows, cols, vals = [], [], []
    for i, e in enumerate(joint):
        for k in range(K):
            rows.append(i); cols.append(k * m + e); vals.append(1.0)
    a_ub = coo_matrix((vals, (rows, cols)), shape=(len(joint), K * m)).tocsr()
    b_ub = np.array([net.arcs[e][2] for e in joint], dtype=float)
    ub = np.array([[float(mcf.ub[k][e]) if mcf.ub[k][e] < 10 ** 6 else np.inf for e in range(m)] for k in range(K)]).ravel()
    return c, a_eq, np.zeros(a_eq.shape[0]), a_ub, b_ub, ub, joint


def _solution(mcf, xv, objective, duals, nit, shapes, status):
    K, m = mcf.K, mcf.m
    x = np.asarray(xv, dtype=float).reshape(K, m)
    x[np.abs(x) < 1e-9] = 0.0
    delivered = tuple(float(sum(x[k, e] for e in range(m) if mcf.reward[e])) for k in range(K))
    cost = float(sum(mcf.cost(k, e) * x[k, e] for k in range(K) for e in range(m) if not mcf.reward[e]))
    return Solution(x, float(objective), cost, delivered, duals, int(nit), *shapes, status)


def solve_lp(mcf, method="highs"):
    """Gemeinsames LP mit HiGHS. Die Duallösung sind die Schattenpreise der gemeinsamen Kapazitäten (auf die Kanten verteilt)."""
    c, a_eq, b_eq, a_ub, b_ub, ub, joint = _matrices(mcf)
    res = linprog(c, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=list(zip(np.zeros_like(ub), np.where(np.isinf(ub), None, ub))), method=method)
    if res.status != 0:
        raise RuntimeError(res.message)
    duals = np.zeros(mcf.m)
    for i, e in enumerate(joint):
        duals[e] = max(0.0, -float(res.ineqlin.marginals[i]))
    return _solution(mcf, res.x, res.fun, duals, getattr(res, "nit", 0), (len(c), a_eq.shape[0], a_ub.shape[0]), "optimal")


def solve_ilp(mcf):
    """Ganzzahliges Programm (branch and cut in HiGHS): jede Flusseinheit unteilbar."""
    c, a_eq, b_eq, a_ub, b_ub, ub, joint = _matrices(mcf)
    res = milp(c, constraints=[LinearConstraint(a_eq, b_eq, b_eq), LinearConstraint(a_ub, -np.inf, b_ub)], integrality=np.ones(len(c)), bounds=Bounds(np.zeros_like(ub), ub))
    if res.status != 0:
        raise RuntimeError(res.message)
    return _solution(mcf, np.round(res.x), res.fun, np.zeros(0), 0, (len(c), a_eq.shape[0], a_ub.shape[0]), "optimal")


# --- Einzelgut-Verfahren über SSP -----------------------------------------------------------------------------------------------------

def _good_net(mcf, k, cap, cost_fn, scale=1):
    """Einzelgutnetz von Gut k: Kapazität cap[e] (auf gemeinsamen Kanten die verbleibende, sonst die Obergrenze), Kosten cost_fn(e) mal scale."""
    dk = mcf.demand(k)
    arcs = []
    for e, (u, v, _, _, kind) in enumerate(mcf.net.arcs):
        arcs.append((u, v, int(min(mcf.ub[k][e], cap[e], dk)), int(cost_fn(e)), kind))
    net = mcf.net
    return sc.Net(net.names, net.labels, net.pos, tuple(arcs), net.s, net.t, net.logistic)


def _best_flow(mcf, gnet, threshold):
    """Fluss mit allen SSP-Runden, deren Wegpreis unter der Schwelle (der Belohnung) liegt."""
    r = ssp.ssp(gnet, "dijkstra", None, keep_trace=True)
    flow = [0] * gnet.m
    for rnd in r.rounds:
        if rnd.price >= threshold:
            break
        flow = list(rnd.flow_after)
    return flow


def _result_from_flows(mcf, flows):
    x = np.array(flows, dtype=float)
    delivered = tuple(float(sum(x[k, e] for e in range(mcf.m) if mcf.reward[e])) for k in range(mcf.K))
    cost = float(sum(mcf.cost(k, e) * x[k, e] for k in range(mcf.K) for e in range(mcf.m) if not mcf.reward[e]))
    return x, delivered, cost


def solve_single(mcf):
    """Jedes Gut allein, ohne Rücksicht auf die anderen (volle Kapazität für jedes): billigster Fluss je Gut. Summe der Flüsse kann die gemeinsamen Kapazitäten überschreiten.
    Rückgabe (Lösung, Überlastung je Kante: Summe - Kapazität, nur > 0)."""
    caps = [a[2] for a in mcf.net.arcs]
    flows = [_best_flow(mcf, _good_net(mcf, k, caps, lambda e, k=k: mcf.cost(k, e)), mcf.M) for k in range(mcf.K)]
    x, delivered, cost = _result_from_flows(mcf, flows)
    over = {e: float(x[:, e].sum() - caps[e]) for e in range(mcf.m) if mcf.joint[e] and x[:, e].sum() > caps[e]}
    objective = cost - mcf.M * sum(delivered)
    return Solution(x, objective, cost, delivered, np.zeros(0), 0, mcf.K * mcf.m, 0, 0, "unabhängig"), over


def solve_sequential(mcf, order=None):
    """Güter nacheinander: jedes Gut bekommt den billigsten Fluss auf den Restkapazitäten, die die vorigen übrig lassen. Immer zulässig, aber reihenfolgeabhängig."""
    order = list(range(mcf.K)) if order is None else list(order)
    left = [a[2] for a in mcf.net.arcs]
    flows = [None] * mcf.K
    for k in order:
        flow = _best_flow(mcf, _good_net(mcf, k, left, lambda e, k=k: mcf.cost(k, e)), mcf.M)
        flows[k] = flow
        for e in range(mcf.m):
            if mcf.joint[e]:
                left[e] -= flow[e]
    x, delivered, cost = _result_from_flows(mcf, flows)
    return Solution(x, cost - mcf.M * sum(delivered), cost, delivered, np.zeros(0), 0, mcf.K * mcf.m, 0, 0, "nacheinander")


def decouple(mcf, prices, max_denominator=64):
    """Entkopplung: mit Schattenpreisen lambda auf den gemeinsamen Kanten ist jedes Gut ein gewöhnlicher Min-Cost-Flow mit Kosten cost + lambda. Rückgabe (Lagrange-Wert, Flüsse je Gut).
    Lagrange-Wert = sum_k (kleinste Kosten von Gut k mit Preisen) - sum_e lambda_e · u_e; bei optimalen Preisen gleich dem LP-Optimum (starke Dualität)."""
    fr = [Fraction(float(p)).limit_denominator(max_denominator) for p in prices]
    denom = lcm(1, *[f.denominator for f in fr])
    lam = [int(f * denom) for f in fr]                       # lambda · denom
    flows, total = [], Fraction(0)
    big = [BIG_CAP for _ in mcf.net.arcs]
    for k in range(mcf.K):
        gnet = _good_net(mcf, k, big, lambda e, k=k: denom * mcf.cost(k, e) + (lam[e] if mcf.joint[e] else 0))
        flow = _best_flow(mcf, gnet, mcf.M * denom)
        flows.append(flow)
        value = sum(flow[e] * (denom * mcf.cost(k, e) + (lam[e] if mcf.joint[e] else 0)) for e in range(mcf.m) if not mcf.reward[e]) - mcf.M * denom * sum(flow[e] for e in range(mcf.m) if mcf.reward[e])
        total += Fraction(value, denom)
    total -= sum(f * mcf.net.arcs[e][2] for e, f in enumerate(fr) if mcf.joint[e])
    return float(total), flows


BIG_CAP = 10 ** 6
