"""Konstanten, Regler-Grenzen, Presets und feste Seed-Mengen der Demo "Pfad-Formulierung und Column Generation: nur die Pfade, die sich lohnen"."""

# --- Regler Distributionsnetz (wie in den Vorgänger-Demos) ------------------------------------------------------------------------
P_MIN, P_MAX, DEFAULT_P = 2, 6, 3            # Werke
D_MIN, D_MAX, DEFAULT_D = 2, 6, 3            # Verteilzentren
S_MIN, S_MAX, DEFAULT_S = 3, 12, 8           # Filialen
DENSITY_MIN, DENSITY_MAX, DEFAULT_DENSITY = 20, 100, 60   # Anteil vorhandener Lanes in ganzen Prozent, Schritt 10
SPREAD_MIN, SPREAD_MAX, DEFAULT_SPREAD = 0, 100, 50       # Streuung der Lane-Breiten in ganzen Prozent, Schritt 25
LOAD_MIN, LOAD_MAX, DEFAULT_LOAD = 40, 160, 90            # Gesamtnachfrage in Prozent der Werkskapazität, Schritt 10
DEFAULT_SEED = 155
SEED_MAX = 2_000_000_000

# --- Regler Streckennetz ------------------------------------------------------------------------------------------------------------
GW_MIN, GW_MAX, DEFAULT_GW = 3, 8, 5                      # Breite des Gitters
GH_MIN, GH_MAX, DEFAULT_GH = 3, 6, 4                      # Höhe des Gitters
GDENSITY_MIN, GDENSITY_MAX, DEFAULT_GDENSITY = 40, 100, 70   # Anteil der Gitterkanten (über den Spannbaum hinaus), Schritt 10
GCAP_MIN, GCAP_MAX, DEFAULT_GCAP = 1, 4, 2                # größte Kapazität je Kante und Richtung
GDEM_MIN, GDEM_MAX, DEFAULT_GDEM = 1, 6, 4                # größte Menge je Gut
DEFAULT_GSEED = 7

K_MIN, K_MAX, DEFAULT_K = 2, 5, 3            # Zahl der Güter

NETS = {
    "random": "Distributionsnetz (wie im Vorgänger)",
    "grid": "Streckennetz (Gitter mit Start-Ziel-Aufträgen)",
    "preis": "Preis-Netz: zwei Güter, eine Engstelle",
    "gap": "Frachtnetz mit Bruch (2 Güter, LP gebrochen)",
}
DEFAULT_NET = "random"
FIXED_NETS = ("preis", "gap")

PER_ROUND = {"alle": "Der beste Pfad je Gut", "eine": "Nur der insgesamt beste Pfad"}
DEFAULT_PER_ROUND = "alle"
START = {"leer": "Leer (das erste Pricing baut die Spalten)", "nacheinander": "Aus dem Nacheinander-Fahren (Stück 7)"}
DEFAULT_START = "leer"
ALPHAS = (0.0, 0.5, 0.8)
DEFAULT_ALPHA = 0.0
GAPS = (0.0, 0.01, 0.05)
DEFAULT_GAP = 0.0

# --- feste Seed-Mengen (dieselben wie in den Vorgänger-Demos; unabhängig vom Nutzer-Seed) ------------------------------------------
DIST_SEEDS = tuple(range(100000, 100100))
PATH_SEEDS = DIST_SEEDS[:5]
SIZE_SEEDS = DIST_SEEDS[:6]
GRID_SIZES = ((3, 3), (4, 3), (5, 4), (6, 4), (6, 5))      # Experiment: Spalten gegen mögliche Pfade (Dichte 100 %, drei Güter)
SCALE_SIZES = ((5, 4), (8, 6), (10, 6), (12, 8), (16, 10))  # Experiment: Größe und Kreuzungspunkt (K = 5)
PATH_LIMIT = 20000                                          # Zählung der Pfade je Gut in der Hauptansicht: ab hier "mindestens"
PATH_BUDGET = 600000                                        # Schritte der Tiefensuche, danach "mindestens"
TABLE_PATH_LIMIT = 10 ** 6                                  # dasselbe im Experiment "Spalten gegen mögliche Pfade" (je Gut): auf diesen Gittern zählt die Suche exakt
TABLE_PATH_BUDGET = 3 * 10 ** 7

COLORS = {"flow": "#1f77b4", "price": "rgba(255,127,14,0.35)", "new": "#111111", "faint": "rgba(150,150,150,0.45)", "node": "#111111", "optimal": "#d62728"}

# --- Presets -----------------------------------------------------------------------------------------------------------------
_BASE = dict(net="random", k=DEFAULT_K, p=DEFAULT_P, d=DEFAULT_D, s=DEFAULT_S, density=DEFAULT_DENSITY, spread=DEFAULT_SPREAD, load=DEFAULT_LOAD, seed=DEFAULT_SEED,
             gw=DEFAULT_GW, gh=DEFAULT_GH, gdensity=DEFAULT_GDENSITY, gcap=DEFAULT_GCAP, gdem=DEFAULT_GDEM, gseed=DEFAULT_GSEED,
             per_round=DEFAULT_PER_ROUND, start=DEFAULT_START, alpha=DEFAULT_ALPHA, gap=DEFAULT_GAP, ignore_mu=False)
PRESETS = {
    "🚚 Zufallsnetz": {**_BASE},
    "🗺️ Streckennetz": {**_BASE, "net": "grid", "k": 4},
    "🔀 Preis-Wende": {**_BASE, "net": "preis", "k": 2},
    "🧩 Frachtnetz mit Bruch": {**_BASE, "net": "gap", "k": 2},
    "🚀 Start aus Nacheinander": {**_BASE, "start": "nacheinander"},
    "🐢 Eine Spalte je Runde": {**_BASE, "per_round": "eine"},
    "🕸️ Dichtes Streckennetz": {**_BASE, "net": "grid", "k": 5, "gw": 8, "gh": 5, "gdensity": 100},
    "🚫 Negativkontrolle": {**_BASE, "ignore_mu": True},
}
PRESET_HELP = {
    "🚚 Zufallsnetz": "Das Netz der Vorgänger-Demos (Seed 155, drei Güter): das Kanten-LP hatte 114 Variablen; hier endet die Column Generation nach 14 Runden mit 31 Spalten, davon 20 mit Fluss - im Optimum 67 von 76 Einheiten für 1548.",
    "🗺️ Streckennetz": "Ein Gitter 5 × 4 mit vier Gütern, jedes von seinem Start zu seinem Ziel: 242 mögliche Pfade, 256 Variablen im Kanten-LP - die Column Generation braucht 16 Spalten in 5 Runden, 7 davon tragen im Optimum Fluss.",
    "🔀 Preis-Wende": "Zwei Güter von A nach D, die Direktstrecke trägt nur eine Einheit. Runde 1: beide fahren direkt und die Kante bekommt einen hohen Preis; Runde 2: der Umweg lohnt sich - der Preis der Direktstrecke ist genau der Mehrpreis des Umwegs.",
    "🧩 Frachtnetz mit Bruch": "Das LP-Optimum ist gebrochen (1,5 Einheiten, ganzzahlig 1): die Column Generation liefert genau dieses LP-Optimum, mit Pfaden als Spalten - die Ganzzahligkeit bräuchte Branch-and-Price.",
    "🚀 Start aus Nacheinander": "Dasselbe Netz, aber der Master startet mit den Pfaden aus dem Nacheinander-Fahren des Vorgängers: etwa halb so viele Runden.",
    "🐢 Eine Spalte je Runde": "Dasselbe Netz, aber pro Runde wird nur der insgesamt beste Pfad aufgenommen statt je einer pro Gut: mehr als doppelt so viele Runden.",
    "🕸️ Dichtes Streckennetz": "Volles Gitter 8 × 5 mit fünf Gütern: mindestens 28 000 mögliche Pfade, das Kanten-LP hat 720 Variablen, die Column Generation braucht 32 Spalten (9 mit Fluss) in 12 Runden - aber jede Runde löst das Master-LP neu.",
    "🚫 Negativkontrolle": "Das Pricing vergisst die Preise der Gut-Obergrenzen (Werks- und Nachfragekanten je Gut): es schlägt nur schon bekannte Pfade vor und hält mit einem falschen Wert an - die Preise sind nicht verhandelbar.",
}
