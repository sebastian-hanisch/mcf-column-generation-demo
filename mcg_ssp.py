"""Successive Shortest Paths: kostenminimaler Fluss durch den jeweils billigsten Weg im Restgraphen.

Gegeben ein Netz mit Kapazitäten und Kosten je Einheit. SSP füllt wiederholt den **billigsten** Weg von S nach T im Restgraphen auf (nicht den mit den wenigsten Kanten, wie Edmonds-Karp): eine Vorwärtskante kostet c, ihre Rückkante -c
(zurückgenommener Fluss spart Geld). Weil kein negativer Kreis im Restgraphen entsteht, ist der Fluss nach jeder Runde ein **kostenminimaler Fluss seiner Menge**; die Kosten je Einheit der Wege (Grenzkosten) sind nicht fallend.

Restkanten wie in den Vorgänger-Demos: Kante 2i ist die Vorwärtskante der Netzkante i (Rest = Kapazität - Fluss, Kosten c), Kante 2i+1 die Rückkante (Rest = Fluss, Kosten -c).

Drei Suchen nach dem billigsten Weg:
- **dijkstra**: Dijkstra auf **reduzierten Kosten** c(u,v) + pi(u) - pi(v) >= 0 (Johnson). Nach jeder Suche wird pi(v) um min(d(v), d(T)) erhöht; die Potenziale bleiben gültig (alle Restkanten reduziert >= 0) und sind die **Schattenpreise**:
  pi(T) - pi(S) ist der Preis der nächsten Einheit. Start pi = 0 (alle Kosten >= 0).
- **spfa**: Bellman-Ford mit Warteschlange auf den echten Kosten, ohne Potenziale (Referenz).
- **naive**: Dijkstra auf den echten Kosten - trotz negativer Rückkantenkosten. Ein einmal abgeschlossener Knoten wird nie mehr korrigiert, der Weg kann also teurer als nötig sein. Negativkontrolle, kein zulässiges Verfahren.

Aufwand wird in gescannten Kanten gezählt (jede in einer Adjazenzliste angesehene Restkante), nie in Sekunden.
"""

import heapq
from collections import deque
from dataclasses import dataclass

from mcg_edmonds_karp import _adjacency

INF = float("inf")
SEARCHES = ("dijkstra", "spfa", "naive")


@dataclass(frozen=True)
class Round:
    path: tuple            # Restkanten-Indizes von S nach T (gerade = Vorwärts-, ungerade = Rückkante)
    nodes: tuple           # Knotenfolge von S nach T
    bottleneck: int
    length: int
    price: int             # Kosten je Einheit auf diesem Weg (Grenzkosten)
    value: int             # Flusswert nach der Runde
    total: int             # Gesamtkosten nach der Runde
    scanned: int
    uses_back_arc: bool
    potentials: tuple      # Potenziale nach der Runde (leer außer bei 'dijkstra' mit Trace)
    flow_after: tuple      # Fluss je Netzkante nach der Runde (leer ohne Trace)


@dataclass(frozen=True)
class Result:
    rounds: tuple
    value: int
    total: int             # Gesamtkosten des Flusses
    flow: tuple
    potentials: tuple      # Potenziale des Verfahrens (nur 'dijkstra'), sonst leer
    final_scanned: int     # letzte, gescheiterte Suche
    scanned_total: int
    search: str

    @property
    def n_rounds(self):
        return len(self.rounds)


def _costs(net):
    cost = [0] * (2 * net.m)
    for i, arc in enumerate(net.arcs):
        cost[2 * i] = arc[3]
        cost[2 * i + 1] = -arc[3]
    return cost


def _path(parent, head, t):
    path, node = [], t
    while parent[node] != -1:
        e = parent[node]
        path.append(e)
        node = head[e ^ 1]
    path.reverse()
    return tuple(path)


def _search_dijkstra(adj, head, res, cost, pi, s, t):
    """Dijkstra auf reduzierten Kosten. Rückgabe (Pfad oder None, durchsuchte Kanten, Potenzial-Zuwachs je Knoten). Hält an, sobald T abgeschlossen ist."""
    n = len(adj)
    dist = [INF] * n
    dist[s] = 0
    parent = [-1] * n
    heap = [(0, s)]
    done = [False] * n
    scanned = 0
    while heap:
        d, u = heapq.heappop(heap)
        if done[u]:
            continue
        done[u] = True
        if u == t:
            return _path(parent, head, t), scanned, [min(dist[v], d) for v in range(n)]
        for e in adj[u]:
            scanned += 1
            if res[e] > 0:
                v = head[e]
                nd = d + cost[e] + pi[u] - pi[v]
                if nd < dist[v]:
                    dist[v] = nd
                    parent[v] = e
                    heapq.heappush(heap, (nd, v))
    return None, scanned, None


def _search_spfa(adj, head, res, cost, s, t):
    n = len(adj)
    dist = [INF] * n
    dist[s] = 0
    parent = [-1] * n
    queue, queued = deque([s]), [False] * n
    scanned = 0
    while queue:
        u = queue.popleft()
        queued[u] = False
        for e in adj[u]:
            scanned += 1
            if res[e] > 0 and dist[u] + cost[e] < dist[head[e]]:
                v = head[e]
                dist[v] = dist[u] + cost[e]
                parent[v] = e
                if not queued[v]:
                    queued[v] = True
                    queue.append(v)
    if dist[t] == INF:
        return None, scanned
    return _path(parent, head, t), scanned


def _search_naive(adj, head, res, cost, s, t):
    """Dijkstra auf den echten Kosten, ein abgeschlossener Knoten wird nie mehr geändert (falsch bei negativen Kanten)."""
    n = len(adj)
    dist = [INF] * n
    dist[s] = 0
    parent = [-1] * n
    heap = [(0, s)]
    done = [False] * n
    scanned = 0
    while heap:
        d, u = heapq.heappop(heap)
        if done[u]:
            continue
        done[u] = True
        if u == t:
            return _path(parent, head, t), scanned
        for e in adj[u]:
            scanned += 1
            v = head[e]
            if res[e] > 0 and not done[v] and d + cost[e] < dist[v]:
                dist[v] = d + cost[e]
                parent[v] = e
                heapq.heappush(heap, (dist[v], v))
    return None, scanned


def ssp(net, search="dijkstra", target=None, keep_trace=True):
    """Kostenminimaler Fluss nach dem Successive-Shortest-Paths-Verfahren. `target`: gewünschte Menge (der letzte Weg wird gekürzt); None = so viel wie möglich."""
    if search not in SEARCHES:
        raise ValueError(search)
    adj, head = _adjacency(net)
    cost = _costs(net)
    n, s, t = net.n, net.s, net.t
    res = [0] * (2 * net.m)
    for i, (_, _, cap, _, _) in enumerate(net.arcs):
        res[2 * i] = cap
    pi = [0] * n
    rounds = []
    value = total = scanned_total = 0

    def flow_now():
        return tuple(net.arcs[i][2] - res[2 * i] for i in range(net.m))

    final_scanned = 0
    while target is None or value < target:
        gain = None
        if search == "dijkstra":
            path, scanned, gain = _search_dijkstra(adj, head, res, cost, pi, s, t)
        elif search == "spfa":
            path, scanned = _search_spfa(adj, head, res, cost, s, t)
        else:
            path, scanned = _search_naive(adj, head, res, cost, s, t)
        if path is None:
            final_scanned = scanned
            scanned_total += scanned
            break
        bottleneck = min(res[e] for e in path)
        if target is not None:
            bottleneck = min(bottleneck, target - value)
        price = sum(cost[e] for e in path)
        for e in path:
            res[e] -= bottleneck
            res[e ^ 1] += bottleneck
        if gain is not None:
            for v in range(n):
                pi[v] += gain[v]
        value += bottleneck
        total += bottleneck * price
        scanned_total += scanned
        nodes = (s,) + tuple(head[e] for e in path)
        rounds.append(Round(path, nodes, bottleneck, len(path), price, value, total, scanned, any(e % 2 for e in path),
                            tuple(pi) if (keep_trace and search == "dijkstra") else (), flow_now() if keep_trace else ()))
    return Result(tuple(rounds), value, total, flow_now(), tuple(pi) if search == "dijkstra" else (), final_scanned, scanned_total, search)


def certificate(net, flow):
    """Optimalitätszertifikat für einen Fluss: Potenziale aus einer Bellman-Ford-Rechnung von einem gedachten Start mit Kosten 0 zu allen Knoten.
    Rückgabe (Potenziale, gültig): gültig heißt, alle Restkanten haben reduzierte Kosten >= 0, es gibt also keinen negativen Kreis - der Fluss ist kostenminimal für seine Menge."""
    n = net.n
    pi = [0] * n
    arcs = []
    for i, (u, v, c, k, _) in enumerate(net.arcs):
        if c - flow[i] > 0:
            arcs.append((u, v, k))
        if flow[i] > 0:
            arcs.append((v, u, -k))
    for _ in range(n + 1):
        changed = False
        for u, v, k in arcs:
            if pi[u] + k < pi[v]:
                pi[v] = pi[u] + k
                changed = True
        if not changed:
            return tuple(pi), True
    return tuple(pi), False


def reduced_costs(net, flow, pi):
    """(Netzkante, Vorwärts-Rest > 0, reduzierte Kosten der Vorwärts-, der Rückkante) - zur Anzeige und für Tests."""
    out = []
    for i, (u, v, c, k, _) in enumerate(net.arcs):
        rc = k + pi[u] - pi[v]
        out.append((i, c - flow[i] > 0, flow[i] > 0, rc))
    return out


def flow_cost(net, flow):
    return sum(flow[i] * net.arcs[i][3] for i in range(net.m))
