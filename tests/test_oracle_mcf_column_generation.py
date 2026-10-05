"""Orakel-Regressionstest: Column Generation, Kanten-LP und ganzzahliges Programm gegen eine selbst gebaute dichte LP-Formulierung (scipy), CP-SAT und networkx.

Unabhängige Rechenwege: das Kanten-LP wird hier aus den Netzdaten neu aufgestellt (dichte Matrizen, eigene Kostenregel), das ganzzahlige Programm mit CP-SAT gelöst, die
Pfadzahlen mit networkx aufgezählt, die Preise des letzten Masters mit networkx-Dijkstra auf Optimalität geprüft."""

import random

import numpy as np
import pytest
from scipy.optimize import linprog

import mcg_cg as cg
import mcg_edge_lp as el
import mcg_model as md
import mcg_paths as pa
import mcg_scenario as sc

nx = pytest.importorskip("networkx")


def _cost(mcf, k, e):
    _, _, _, c, kind = mcf.net.arcs[e]
    return mcf.factors[k] * c if kind in (sc.K_LANE_IN, sc.K_LANE_OUT) else c


def _own_lp(mcf):
    K, m, n, arcs = mcf.K, mcf.m, mcf.net.n, mcf.net.arcs
    c = np.zeros(K * m)
    bounds = []
    for k in range(K):
        for e in range(m):
            c[k * m + e] = _cost(mcf, k, e) - (mcf.M if arcs[e][1] == mcf.net.t else 0)
            bounds.append((0, None if mcf.ub[k][e] >= 10 ** 6 else mcf.ub[k][e]))
    a_eq = []
    for k in range(K):
        for v in range(n):
            if v in (mcf.net.s, mcf.net.t):
                continue
            row = np.zeros(K * m)
            for e, (a, b, *_rest) in enumerate(arcs):
                row[k * m + e] += (b == v) - (a == v)
            a_eq.append(row)
    a_ub, b_ub = [], []
    for e in range(m):
        if mcf.joint[e]:
            row = np.zeros(K * m)
            row[[k * m + e for k in range(K)]] = 1
            a_ub.append(row)
            b_ub.append(arcs[e][2])
    res = linprog(c, A_ub=np.array(a_ub), b_ub=b_ub, A_eq=np.array(a_eq), b_eq=np.zeros(len(a_eq)), bounds=bounds, method="highs")
    assert res.status == 0
    return res.fun


def _nets():
    rng = random.Random(3)
    out = [md.gap_net(), md.order_net(), md.preis_net()]
    for _ in range(3):
        out.append(md.generate_mcf(rng.randint(2, 4), rng.randint(2, 4), rng.randint(3, 8), rng.choice(range(20, 101, 10)), rng.choice((0, 50, 100)), rng.choice(range(40, 161, 10)), rng.randint(0, 10 ** 6), rng.randint(2, 5)))
        out.append(md.generate_grid(rng.randint(3, 5), rng.randint(3, 4), rng.choice(range(40, 101, 10)), rng.randint(1, 4), rng.randint(1, 6), rng.randint(2, 5), rng.randint(0, 10 ** 6)))
        out.append(md.generate_pairs(rng.randint(3, 7), rng.choice((30, 45, 60, 80)), rng.randint(2, 4), rng.randint(0, 10 ** 6), rng.randint(1, 3), rng.randint(1, 3)))
    return out


def test_column_generation_and_edge_lp_equal_a_from_scratch_lp_with_valid_bounds_and_prices():
    for mcf in _nets():
        opt = _own_lp(mcf)
        assert abs(el.solve_lp(mcf).objective - opt) < 1e-6
        for kw in ({}, {"per_round": "eine"}, {"start": "nacheinander"}):
            r = cg.column_generation(mcf, **kw)
            assert r.optimal and abs(r.obj - opt) < 1e-6 and abs(r.obj - (r.cost - mcf.M * r.total_delivered)) < 1e-6
            assert all(rd.obj >= opt - 1e-6 and rd.lb <= opt + 1e-6 for rd in r.rounds)
            assert all(a.obj >= b.obj - 1e-7 for a, b in zip(r.rounds, r.rounds[1:]))
        last = cg.column_generation(mcf).rounds[-1]
        for k in range(mcf.K):
            G = nx.DiGraph()
            for e, (u, v, *_rest) in enumerate(mcf.net.arcs):
                if mcf.ub[k][e] > 0:
                    G.add_edge(u, v, weight=(0 if mcf.reward[e] else _cost(mcf, k, e)) + (last.lam[e] if mcf.joint[e] else 0.0) + last.mu[k, e])
            if mcf.net.s in G and mcf.net.t in G and nx.has_path(G, mcf.net.s, mcf.net.t):
                assert nx.dijkstra_path_length(G, mcf.net.s, mcf.net.t) >= mcf.M - 1e-7


def test_path_counts_equal_networkx_enumeration():
    for mcf in _nets():
        for k in range(mcf.K):
            G = nx.DiGraph()
            G.add_edges_from((u, v) for e, (u, v, *_rest) in enumerate(mcf.net.arcs) if mcf.ub[k][e] > 0)
            ref = sum(1 for _ in nx.all_simple_paths(G, mcf.net.s, mcf.net.t)) if mcf.net.s in G and mcf.net.t in G else 0
            count, exact = pa.count_paths(mcf, k)
            assert exact and count == ref == len(pa.enumerate_paths(mcf, k))


def test_integer_program_equals_cpsat_and_the_teaching_nets_by_hand():
    cp = pytest.importorskip("ortools.sat.python.cp_model")
    for mcf in (md.gap_net(), md.order_net(), md.preis_net()):
        K, m, arcs = mcf.K, mcf.m, mcf.net.arcs
        mod = cp.CpModel()
        x = [[mod.NewIntVar(0, min(mcf.ub[k][e], arcs[e][2] if mcf.joint[e] else 10 ** 4, 10 ** 4), "") for e in range(m)] for k in range(K)]
        for k in range(K):
            for v in range(mcf.net.n):
                if v not in (mcf.net.s, mcf.net.t):
                    mod.Add(sum(x[k][e] for e in range(m) if arcs[e][1] == v) == sum(x[k][e] for e in range(m) if arcs[e][0] == v))
        for e in range(m):
            if mcf.joint[e]:
                mod.Add(sum(x[k][e] for k in range(K)) <= arcs[e][2])
        mod.Minimize(sum(x[k][e] * (_cost(mcf, k, e) - (mcf.M if mcf.reward[e] else 0)) for k in range(K) for e in range(m)))
        solver = cp.CpSolver()
        solver.parameters.num_workers = 1
        assert solver.Solve(mod) == cp.OPTIMAL
        assert abs(el.solve_ilp(mcf).objective - round(solver.ObjectiveValue())) < 1e-6
    assert abs(_own_lp(md.gap_net()) - -1476) < 1e-6          # 1,5 Einheiten geliefert (1500), Kosten 24
    assert abs(_own_lp(md.preis_net()) - (5 - 2000)) < 1e-6              # Kosten 5, zwei Einheiten
