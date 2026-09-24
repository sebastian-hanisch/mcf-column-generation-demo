"""Plotly-Abbildungen: Netz mit Preisen, Master-Fluss und neu gefundenen Pfaden je Runde, Konvergenz, Spalten, Optionen, Pfadzahlen und Größe.
Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht zoomen. Kanten haben über unsichtbare Marker einen Hover-Text
(Plotly-Linien reagieren nur an ihren Stützpunkten)."""

from math import atan2, degrees, hypot

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import mcg_constants as C


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.08), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def _layout(fig, net, height, skip=()):
    xs = [p[0] for v, p in enumerate(net.pos) if v not in skip]
    ys = [p[1] for v, p in enumerate(net.pos) if v not in skip]
    pad = 9
    fig.update_xaxes(visible=False, range=[min(xs) - pad, max(xs) + pad], scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False, range=[min(ys) - pad, max(ys) + pad])
    return _base(fig, height)


def _curve(p0, p1, bulge, steps=8):
    """Punkte von p0 nach p1; mit `bulge` > 0 als flacher Bogen nach rechts (so trennen sich Vorwärts- und Rückkante). Dazu der Pfeilwinkel bei 65 %."""
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    length = hypot(dx, dy) or 1.0
    cx, cy = (x0 + x1) / 2 + bulge * length * dy / length, (y0 + y1) / 2 - bulge * length * dx / length
    ts = [k / steps for k in range(steps + 1)]
    xs = [(1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1 for t in ts]
    ys = [(1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1 for t in ts]
    t = 0.65
    tx = 2 * (1 - t) * (cx - x0) + 2 * t * (x1 - cx)
    ty = 2 * (1 - t) * (cy - y0) + 2 * t * (y1 - cy)
    ax = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1
    ay = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1
    return xs, ys, (ax, ay, degrees(atan2(tx, ty))), (xs[steps // 2], ys[steps // 2])


def _segments(curves):
    x, y = [], []
    for xs, ys, _, _ in curves:
        x += xs + [None]
        y += ys + [None]
    return x, y


def _lines(fig, curves, color, width, name, dash=None, showlegend=True):
    if not curves:
        return
    x, y = _segments(curves)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=width, dash=dash), hoverinfo="skip", name=name, showlegend=showlegend))


def _arrows(fig, curves, color, size=9):
    if not curves:
        return
    fig.add_trace(go.Scatter(x=[c[2][0] for c in curves], y=[c[2][1] for c in curves], mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(symbol="arrow", size=size, color=color, angle=[c[2][2] for c in curves])))


def _hover_points(fig, net, entries):
    """Unsichtbare Marker entlang jeder Kante, damit der Hover-Text überall auf der Kante erscheint. entries: [(Kurve, Text)]"""
    x, y, text = [], [], []
    for curve, label in entries:
        xs, ys = curve[0], curve[1]
        for k in range(1, len(xs) - 1):
            x.append(xs[k]); y.append(ys[k]); text.append(label)
    if x:
        fig.add_trace(go.Scatter(x=x, y=y, mode="markers", marker=dict(size=9, opacity=0), hovertext=text, hoverinfo="text", showlegend=False))


def _labels(fig, points):
    """points: [(x, y, Text)] - als Annotationen mit heller Hinterlegung, damit sie Kanten, Pfeile und Knotenbeschriftungen nicht unlesbar machen."""
    for x, y, text in points:
        fig.add_annotation(x=x, y=y, text=text, showarrow=False, xanchor="left", font=dict(size=11, color="#111"), bgcolor="rgba(255,255,255,0.88)", borderpad=1)


def _arc_name(net, i):
    u, v = net.arcs[i][0], net.arcs[i][1]
    return f"{net.names[u]} → {net.names[v]}"


def _nodes(fig, net, reach=None):
    """Knoten: S und T als Quadrate, alle anderen als Kreise; mit `reach` grün (von S erreichbar) oder grau eingefärbt."""
    text_pos = {0: "top center", 1: "bottom center"}
    for kind, idx in (("Quelle/Senke", [net.s, net.t]), ("Knoten", [v for v in range(net.n) if v not in (net.s, net.t)])):
        colors = [C.COLORS["node"] if reach is None else (C.COLORS["reach"] if reach[v] else C.COLORS["unreach"]) for v in idx]
        pos = [text_pos.get(v, "top center" if net.pos[v][1] > 70 else ("bottom center" if net.pos[v][1] < 30 else "middle left")) for v in idx]
        if net.logistic and kind == "Knoten":
            pos = ["top center" if net.names[v].startswith("Werk") else "bottom center" if net.names[v].startswith("Filiale") else "middle left" for v in idx]
        fig.add_trace(go.Scatter(
            x=[net.pos[v][0] for v in idx], y=[net.pos[v][1] for v in idx], mode="markers+text", showlegend=False,
            text=[net.labels[v] for v in idx], textposition=pos, hovertext=[net.names[v] for v in idx], hoverinfo="text",
            marker=dict(symbol="square" if kind == "Quelle/Senke" else "circle", size=13 if kind == "Quelle/Senke" else 10, color=colors, line=dict(width=1.5, color="#333"))))


def _wscale(net):
    return max(c for _, _, c, _, _ in net.arcs)


def _width(amount, top, lo=1.0, hi=6.0):
    return lo + (hi - lo) * amount / top if top else lo


def _node_text_positions(net, idx):
    if net.logistic:
        return ["top center" if (v == 0 or net.names[v].startswith("Werk")) else "bottom center" if (v == 1 or net.names[v].startswith("Filiale")) else "middle left" for v in idx]
    return ["top center" if v == net.s else "bottom center" if v == net.t else "middle left" for v in idx]


TOL = 1e-6


def _shift(curve, dx, dy):
    xs, ys, (ax, ay, ang), (mx, my) = curve
    return [x + dx for x in xs], [y + dy for y in ys], (ax + dx, ay + dy, ang), (mx + dx, my + dy)


def _fmt(x):
    return f"{x:.1f}".replace(".", ",") if abs(x - round(x)) > TOL else f"{round(x)}"


def mcg_color(k):
    import mcg_model as md
    return md.GOOD_COLORS[k % len(md.GOOD_COLORS)]


def _is_terminal(net, e):
    return net.arcs[e][0] == net.s or net.arcs[e][1] == net.t


def _price(x):
    return f"{x:.0f}" if x >= 10 else _fmt(round(x, 1))


def build_cg(mcf, rd, columns, height=460):
    """Netz einer Runde der Column Generation: je Gut eine Farbe (Breite ~ Fluss des Masters), orange Unterlage mit dem Preis λ an den Kanten mit positivem Schattenpreis, schwarz gestrichelt die in dieser Runde
    vom Pricing gefundenen (und aufgenommenen) Pfade. Im Streckennetz sind die Kanten von S und zu T ausgeblendet; Start (Raute) und Ziel (Stern) jedes Guts sind markiert."""
    net = mcf.net
    grid = mcf.layout == "grid"
    fig = go.Figure()
    x = rd.x
    K = mcf.K
    caps = [a[2] for a in net.arcs]
    top = max((caps[e] for e in range(mcf.m) if mcf.joint[e]), default=1)
    bulge = 0.0 if net.logistic else 0.12
    groups, faint, under, hover, labels = {}, [], [], [], []
    small = mcf.m <= 30
    for e, (u, v, cap, cost, kind) in enumerate(net.arcs):
        if grid and _is_terminal(net, e):
            continue
        base = _curve(net.pos[u], net.pos[v], bulge)
        load = float(x[:, e].sum())
        parts = ", ".join(f"{mcf.names[k]} {_fmt(x[k, e])}" for k in range(K) if x[k, e] > TOL)
        price_txt = f", Preis λ {rd.lam[e]:.2f}".replace(".", ",") if mcf.joint[e] and rd.lam[e] > TOL else ""
        hover.append((base, f"{_arc_name(net, e)}: Summe {_fmt(load)}" + (f" von {cap}" if mcf.joint[e] else "") + (f" ({parts})" if parts else "") + price_txt))
        faint.append(base)
        bind = mcf.joint[e] and rd.lam[e] > TOL
        if bind:
            under.append(base)
        dx0, dy0 = net.pos[v][0] - net.pos[u][0], net.pos[v][1] - net.pos[u][1]
        length = (dx0 ** 2 + dy0 ** 2) ** 0.5 or 1.0
        nx, ny = -dy0 / length, dx0 / length
        active = [k for k in range(K) if x[k, e] > TOL]
        for j, k in enumerate(active):
            off = (j - (len(active) - 1) / 2) * 1.1
            f = x[k, e]
            frac = abs(f - round(f)) > TOL
            groups.setdefault((k, max(1, round(1.5 + 5 * f / top)), frac), []).append(_shift(base, nx * off, ny * off))
        if bind:
            labels.append((base[0][3] + 1.5, base[1][3], f"λ {_price(rd.lam[e])}"))
        elif any(abs(x[k, e] - round(x[k, e])) > TOL for k in range(K)):
            labels.append((base[0][3] + 1.5, base[1][3], "/".join(_fmt(x[k, e]) for k in active)))
        elif small and load > TOL:
            labels.append((base[0][3] + 1.5, base[1][3], f"{_fmt(load)}" + (f"/{cap}" if mcf.joint[e] else "")))
    _lines(fig, under, C.COLORS["price"], 12, "Preis λ > 0 (bindende Kapazität)")
    _lines(fig, faint, C.COLORS["faint"], 1.0, "Kante", showlegend=False)
    for (k, w, frac), curves in sorted(groups.items()):
        _lines(fig, curves, mcg_color(k), w, mcf.names[k], dash="dot" if frac else None, showlegend=False)
    for k in range(K):
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=mcg_color(k), width=4), name=mcf.names[k]))
    new_curves = []
    for idx in rd.new:
        for e in columns[idx].edges:
            if grid and _is_terminal(net, e):
                continue
            u, v = net.arcs[e][0], net.arcs[e][1]
            new_curves.append(_curve(net.pos[u], net.pos[v], bulge))
    if new_curves:
        _lines(fig, new_curves, C.COLORS["new"], 2.5, "neu gefundener Pfad (Pricing)", dash="dash")
    if any(f for (_, _, f) in groups):
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color="#555", width=3, dash="dot"), name="gestrichelt: gebrochener Fluss"))
    if net.m <= 80:
        _arrows(fig, faint, "rgba(60,60,60,0.55)", 7)
    _hover_points(fig, net, hover)
    _labels(fig, labels)
    idx = [v for v in range(net.n) if not (grid and v in (net.s, net.t))]
    fig.add_trace(go.Scatter(x=[net.pos[v][0] for v in idx], y=[net.pos[v][1] for v in idx], mode="markers+text", showlegend=False, text=[net.labels[v] for v in idx], textposition=_node_text_positions(net, idx),
                             hovertext=[net.names[v] for v in idx], hoverinfo="text", marker=dict(symbol=["square" if v in (net.s, net.t) else "circle" for v in idx], size=[13 if v in (net.s, net.t) else (7 if grid else 10) for v in idx],
                                                                                              color=C.COLORS["node"], line=dict(width=1.5, color="#333"))))
    if grid:
        for k in range(K):
            o = [net.arcs[e][1] for e in range(mcf.m) if net.arcs[e][0] == net.s and mcf.ub[k][e] > 0]
            t = [net.arcs[e][0] for e in range(mcf.m) if net.arcs[e][1] == net.t and mcf.ub[k][e] > 0]
            dem = mcf.demand(k)
            fig.add_trace(go.Scatter(x=[net.pos[v][0] for v in o], y=[net.pos[v][1] for v in o], mode="markers+text", showlegend=False, text=[f"{k + 1}" for _ in o], textposition="top center",
                                     hovertext=[f"Start {mcf.names[k]} (Menge {dem})" for _ in o], hoverinfo="text", marker=dict(symbol="diamond", size=14, color=mcg_color(k), line=dict(width=1.5, color="#333"))))
            fig.add_trace(go.Scatter(x=[net.pos[v][0] for v in t], y=[net.pos[v][1] for v in t], mode="markers+text", showlegend=False, text=[f"{k + 1}" for _ in t], textposition="bottom center",
                                     hovertext=[f"Ziel {mcf.names[k]} (Menge {dem})" for _ in t], hoverinfo="text", marker=dict(symbol="star", size=14, color=mcg_color(k), line=dict(width=1.5, color="#333"))))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(symbol="diamond", size=10, color="#777"), name="Start des Guts (Nummer)"))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(symbol="star", size=10, color="#777"), name="Ziel des Guts"))
    fig = _layout(fig, net, height, skip=(net.s, net.t) if grid else ())
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=90 if grid else 70), legend=dict(orientation="h", y=-0.12))
    return fig


def build_convergence(result, current, lp_obj, M, height=300):
    """Wert in Einheiten (-Z/M): der Master (erreichbar) steigt, die Farley-Schranke (nicht besser möglich) sinkt; gestrichelt das Optimum des Kanten-LP."""
    rs = result.rounds
    xs = [rd.r for rd in rs]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=[-rd.obj / M for rd in rs], mode="lines+markers", name="Master (erreichbar)", line=dict(color=C.COLORS["flow"], width=2)))
    if not result.config.get("ignore_mu"):
        fig.add_trace(go.Scatter(x=xs, y=[-rd.lb / M for rd in rs], mode="lines+markers", name="Farley-Schranke (nicht besser möglich)", line=dict(color="#2ca02c", width=2)))
    fig.add_hline(y=-lp_obj / M, line=dict(color="#555", dash="dash"), annotation_text="Kanten-LP", annotation_position="bottom right")
    fig.add_vline(x=current, line=dict(color=C.COLORS["optimal"], dash="dot"))
    fig.update_xaxes(title="Runde", dtick=1 if len(xs) <= 16 else None)
    fig.update_yaxes(title="Wert −Z/M [Einheiten]")
    fig = _base(fig, height)
    fig.update_layout(legend=dict(orientation="h", y=-0.35), height=height + 40, margin=dict(l=10, r=10, t=10, b=10))
    return fig


def build_columns(result, current, n_vars, n_paths, paths_exact, height=260):
    """Spalten im Master je Runde (logarithmisch) gegen die Variablen des Kanten-LP und die Zahl aller möglichen Pfade."""
    rs = result.rounds
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[rd.r for rd in rs], y=[max(rd.n_columns, 0.5) for rd in rs], marker=dict(color=C.COLORS["flow"], opacity=[1.0 if rd.r == current else 0.4 for rd in rs]), showlegend=False,
                         hovertext=[f"Runde {rd.r}: {rd.n_columns} Spalten" for rd in rs], hoverinfo="text"))
    xr = [-0.5, len(rs) - 0.5]
    fig.add_trace(go.Scatter(x=xr, y=[n_vars, n_vars], mode="lines", line=dict(color="#d62728", dash="dash"), name=f"Kanten-LP: {n_vars} Variablen"))
    fig.add_trace(go.Scatter(x=xr, y=[max(n_paths, 1)] * 2, mode="lines", line=dict(color="#7f7f7f", dash="dot"), name=("alle Pfade: " if paths_exact else "alle Pfade: mindestens ") + f"{n_paths}"))
    fig.update_xaxes(title="Runde", dtick=1 if len(rs) <= 16 else None)
    fig.update_yaxes(title="Spalten", type="log")
    fig = _base(fig, height)
    fig.update_layout(legend=dict(orientation="h", y=-0.4), height=height + 50, margin=dict(l=10, r=10, t=10, b=10))
    return fig


SHORT_VARIANTS = ("Standard", "eine je Runde", "Start Nacheinander", "α = 0,5", "α = 0,8", "ohne μ")


def build_options(rows, height=300):
    """Runden und Spalten je Option (Mittel über 100 feste Netze); die Negativkontrolle bekommt eine rote Kontur, weil sie mit einem falschen Wert anhält."""
    fig = go.Figure()
    names = SHORT_VARIANTS[:len(rows)]
    fig.add_trace(go.Bar(x=names, y=[r["rounds"] for r in rows], name="Runden", marker_color=C.COLORS["flow"],
                         marker_line=dict(width=[0 if r["exact"] > 0.5 else 3 for r in rows], color="#d62728"), hovertext=[f"{r['name']}: {r['rounds']:.1f} Runden, {r['exact'] * 100:.0f} % im Optimum" for r in rows], hoverinfo="text"))
    fig.add_trace(go.Bar(x=names, y=[r["columns"] for r in rows], name="Spalten", marker_color="#9467bd", hovertext=[f"{r['name']}: {r['columns']:.1f} Spalten" for r in rows], hoverinfo="text"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="Mittel über 100 Netze")
    fig = _base(fig, height)
    fig.update_layout(legend=dict(orientation="h", y=-0.3), height=height + 40, margin=dict(l=10, r=10, t=10, b=10))
    return fig


def build_paths(rows, height=320):
    """Mögliche Pfade, Variablen des Kanten-LP und Spalten der Column Generation je Gittergröße (logarithmisch)."""
    fig = go.Figure()
    labels = [f"{r['size'][0]}×{r['size'][1]}" for r in rows]
    fig.add_trace(go.Scatter(x=labels, y=[r["paths"] for r in rows], mode="lines+markers", name="mögliche Pfade (alle Güter)", line=dict(color="#7f7f7f", dash="dot")))
    fig.add_trace(go.Scatter(x=labels, y=[r["vars"] for r in rows], mode="lines+markers", name="Variablen K·m", line=dict(color="#d62728", dash="dash")))
    fig.add_trace(go.Scatter(x=labels, y=[r["columns"] for r in rows], mode="lines+markers", name="Spalten der CG", line=dict(color=C.COLORS["flow"])))
    fig.add_trace(go.Scatter(x=labels, y=[r["used"] for r in rows], mode="lines+markers", name="Spalten mit Fluss", line=dict(color="#2ca02c")))
    fig.update_xaxes(title="Gitter")
    fig.update_yaxes(title="Anzahl", type="log")
    fig = _base(fig, height)
    fig.update_layout(legend=dict(orientation="h", y=-0.4), height=height + 50, margin=dict(l=10, r=10, t=10, b=10))
    return fig


def build_size(rows, height=300):
    """Simplex-Iterationen gesamt: Kanten-LP gegen Column Generation (alle Runden zusammen) je Gittergröße."""
    fig = go.Figure()
    labels = [f"{r['size'][0]}×{r['size'][1]}" for r in rows]
    fig.add_trace(go.Bar(x=labels, y=[r["lp_iterations"] for r in rows], name="Kanten-LP", marker_color="#d62728"))
    fig.add_trace(go.Bar(x=labels, y=[r["cg_iterations"] for r in rows], name="Column Generation (alle Runden)", marker_color=C.COLORS["flow"]))
    fig.update_layout(barmode="group")
    fig.update_xaxes(title="Gitter")
    fig.update_yaxes(title="HiGHS-Iterationen")
    fig = _base(fig, height)
    fig.update_layout(legend=dict(orientation="h", y=-0.3), height=height + 40, margin=dict(l=10, r=10, t=10, b=10))
    return fig


def build_rounds_hist(rounds, current=None, height=260):
    """Runden bis zum Optimum über die 100 festen Netze; rot gestrichelt die Runden des gezeigten Netzes."""
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=rounds, xbins=dict(size=1), marker_color=C.COLORS["flow"], showlegend=False))
    if current is not None:
        fig.add_vline(x=current, line=dict(color=C.COLORS["optimal"], dash="dash"), annotation_text="Ihre Ziehung", annotation_position="top")
    fig.update_xaxes(title="Runden bis zum Optimum")
    fig.update_yaxes(title="Netze")
    fig = _base(fig, height)
    fig.update_layout(margin=dict(l=10, r=10, t=30 if current is not None else 10, b=10))
    return fig
