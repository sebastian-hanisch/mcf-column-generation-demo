"""Kern: Pfad-LP und Column Generation gegen unabhängige Gegenproben (Kanten-LP, Pfad-LP mit allen aufgezählten Pfaden, Dualitätszertifikat über alle Pfade, komplementärer Schlupf), Zulässigkeit,
Schranken, Optionen, Negativkontrolle, Pfadzählung und Pfadzerlegung, Lehrnetze."""

import itertools
import random

import networkx as nx
import numpy as np
import pytest

import mcg_cg as cg
import mcg_constants as C
import mcg_edge_lp as el
import mcg_model as md
import mcg_paths as pa
import mcg_scenario as sc
import mcg_ssp as ssp
from mcg_scenario import SplitMix64

TOL = 1e-6


def _dist(count):
    """Zufällige Distributionsnetze mit 2 bis 4 Gütern in verschiedenen Größen."""
    rng = random.Random(21)
    sizes = ((2, 2, 3), (3, 3, 6), (3, 3, 8), (4, 3, 5), (2, 4, 9))
    for i in range(count):
        p, d, s = sizes[i % len(sizes)]
        yield md.generate_mcf(p, d, s, rng.choice((40, 60, 80, 100)), rng.choice((0, 50, 100)), rng.choice((60, 90, 130)), 4000 + i, 2 + i % 3)


def _grids(count):
    rng = random.Random(22)
    for i in range(count):
        yield md.generate_grid(rng.choice((3, 4, 5)), rng.choice((3, 4)), rng.choice((50, 70, 100)), rng.choice((1, 2, 3)), rng.choice((2, 4)), 2 + i % 3, 5000 + i)


def _check_feasible(mcf, x, tol=TOL):
    """Erhaltung je Gut, gemeinsame Kapazität, gutspezifische Obergrenzen, Nichtnegativität."""
    net = mcf.net
    assert (x >= -tol).all()
    for k in range(mcf.K):
        bal = np.zeros(net.n)
        for e, (u, v, _, _, _) in enumerate(net.arcs):
            bal[u] -= x[k, e]
            bal[v] += x[k, e]
            assert x[k, e] <= min(mcf.ub[k][e], 10 ** 6) + tol
        assert all(abs(bal[v]) <= tol for v in range(net.n) if v not in (net.s, net.t))
    for e, (_, _, cap, _, _) in enumerate(net.arcs):
        if mcf.joint[e]:
            assert x[:, e].sum() <= cap + tol


def test_splitmix64_reference_vector():
    rng = SplitMix64(0)
    assert [rng.next() for _ in range(2)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4]


def test_the_ssp_copy_reproduces_the_predecessor_numbers():
    """Wache: SSP 53 907 durchsuchte Kanten (Mittel 539,07) über die 100 festen Netze der Vorgänger-Demos, Kosten = networkx."""
    scans = 0
    for seed in C.DIST_SEEDS:
        net = sc.generate(3, 3, 8, 60, 50, 90, seed)
        r = ssp.ssp(net, keep_trace=False)
        scans += r.scanned_total
        if seed < C.DIST_SEEDS[0] + 20:
            g = nx.DiGraph()
            for u, v, c, k, _ in net.arcs:
                g.add_edge(u, v, capacity=c, weight=k)
            flow = nx.max_flow_min_cost(g, net.s, net.t)
            assert (r.value, r.total) == (sum(flow[net.s].values()), nx.cost_of_flow(g, flow))
    assert scans == 53907


def test_the_edge_lp_copy_reproduces_the_predecessor_numbers():
    """Wache: das Kanten-LP des Vorgängers (Seed 155, drei Güter): 67 von 76 Einheiten für 1548 mit 114 Variablen; Frachtnetz mit Bruch: 1,5 Einheiten für 24, ganzzahlig 1 für 15."""
    mcf = md.generate_mcf(3, 3, 8, 60, 50, 90, 155, 3)
    lp = el.solve_lp(mcf)
    assert (lp.total_delivered, mcf.total_demand(), lp.cost, lp.n_vars) == (67.0, 76, 1548.0, 114)
    gap = md.gap_net()
    lp, ilp = el.solve_lp(gap), el.solve_ilp(gap)
    assert (lp.total_delivered, lp.cost, ilp.total_delivered, ilp.cost) == (1.5, 24.0, 1.0, 15.0)


# --- Netze -----------------------------------------------------------------------------------------------------------------------------------

def test_the_grid_is_connected_symmetric_and_reproducible():
    mcf = md.generate_grid(5, 4, 40, 3, 4, 3, 11)
    assert mcf == md.generate_grid(5, 4, 40, 3, 4, 3, 11) and mcf.layout == "grid" and mcf.K == 3
    net = mcf.net
    inner = [(u, v, c, k) for u, v, c, k, kind in net.arcs if kind == sc.K_OTHER]
    assert sorted((u, v, c, k) for u, v, c, k in inner) == sorted((v, u, c, k) for u, v, c, k in inner)      # jede Kante in beide Richtungen mit derselben Kapazität und denselben Kosten
    g = nx.Graph()
    g.add_nodes_from(range(2, net.n))
    g.add_edges_from((u, v) for u, v, _, _ in inner)
    assert nx.is_connected(g) and len(inner) // 2 >= net.n - 3                                              # mindestens ein Spannbaum (n - 2 Knoten, n - 3 Kanten)
    for k in range(mcf.K):
        out = pa.adjacency(mcf, k)
        assert len(out[net.s]) == 1 and pa.count_paths(mcf, k)[0] >= 1                                       # jedes Gut hat einen Start und mindestens einen Weg zum Ziel


def test_density_only_changes_which_edges_exist():
    """Die Zufallszahlen werden je Gitterkante in fester Reihenfolge gezogen: eine höhere Dichte fügt Kanten hinzu, ändert aber keine bestehende."""
    def edge_set(density):
        return {(u, v, c, k) for u, v, c, k, kind in md.generate_grid(5, 4, density, 3, 4, 3, 11).net.arcs if kind == sc.K_OTHER}
    assert edge_set(40) <= edge_set(70) <= edge_set(100)
    assert len(edge_set(100)) == 2 * (4 * 4 + 5 * 3)                                                        # volles Gitter 5 x 4: 31 Kanten, beide Richtungen


def test_the_price_net_is_a_hand_checked_example():
    """Zwei Güter von A nach D: Direktstrecke (Kosten 1, Kapazität 1) und Umweg über B (2 + 2, Kapazität 2). Optimum: eine Einheit direkt (1), eine über den Umweg (4): Kosten 5, Lieferung 2."""
    mcf = md.preis_net()
    lp = el.solve_lp(mcf)
    assert (lp.total_delivered, lp.cost) == (2.0, 5.0) and not lp.fractional
    assert [pa.count_paths(mcf, k) for k in range(2)] == [(2, True), (2, True)]
    r = cg.column_generation(mcf)
    assert r.optimal and r.n_rounds == 2
    first, last = r.rounds[1], r.rounds[-1]
    direct = 0                                                                                               # Kante A -> D
    assert first.lam[direct] > 900 and abs(sum(first.delivered) - 1.0) < TOL                                  # Runde 1: die Direktstrecke begrenzt die Lieferung, Preis ~ M
    assert abs(last.lam[direct] - 3.0) < TOL and abs(sum(last.delivered) - 2.0) < TOL                         # danach: der Preis ist genau der Mehrpreis des Umwegs (4 - 1)


def test_path_counts_on_the_teaching_nets():
    gap = md.gap_net()
    assert sorted(n for n, _ in (pa.count_paths(gap, k) for k in range(2))) == [1, 3]


def test_path_counting_agrees_with_enumeration_and_every_path_is_simple():
    for mcf in list(_dist(6)) + list(_grids(6)):
        for k in range(mcf.K):
            found = pa.enumerate_paths(mcf, k)
            assert pa.count_paths(mcf, k) == (len(found), True) and len(set(found)) == len(found)
            for edges in found:
                nodes = pa.path_nodes(mcf, edges)
                assert nodes[0] == mcf.net.s and nodes[-1] == mcf.net.t and len(set(nodes)) == len(nodes)
                assert all(mcf.ub[k][e] > 0 for e in edges)


def test_the_counting_budget_gives_up_honestly():
    mcf = md.generate_grid(8, 6, 100, 2, 4, 2, 3)
    n, exact = pa.count_paths(mcf, 0, limit=500, budget=10 ** 6)
    assert (n, exact) == (500, False)
    n, exact = pa.count_paths(mcf, 0, limit=10 ** 9, budget=2000)
    assert not exact


def test_flow_decomposition_reproduces_the_flow():
    for mcf in list(_dist(5)) + list(_grids(5)):
        lp = el.solve_lp(mcf)
        for k in range(mcf.K):
            parts = pa.decompose_flow(mcf, lp.x[k])
            back = np.zeros(mcf.m)
            for edges, amount in parts:
                assert amount > 0 and pa.path_nodes(mcf, edges)[0] == mcf.net.s
                for e in edges:
                    back[e] += amount
            assert np.allclose(back, lp.x[k], atol=TOL)


# --- Column Generation gegen das Kanten-LP ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("make", [lambda: _dist(25), lambda: _grids(25)])
def test_column_generation_reaches_the_edge_lp_optimum(make):
    for mcf in make():
        r = cg.column_generation(mcf)
        lp = el.solve_lp(mcf)
        assert r.optimal and abs(r.obj - lp.objective) < TOL and abs(r.total_delivered - lp.total_delivered) < TOL
        _check_feasible(mcf, r.x)


def test_column_generation_on_the_teaching_nets_and_with_one_good():
    for mcf in (md.gap_net(), md.order_net(), md.preis_net()):
        r = cg.column_generation(mcf)
        assert r.optimal and abs(r.obj - el.solve_lp(mcf).objective) < TOL
    g = md.gap_net()
    r = cg.column_generation(g)
    assert abs(r.total_delivered - 1.5) < TOL and any(abs(a - round(a)) > TOL for a in r.amounts)           # gebrochene Pfadmengen: das LP ist gebrochen
    for mcf in (md.generate_mcf(3, 3, 8, 60, 50, 90, 155, 1), md.generate_grid(4, 3, 100, 2, 3, 1, 5)):
        assert abs(cg.column_generation(mcf).obj - el.solve_lp(mcf).objective) < TOL


def test_the_path_lp_with_all_paths_agrees_with_both():
    """Pfad-LP mit allen aufgezählten Pfaden = Kanten-LP = Column Generation (Kleinstnetze)."""
    nets = [md.gap_net(), md.order_net(), md.preis_net()] + [md.generate_grid(3, 3, 100, 2, 3, 3, s) for s in range(1, 6)] + [md.generate_grid(4, 3, 70, 2, 4, 3, s) for s in range(1, 4)] + list(_dist(4))
    for mcf in nets:
        obj_all, n_all = cg.solve_all_paths(mcf)
        assert abs(obj_all - el.solve_lp(mcf).objective) < TOL and abs(obj_all - cg.column_generation(mcf).obj) < TOL
        assert n_all == sum(len(pa.enumerate_paths(mcf, k)) for k in range(mcf.K))


def test_at_the_end_no_path_at_all_has_negative_reduced_cost():
    """Dualitätszertifikat unabhängig: mit den Preisen des letzten Masters hat jeder der aufgezählten Pfade (nicht nur die von Dijkstra gefundenen) reduzierte Kosten >= 0."""
    for mcf in [md.gap_net(), md.preis_net()] + [md.generate_grid(4, 3, 100, 2, 4, 3, s) for s in range(1, 6)] + list(_dist(4)):
        r = cg.column_generation(mcf)
        last = r.rounds[-1]
        for k in range(mcf.K):
            for edges in pa.enumerate_paths(mcf, k):
                rc = pa.path_cost(mcf, k, edges) - mcf.M + sum((last.lam[e] if mcf.joint[e] else 0.0) + last.mu[k, e] for e in edges)
                assert rc >= -1e-7


def test_prices_are_non_negative_and_complementary():
    """Ein positiver Preis nur auf ausgelasteten Kanten (gemeinsame Kapazität bzw. Gut-Obergrenze)."""
    for mcf in [md.gap_net()] + list(_grids(8)) + list(_dist(5)):
        r = cg.column_generation(mcf)
        last = r.rounds[-1]
        assert (last.lam >= 0).all() and (last.mu >= 0).all()
        for e in range(mcf.m):
            if last.lam[e] > TOL:
                assert mcf.joint[e] and abs(last.x[:, e].sum() - mcf.net.arcs[e][2]) < 1e-6
            for k in range(mcf.K):
                if last.mu[k, e] > TOL:
                    assert abs(last.x[k, e] - mcf.ub[k][e]) < 1e-6


def test_the_columns_are_valid_and_the_master_flow_is_the_sum_of_its_paths():
    for mcf in list(_grids(6)) + list(_dist(4)):
        r = cg.column_generation(mcf)
        assert len({(c.k, c.edges) for c in r.columns}) == len(r.columns)                                    # keine Spalte doppelt
        for c in r.columns:
            nodes = pa.path_nodes(mcf, c.edges)
            assert nodes[0] == mcf.net.s and nodes[-1] == mcf.net.t and len(set(nodes)) == len(nodes) and c.cost == pa.path_cost(mcf, c.k, c.edges)
        back = np.zeros((mcf.K, mcf.m))
        for c, a in zip(r.columns, r.amounts):
            for e in c.edges:
                back[c.k, e] += a
        assert np.allclose(back, r.x, atol=TOL)


def test_every_new_column_has_negative_reduced_cost_when_it_is_found():
    for mcf in list(_grids(5)) + list(_dist(4)):
        r = cg.column_generation(mcf)
        for rd in r.rounds:
            for j in rd.new:
                c = r.columns[j]
                rc = c.cost - mcf.M + sum((rd.lam[e] if mcf.joint[e] else 0.0) + rd.mu[c.k, e] for e in c.edges)
                assert rc < -1e-9 and j >= rd.n_columns


def test_the_bounds_enclose_the_optimum_and_converge():
    """Master-Wert nie steigend (obere Schranke), beste untere Schranke nie fallend; Optimum dazwischen; am Ende gleich."""
    for mcf in list(_grids(8)) + list(_dist(6)):
        lp = el.solve_lp(mcf)
        r = cg.column_generation(mcf)
        objs = [rd.obj for rd in r.rounds]
        lbs = [rd.lb for rd in r.rounds]
        assert all(b <= a + 1e-7 for a, b in zip(objs, objs[1:])) and all(b >= a - 1e-7 for a, b in zip(lbs, lbs[1:]))
        assert all(lb <= lp.objective + 1e-6 <= ub + 2e-6 for lb, ub in zip(lbs, objs))
        assert abs(lbs[-1] - objs[-1]) < 1e-6 and objs[-1] == r.obj


def test_the_lower_bound_holds_for_arbitrary_prices():
    """Farley-Schranke für beliebige nichtnegative Preise (nicht nur die des Masters) liegt unter dem Optimum."""
    rng = random.Random(5)
    for mcf in list(_grids(6)) + list(_dist(4)):
        lp = el.solve_lp(mcf)
        master = cg.Master(mcf)
        adj = [pa.adjacency(mcf, k) for k in range(mcf.K)]
        for _ in range(5):
            lam = np.array([rng.choice((0.0, 0.5, 3.0, 20.0)) if mcf.joint[e] else 0.0 for e in range(mcf.m)])
            mu = np.array([[rng.choice((0.0, 1.0, 10.0)) for _ in range(mcf.m)] for _ in range(mcf.K)])
            dists = [cg.price(mcf, adj[k], k, lam, mu)[0] for k in range(mcf.K)]
            assert cg._lower_bound(master, mcf, lam, mu, dists) <= lp.objective + 1e-6


# --- Optionen und Negativkontrolle -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kw", [dict(per_round="eine"), dict(start="nacheinander"), dict(alpha=0.5), dict(alpha=0.8), dict(start="nacheinander", per_round="eine", alpha=0.5)])
def test_every_option_still_ends_in_the_optimum(kw):
    for mcf in list(_grids(6)) + list(_dist(5)):
        r = cg.column_generation(mcf, **kw)
        assert r.optimal and abs(r.obj - el.solve_lp(mcf).objective) < TOL


def test_one_column_per_round_takes_more_rounds_and_adds_one_each():
    mcf = md.generate_mcf(3, 3, 8, 60, 50, 90, 155, 3)
    all_r, one_r = cg.column_generation(mcf), cg.column_generation(mcf, per_round="eine")
    assert one_r.n_rounds > all_r.n_rounds and all(len(rd.new) <= 1 for rd in one_r.rounds) and any(len(rd.new) > 1 for rd in all_r.rounds)
    assert one_r.n_columns == one_r.n_rounds


def test_a_warm_start_begins_with_columns_and_an_empty_start_with_none():
    mcf = md.generate_mcf(3, 3, 8, 60, 50, 90, 155, 3)
    assert cg.column_generation(mcf).rounds[0].n_columns == 0 and cg.column_generation(mcf).rounds[0].obj == 0.0
    warm = cg.column_generation(mcf, start="nacheinander")
    seq = el.solve_sequential(mcf)
    assert warm.rounds[0].n_columns > 0 and abs(warm.rounds[0].obj - seq.objective) < TOL
    assert warm.n_rounds < cg.column_generation(mcf).n_rounds


def test_the_first_pricing_without_prices_is_each_good_alone():
    """Runde 0 ohne Spalten hat keine Preise; das Pricing liefert den billigsten Weg jedes Guts - sein Fluss aus dem Vorgänger ('jedes Gut allein') beginnt mit denselben Wegen."""
    mcf = md.generate_grid(5, 4, 70, 2, 4, 3, 9)
    r = cg.column_generation(mcf)
    adj = [pa.adjacency(mcf, k) for k in range(mcf.K)]
    zero = np.zeros(mcf.m), np.zeros((mcf.K, mcf.m))
    firsts = [cg.price(mcf, adj[k], k, *zero)[1] for k in range(mcf.K)]
    assert [(c.k, c.edges) for c in [r.columns[j] for j in r.rounds[0].new]] == [(k, e) for k, e in enumerate(firsts)]


def test_a_gap_tolerance_stops_early_with_the_promised_gap():
    for mcf in list(_dist(6)) + list(_grids(4)):
        full = cg.column_generation(mcf)
        r = cg.column_generation(mcf, gap_tol=0.05)
        last = r.rounds[-1]
        assert r.n_rounds <= full.n_rounds and (r.gap_stop or r.optimal)
        if r.gap_stop:
            assert last.obj - last.lb <= 0.05 * abs(last.obj) + 1e-9 and last.obj >= full.obj - 1e-9


def test_smoothing_changes_the_path_but_never_the_result():
    mcf = md.generate_mcf(3, 3, 8, 60, 50, 90, 155, 3)
    base, smooth = cg.column_generation(mcf), cg.column_generation(mcf, alpha=0.8)
    assert abs(base.obj - smooth.obj) < TOL and smooth.optimal


def test_the_negative_control_stops_with_a_wrong_value():
    """Ohne die Preise der Gut-Obergrenzen (mu) im Pricing: das Pricing schlägt nur schon bekannte Pfade vor, die Column Generation bleibt stecken und liefert weniger als das LP."""
    mcf = md.generate_mcf(3, 3, 8, 60, 50, 90, 155, 3)
    r = cg.column_generation(mcf, ignore_mu=True)
    assert r.stuck and not r.optimal and r.obj > el.solve_lp(mcf).objective + 1.0 and r.total_delivered < el.solve_lp(mcf).total_delivered - 1
    wrong = 0
    for mcf in _dist(10):
        r = cg.column_generation(mcf, ignore_mu=True)
        wrong += abs(r.obj - el.solve_lp(mcf).objective) > TOL
    assert wrong >= 8


def test_a_net_where_nothing_arrives_ends_at_once():
    """Ein Netz ohne Weg: das Pricing findet nichts, der Master bleibt leer, Wert 0."""
    mcf = md.generate_mcf(2, 6, 3, 20, 50, 90, 8, 3)
    r = cg.column_generation(mcf)
    lp = el.solve_lp(mcf)
    assert r.optimal and abs(r.obj - lp.objective) < TOL and r.total_delivered == lp.total_delivered


def test_the_master_lp_grows_by_columns_not_by_edge_variables():
    mcf = md.generate_grid(5, 4, 100, 2, 4, 4, 3)
    r = cg.column_generation(mcf)
    lp = el.solve_lp(mcf)
    assert r.n_columns < lp.n_vars / 5 and lp.n_vars == mcf.K * mcf.m
    assert [rd.n_columns for rd in r.rounds] == sorted(rd.n_columns for rd in r.rounds)
