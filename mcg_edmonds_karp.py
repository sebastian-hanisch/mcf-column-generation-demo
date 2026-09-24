"""Maximaler Fluss durch Verbesserungswege im Restgraphen (Ford-Fulkerson; mit Breitensuche = Edmonds-Karp).

Jede Kante i des Netzes ist als Paar im Restgraphen gespeichert: Kante 2i ist die Vorwärtskante (Restkapazität = Kapazität -
Fluss), Kante 2i+1 die Rückkante (Restkapazität = Fluss). Ein Verbesserungsweg ist ein Weg von S nach T über Kanten mit
Restkapazität > 0; er wird um seinen Engpass (kleinste Restkapazität) aufgefüllt. Wenn die Suche scheitert, ist die Menge der
von S aus erreichbaren Knoten der Beweis: alle Kanten aus ihr heraus sind voll, ihre Kapazität ist der Flusswert (Min-Cut).

Aufwand wird in gescannten Kanten gezählt (jede in einer Adjazenzliste angesehene Restkante), nie in Sekunden.
Drei Wegesuchen: 'bfs' (kürzester Weg = Edmonds-Karp), 'dfs' (erster gefundener Weg in fester Kantenreihenfolge =
Ford-Fulkerson) und 'widest' (Weg mit dem größten Engpass, Edmonds-Karp 1972, zweite Regel).
"""

import heapq
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Round:
    path: tuple          # Restkanten-Indizes von S nach T (gerade = Vorwärts-, ungerade = Rückkante)
    nodes: tuple         # Knotenfolge von S nach T
    bottleneck: int
    length: int          # Zahl der Kanten des Weges
    flow_after: int
    scanned: int         # in dieser Suche angesehene Restkanten
    uses_back_arc: bool


@dataclass(frozen=True)
class Result:
    rounds: tuple
    flows: tuple             # flows[k] = Fluss je Kante des Netzes nach k Runden (flows[0] = alles 0)
    value: int
    reach: tuple             # bool je Knoten: von S im Schluss-Restgraphen erreichbar
    co_reach: tuple          # bool je Knoten: T im Schluss-Restgraphen erreichbar
    cut_arcs: tuple          # Indizes der Netzkanten von der erreichbaren Menge hinaus (alle voll)
    cut_capacity: int
    final_scanned: int       # Aufwand der letzten, gescheiterten Suche
    scanned_total: int
    unique_cut: bool         # kleinster und größter minimaler Schnitt fallen zusammen


def _adjacency(net):
    """Restkanten-Adjazenz: adj[u] = Indizes der von u ausgehenden Restkanten (Vorwärts- und Rückkanten) in Erzeugungsreihenfolge."""
    adj = [[] for _ in range(net.n)]
    head = []
    for i, (u, v, _, _, _) in enumerate(net.arcs):
        adj[u].append(2 * i)
        adj[v].append(2 * i + 1)
        head += [v, u]
    return adj, head


def _search_bfs(adj, head, res, s, t, use_back):
    parent = {s: -1}
    queue = deque([s])
    scanned = 0
    while queue:
        u = queue.popleft()
        for e in adj[u]:
            scanned += 1
            if res[e] > 0 and (use_back or e % 2 == 0) and head[e] not in parent:
                parent[head[e]] = e
                if head[e] == t:
                    return _path(parent, head, t), scanned, None
                queue.append(head[e])
    return None, scanned, set(parent)


def _search_dfs(adj, head, res, s, t, use_back):
    parent = {s: -1}
    stack = [(s, iter(adj[s]))]
    scanned = 0
    while stack:
        u, it = stack[-1]
        advanced = False
        for e in it:
            scanned += 1
            if res[e] > 0 and (use_back or e % 2 == 0) and head[e] not in parent:
                parent[head[e]] = e
                if head[e] == t:
                    return _path(parent, head, t), scanned, None
                stack.append((head[e], iter(adj[head[e]])))
                advanced = True
                break
        if not advanced:
            stack.pop()
    return None, scanned, set(parent)


def _search_widest(adj, head, res, s, t, use_back):
    """Weg mit dem größten Engpass (Dijkstra-Variante: statt Weglänge wird das Minimum der Restkapazitäten maximiert)."""
    best = {s: 1 << 60}
    parent = {s: -1}
    heap = [(-(1 << 60), 0, s)]
    counter = 1
    settled = set()
    scanned = 0
    while heap:
        neg, _, u = heapq.heappop(heap)
        if u in settled:
            continue
        settled.add(u)
        if u == t:
            return _path(parent, head, t), scanned, None
        for e in adj[u]:
            scanned += 1
            if res[e] > 0 and (use_back or e % 2 == 0):
                v = head[e]
                width = min(-neg, res[e])
                if v not in settled and width > best.get(v, 0):
                    best[v] = width
                    parent[v] = e
                    heapq.heappush(heap, (-width, counter, v))
                    counter += 1
    return None, scanned, set(settled)


def _path(parent, head, t):
    path = []
    node = t
    while parent[node] != -1:
        e = parent[node]
        path.append(e)
        node = head[e ^ 1]
    path.reverse()
    return tuple(path)


SEARCHES = {"bfs": _search_bfs, "dfs": _search_dfs, "widest": _search_widest}


def _reachable(adj, head, res, start, reverse=False):
    """Alle Knoten, die von `start` aus (bzw. mit `reverse` zu `start` hin) über Restkanten erreichbar sind."""
    seen = {start}
    queue = deque([start])
    while queue:
        u = queue.popleft()
        for e in adj[u]:
            # vorwärts: Kante e verlässt u; rückwärts: Kante e^1 führt nach u (ihre Restkapazität zählt)
            edge = e ^ 1 if reverse else e
            if res[edge] > 0 and head[e] not in seen:
                seen.add(head[e])
                queue.append(head[e])
    return seen


def max_flow(net, rule="bfs", back_arcs=True, chooser=None, keep_flows=True):
    """Maximaler Fluss. `back_arcs=False` lässt die Rückkanten weg (nur Vorwärtskanten): ein Greedy-Verfahren ohne 'Umleiten'.
    `chooser(k, res)` darf den k-ten Weg vorgeben (Gegenspieler-Experiment); gibt er None zurück, sucht `rule` weiter.
    `keep_flows=False` spart die Flusszustände je Runde (für Verteilungen über viele Netze): `flows` enthält dann nur den leeren und den fertigen Fluss."""
    adj, head = _adjacency(net)
    res = [0] * (2 * net.m)
    for i, (_, _, cap, _, _) in enumerate(net.arcs):
        res[2 * i] = cap
    search = SEARCHES[rule]
    rounds = []
    flows = [tuple([0] * net.m)]
    value = 0
    scanned_total = 0
    while True:
        path = None
        scanned = 0
        if chooser is not None:
            path = chooser(len(rounds), res)
        if path is None:
            path, scanned, visited = search(adj, head, res, net.s, net.t, back_arcs)
        if path is None:
            break
        bottleneck = min(res[e] for e in path)
        for e in path:
            res[e] -= bottleneck
            res[e ^ 1] += bottleneck
        value += bottleneck
        scanned_total += scanned
        nodes = (net.s,) + tuple(head[e] for e in path)
        rounds.append(Round(path, nodes, bottleneck, len(path), value, scanned, any(e % 2 for e in path)))
        if keep_flows:
            flows.append(tuple(net.arcs[i][2] - res[2 * i] for i in range(net.m)))
    scanned_total += scanned
    if not keep_flows:
        flows.append(tuple(net.arcs[i][2] - res[2 * i] for i in range(net.m)))
    reach = _reachable(adj, head, res, net.s)
    co_reach = _reachable(adj, head, res, net.t, reverse=True)
    cut = tuple(i for i, (u, v, _, _, _) in enumerate(net.arcs) if u in reach and v not in reach)
    unique = all(v in reach or v in co_reach for v in range(net.n))
    return Result(
        rounds=tuple(rounds),
        flows=tuple(flows),
        value=value,
        reach=tuple(v in reach for v in range(net.n)),
        co_reach=tuple(v in co_reach for v in range(net.n)),
        cut_arcs=cut,
        cut_capacity=sum(net.arcs[i][2] for i in cut),
        final_scanned=scanned,
        scanned_total=scanned_total,
        unique_cut=unique,
    )


def has_augmenting_path(net, flow):
    """Unabhängige Gegenprobe: gibt es zu diesem Fluss noch einen Verbesserungsweg? (Breitensuche im Restgraphen, ohne Rundenlogik)"""
    adj, head = _adjacency(net)
    res = [0] * (2 * net.m)
    for i, (_, _, cap, _, _) in enumerate(net.arcs):
        res[2 * i] = cap - flow[i]
        res[2 * i + 1] = flow[i]
    return net.t in _reachable(adj, head, res, net.s)


def flow_cost(net, flow):
    return sum(flow[i] * net.arcs[i][3] for i in range(net.m))
