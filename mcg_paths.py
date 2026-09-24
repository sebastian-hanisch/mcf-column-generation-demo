"""Pfade im Mehrgütermodell: Nachbarschaftslisten je Gut, Zählung und Aufzählung einfacher Quelle-Senke-Pfade, Pfadzerlegung eines Kantenflusses.

Ein Pfad ist hier immer ein Weg von der Quelle S zur Senke T über Kantenindizes, einschließlich der Angebotskante (S -> Start) und der Nachfragekante (Ziel -> T). Für Gut k stehen nur Kanten zur Verfügung,
deren gutspezifische Obergrenze ub[k][e] positiv ist (ein Werk ohne das Gut hat keine Angebotskante für k).
"""

from collections import deque


def good_arcs(mcf, k):
    """Kanten, die Gut k benutzen darf."""
    return [e for e in range(mcf.m) if mcf.ub[k][e] > 0]


def adjacency(mcf, k):
    """out[u] = [(Kante, Endknoten), ...] für Gut k."""
    out = [[] for _ in range(mcf.net.n)]
    for e in good_arcs(mcf, k):
        u, v = mcf.net.arcs[e][0], mcf.net.arcs[e][1]
        out[u].append((e, v))
    return out


def _is_dag(out):
    """Kahn: hat der Graph keinen Kreis?"""
    n = len(out)
    indeg = [0] * n
    for u in range(n):
        for _, v in out[u]:
            indeg[v] += 1
    queue = deque(u for u in range(n) if indeg[u] == 0)
    seen = 0
    while queue:
        u = queue.popleft()
        seen += 1
        for _, v in out[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    return seen == n


def count_paths(mcf, k, limit=10 ** 6, budget=400000):
    """Anzahl der einfachen S-T-Pfade von Gut k. Im Distributionsnetz (ohne Kreis) exakt per Zählung von hinten; im Streckennetz mit beidseitigen Kanten per Tiefensuche, die bei `limit` aufgibt
    (Rückgabe (limit, False): mindestens so viele) oder nach `budget` Schritten der Suche (Rückgabe (bisher gezählt, False)). Rückgabe (Anzahl, exakt)."""
    net = mcf.net
    out = adjacency(mcf, k)
    if _is_dag(out):
        memo = {}

        def ways(u):
            if u == net.t:
                return 1
            if u not in memo:
                memo[u] = sum(ways(v) for _, v in out[u])
            return memo[u]
        return ways(net.s), True
    count = 0
    on_path = [False] * net.n
    stack = [(net.s, iter(out[net.s]))]
    on_path[net.s] = True
    steps = 0
    while stack:
        u, it = stack[-1]
        steps += 1
        if steps > budget:
            return count, False
        for _, v in it:
            if v == net.t:
                count += 1
                if count >= limit:
                    return limit, False
            elif not on_path[v]:
                on_path[v] = True
                stack.append((v, iter(out[v])))
                break
        else:
            on_path[u] = False
            stack.pop()
    return count, True


def enumerate_paths(mcf, k, limit=100000):
    """Alle einfachen S-T-Pfade von Gut k als Kantentupel (Tiefensuche); `limit` schützt vor Explosion (ValueError)."""
    net = mcf.net
    out = adjacency(mcf, k)
    paths = []
    on_path = [False] * net.n

    def walk(u, edges):
        if u == net.t:
            paths.append(tuple(edges))
            if len(paths) > limit:
                raise ValueError("zu viele Pfade")
            return
        on_path[u] = True
        for e, v in out[u]:
            if not on_path[v]:
                edges.append(e)
                walk(v, edges)
                edges.pop()
        on_path[u] = False
    walk(net.s, [])
    return paths


def path_cost(mcf, k, edges):
    """Echte Kosten des Pfades für Gut k (ohne die Belohnung auf der Nachfragekante)."""
    return sum(mcf.cost(k, e) for e in edges if not mcf.reward[e])


def path_nodes(mcf, edges):
    """Knotenfolge eines Kantenpfades."""
    arcs = mcf.net.arcs
    return [arcs[edges[0]][0]] + [arcs[e][1] for e in edges]


def decompose_flow(mcf, row, tol=1e-9):
    """Zerlegt den Fluss `row` (eine Kantenliste der Länge m) eines Guts in S-T-Pfade: immer wieder ein Pfad im Träger (Breitensuche), so viel abziehen, wie der engste Abschnitt hergibt.
    Rückgabe [(Kantentupel, Menge), ...]; Kreise im Fluss bleiben liegen (bei nichtnegativen Kosten kommen sie in optimalen Flüssen nicht vor)."""
    net = mcf.net
    rest = [float(v) for v in row]
    out = [[] for _ in range(net.n)]
    for e, (u, v, _, _, _) in enumerate(net.arcs):
        out[u].append((e, v))
    result = []
    while True:
        prev = {net.s: None}
        queue = deque([net.s])
        while queue and net.t not in prev:
            u = queue.popleft()
            for e, v in out[u]:
                if rest[e] > tol and v not in prev:
                    prev[v] = (u, e)
                    queue.append(v)
        if net.t not in prev:
            return result
        edges, v = [], net.t
        while prev[v] is not None:
            u, e = prev[v]
            edges.append(e)
            v = u
        edges.reverse()
        amount = min(rest[e] for e in edges)
        for e in edges:
            rest[e] -= amount
        result.append((tuple(edges), amount))
