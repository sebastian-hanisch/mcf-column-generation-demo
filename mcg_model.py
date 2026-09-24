"""Mehrgüterfluss-Modell: K Güter (Frische, Trocken, Kühl, ...) im Distributionsnetz, die sich die Kanten teilen.

Aufbau wie in den Vorgänger-Demos (Quelle S, Werke, Verteilzentren als Eingang -> Ausgang gespalten, Filialen, Senke T). Je Gut k gibt es Flussvariablen x[k][e] auf allen Kanten.
- **Gemeinsame Kapazität** (joint): Werkskapazität, Lanes und Verteilzentrum-Durchsatz gelten für die *Summe* der Güter: sum_k x[k][e] <= u[e].
- **Gutspezifische Obergrenzen** ub[k][e]: ein Werk stellt nicht jedes Gut her (ub = 0 auf seiner Angebotskante), die Nachfragekante zur Senke trägt höchstens die Filialnachfrage des Guts.
- **Kosten** je Gut: auf den Lanes mal einem Kostenfaktor (Kühl teurer als Trocken), sonst wie im Einzelgutnetz.
- **Belohnung** M je gelieferter Einheit (Kanten in die Senke, Kosten -M): so liefert das LP zuerst so viel wie möglich und darunter so billig wie möglich (lexikographisch); Unterversorgung ist kein Fehler, sondern sichtbar.
Alles ganzzahlig.
"""

from dataclasses import dataclass

import mcg_scenario as sc
from mcg_scenario import SplitMix64

BIG = 10 ** 6                       # "unbeschränkt" für Obergrenzen
GOODS = ("Frische", "Trocken", "Kühl", "Getränke", "Tiefkühl")
FACTORS = (2, 1, 3, 1, 4)           # Kostenfaktor auf den Lanes je Gut
GOOD_COLORS = ("#2ca02c", "#1f77b4", "#9467bd", "#ff7f0e", "#17becf")
M_REWARD = 1000                     # größer als jeder Weg (höchste Wegkosten < 200)


@dataclass(frozen=True)
class Mcf:
    net: sc.Net
    names: tuple         # Gutnamen
    factors: tuple       # Kostenfaktor je Gut auf Lanes
    ub: tuple            # ub[k][e]: Obergrenze je Gut und Kante (BIG = unbeschränkt)
    joint: tuple         # joint[e]: gemeinsame Kapazität (Summe über die Güter)
    reward: tuple        # reward[e]: Kante in die Senke (Belohnung M je Einheit)
    M: int
    layout: str = "layered"   # "layered" (Distributionsnetz), "pairs" (Frachtnetz) oder "grid" (Streckennetz: S/T-Kanten werden nicht gezeichnet)

    @property
    def K(self):
        return len(self.names)

    @property
    def m(self):
        return self.net.m

    def cost(self, k, e):
        """Kosten je Einheit von Gut k auf Kante e (ohne Belohnung)."""
        _, _, _, c, kind = self.net.arcs[e]
        return self.factors[k] * c if kind in (sc.K_LANE_IN, sc.K_LANE_OUT) else c

    def demand(self, k):
        """Gesamtnachfrage von Gut k (Summe der Obergrenzen der Senkenkanten)."""
        return sum(self.ub[k][e] for e in range(self.m) if self.reward[e])

    def total_demand(self):
        return sum(self.demand(k) for k in range(self.K))


def _split(total, weights):
    """Ganzzahlige Aufteilung von `total` im Verhältnis der Gewichte; der Rest geht an das schwerste Gewicht."""
    w = sum(weights)
    parts = [total * x // w for x in weights]
    parts[max(range(len(weights)), key=lambda i: weights[i])] += total - sum(parts)
    return parts


def generate_mcf(n_plants, n_dcs, n_stores, density, spread, load, seed, K):
    """Zufälliges Distributionsnetz mit K Gütern. Das Einzelgutnetz (`sc.generate`) liefert Kapazitäten und Gesamtnachfrage; darauf werden Güter verteilt:
    jedes Werk stellt ein Gut mit 70 % Wahrscheinlichkeit her (jedes Gut hat mindestens ein Werk), die Nachfrage einer Filiale wird im Verhältnis zufälliger Gewichte auf die Güter verteilt."""
    net = sc.generate(n_plants, n_dcs, n_stores, density, spread, load, seed)
    rng = SplitMix64(seed ^ 0x6D63665F)
    supply = [i for i, a in enumerate(net.arcs) if a[4] == sc.K_SUPPLY]
    demand_arcs = [i for i, a in enumerate(net.arcs) if a[4] == sc.K_DEMAND]
    ub = [[BIG] * net.m for _ in range(K)]
    for k in range(K):
        allowed = [rng.below(100) < 70 for _ in supply]
        if not any(allowed):
            allowed[rng.below(len(supply))] = True
        for j, e in enumerate(supply):
            ub[k][e] = net.arcs[e][2] if allowed[j] else 0
    for e in demand_arcs:
        parts = _split(net.arcs[e][2], [1 + rng.below(10) for _ in range(K)])
        for k in range(K):
            ub[k][e] = parts[k]
    joint = tuple(a[4] != sc.K_DEMAND for a in net.arcs)
    reward = tuple(a[1] == net.t for a in net.arcs)
    return Mcf(net, GOODS[:K], FACTORS[:K], tuple(tuple(r) for r in ub), joint, reward, M_REWARD)


def generate_pairs(n_nodes, density, K, seed, max_cap=3, max_demand=3):
    """Zweites Fahrzeug: ein Frachtnetz mit K Quelle-Ziel-Paaren. Ein zufälliger gerichteter Graph (Kanten in beide Richtungen möglich, Kapazität 1..max_cap, Kosten 1..9), Gut k fährt von seinem
    Startknoten zu seinem Zielknoten (Menge 1..max_demand). Anders als im geschichteten Distributionsnetz laufen die Güter hier gegeneinander - erst so wird das LP gebrochen.
    Über S und T (Angebots- bzw. Nachfragekante je Gut) passt es in dasselbe Modell."""
    rng = SplitMix64(seed ^ 0x70616972)
    names = ["Quelle S", "Senke T"] + [f"K{i + 1}" for i in range(n_nodes)]
    labels = ["S", "T"] + [f"{i + 1}" for i in range(n_nodes)]
    from math import cos, sin, pi
    pos = [(50, 96), (50, 4)] + [(50 + 34 * cos(2 * pi * i / n_nodes + 0.3), 50 + 34 * sin(2 * pi * i / n_nodes + 0.3)) for i in range(n_nodes)]
    arcs = []
    for u in range(n_nodes):
        for v in range(n_nodes):
            if u != v and rng.below(100) < density:
                arcs.append((2 + u, 2 + v, 1 + rng.below(max_cap), 1 + rng.below(9), sc.K_OTHER))
    pairs = []
    for k in range(K):
        a = rng.below(n_nodes)
        b = (a + 1 + rng.below(n_nodes - 1)) % n_nodes
        pairs.append((a, b, 1 + rng.below(max_demand)))
    internal = len(arcs)
    for k, (a, b, dem) in enumerate(pairs):
        arcs.append((0, 2 + a, dem, 0, sc.K_SUPPLY))
    for k, (a, b, dem) in enumerate(pairs):
        arcs.append((2 + b, 1, dem, 0, sc.K_DEMAND))
    net = sc.Net(tuple(names), tuple(labels), tuple(pos), tuple(arcs), 0, 1, False)
    ub = [[BIG] * len(arcs) for _ in range(K)]
    for k, (a, b, dem) in enumerate(pairs):
        for j in range(K):
            ub[k][internal + j] = dem if j == k else 0
            ub[k][internal + K + j] = dem if j == k else 0
    joint = tuple(i < internal for i in range(len(arcs)))
    reward = tuple(a[1] == 1 for a in arcs)
    return Mcf(net, GOODS[:K], (1,) * K, tuple(tuple(r) for r in ub), joint, reward, M_REWARD, "pairs")


def gap_net():
    """Frachtnetz mit Bruch: fünf Knoten, zwei Güter, alle Kapazitäten und Mengen 1. Das LP liefert 1,5 Einheiten (jedes Gut halb über zwei Wege), ganzzahlig gehen nur 1 Einheit."""
    return generate_pairs(5, 55, 2, 1341, 1, 1)


def order_net():
    """Frachtnetz, in dem die Reihenfolge entscheidet: sechs Knoten, drei Güter (Kapazität bis 2, Menge bis 2). Das LP liefert 4 von 5 Einheiten; von den sechs Reihenfolgen erreichen drei das
    Optimum, drei liefern nur 3 Einheiten - das Gut, das zuerst fährt, verbaut den anderen den Weg."""
    return generate_pairs(6, 45, 3, 2, 2, 2)


def _terminals(net_n, pairs, K, internal_arcs, pos, names, labels, layout):
    """Gemeinsamer Aufbau der Frachtnetze: Angebotskante S -> Start und Nachfragekante Ziel -> T je Gut (nur für das eigene Gut offen), alle inneren Kanten gemeinsam."""
    arcs = list(internal_arcs)
    internal = len(arcs)
    for a, b, dem in pairs:
        arcs.append((0, 2 + a, dem, 0, sc.K_SUPPLY))
    for a, b, dem in pairs:
        arcs.append((2 + b, 1, dem, 0, sc.K_DEMAND))
    net = sc.Net(tuple(names), tuple(labels), tuple(pos), tuple(arcs), 0, 1, False)
    ub = [[BIG] * len(arcs) for _ in range(K)]
    for k, (a, b, dem) in enumerate(pairs):
        for j in range(K):
            ub[k][internal + j] = dem if j == k else 0
            ub[k][internal + K + j] = dem if j == k else 0
    joint = tuple(i < internal for i in range(len(arcs)))
    reward = tuple(a[1] == 1 for a in arcs)
    return Mcf(net, GOODS[:K], (1,) * K, tuple(tuple(r) for r in ub), joint, reward, M_REWARD, layout)


def generate_grid(width, height, density, cap_max, dem_max, K, seed):
    """Streckennetz: ein Gitter width x height. Ein zufälliger Spannbaum hält das Netz zusammenhängend, jede weitere Gitterkante gibt es mit `density` Prozent. Jede Kante trägt in beide Richtungen
    dieselbe Kapazität 1..cap_max und dieselben Kosten 1..9 (Länge), gemeinsam für alle Güter. Gut k fährt von seinem Start zu seinem Ziel (verschiedene Knoten, Menge 1..dem_max).
    Die Zufallszahlen werden je Gitterkante in fester Reihenfolge gezogen, egal ob sie existiert - so ändert `density` nur, welche Kanten es gibt."""
    rng = SplitMix64(seed ^ 0x67726964)
    n = width * height
    node = lambda i, j: 2 + j * width + i
    edges = [(node(i, j), node(i + 1, j)) for j in range(height) for i in range(width - 1)] + [(node(i, j), node(i, j + 1)) for j in range(height - 1) for i in range(width)]
    draws = [(rng.below(100), 1 + rng.below(cap_max), 1 + rng.below(9)) for _ in edges]
    tree = SplitMix64(seed ^ 0x74726565)
    order = list(range(len(edges)))
    for i in range(len(order) - 1, 0, -1):                      # Fisher-Yates
        j = tree.below(i + 1)
        order[i], order[j] = order[j], order[i]
    parent = list(range(n + 2))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    keep = set()
    for e in order:
        a, b = find(edges[e][0]), find(edges[e][1])
        if a != b:
            parent[a] = b
            keep.add(e)
    arcs = []
    for e, (u, v) in enumerate(edges):
        r, cap, cost = draws[e]
        if e in keep or r < density:
            arcs.append((u, v, cap, cost, sc.K_OTHER))
            arcs.append((v, u, cap, cost, sc.K_OTHER))
    pairs = []
    for _ in range(K):
        a = rng.below(n)
        b = (a + 1 + rng.below(n - 1)) % n
        pairs.append((a, b, 1 + rng.below(dem_max)))
    names = ["Quelle S", "Senke T"] + [f"Knoten ({i + 1}, {j + 1})" for j in range(height) for i in range(width)]
    labels = ["S", "T"] + [""] * n
    xs = [8 + 84 * i // max(1, width - 1) for i in range(width)]
    ys = [88 - 72 * j // max(1, height - 1) for j in range(height)]
    pos = [(50, 100), (50, 0)] + [(xs[i], ys[j]) for j in range(height) for i in range(width)]
    return _terminals(n, pairs, K, arcs, pos, names, labels, "grid")


def preis_net():
    """Lehrnetz für die Preis-Wende: zwei Güter von A nach D. Die Direktstrecke (Kosten 1) trägt nur eine Einheit, der Umweg über B (Kosten 2 + 2) zwei. In Runde 1 wollen beide Güter direkt fahren;
    mit dem Preis der Direktstrecke lohnt sich der Umweg, und das LP-Optimum ist eine Einheit direkt (1) und eine über den Umweg (4): Kosten 5."""
    names = ["Quelle S", "Senke T", "A", "B", "D"]
    labels = ["S", "T", "A", "B", "D"]
    pos = [(50, 96), (50, 4), (14, 50), (50, 76), (86, 50)]
    arcs = [(2, 4, 1, 1, sc.K_OTHER), (2, 3, 2, 2, sc.K_OTHER), (3, 4, 2, 2, sc.K_OTHER)]
    return _terminals(3, [(0, 2, 1), (0, 2, 1)], 2, arcs, pos, names, labels, "pairs")

