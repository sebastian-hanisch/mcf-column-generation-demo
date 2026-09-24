# Pfad-Formulierung und Column Generation – nur die Pfade, die sich lohnen – Streamlit-Demo

*(noch nicht deployed)*

Achtes Stück der **Netzwerkfluss-Linie** der "Konzepte"-Reihe für die Website "Sebastian Hanisch – Operations Research und Machine Learning", zweites im Mehrgüter-Ast, Konvergenz aus [Mehrgüterfluss](https://github.com/sebastian-hanisch/multicommodity-demo) und der Column Generation am Cutting-Stock-Problem (Demo `column-generation-demo`, dort ist das Pricing ein Rucksack, hier ein kürzester Weg):
anders als die Fall-Demos im Portfolio (ein Anwendungsfall, mehrere Verfahren im Vergleich) zeigt diese Demo **ein** Verfahren – die **Column Generation über Pfade** – an einem wachsenden Beispiel.
Im Vorgänger stand der Mehrgüterfluss als **Kanten-LP** mit einer Variable je Gut und Kante ($K\cdot m$ Stück). Hier bekommt jedes Gut **Pfade** als Variablen: ein Pfad von seinem Start zu seinem Ziel, dessen Wert angibt, wie viel auf ihm fährt. Es gibt exponentiell viele Pfade; der **Master** kennt zu Beginn keinen, löst sein LP über die bekannten und gibt die **Preise** der gemeinsamen Kapazitäten weiter.
Das **Pricing** ist ein gewöhnlicher **kürzester Weg** (Dijkstra) mit Kantenlänge = Kosten + Preis; ein Weg, der billiger ist als das, was eine Einheit einbringt, wird als neue **Spalte** aufgenommen. Findet kein Gut mehr einen solchen Weg, ist der Master **exakt das Kanten-LP-Optimum** – ohne dass je alle Pfade gesehen wurden.
Vehikel: das Distributionsnetz der Vorgänger-Demos (Standard, Seed 155), ein **Streckennetz** (Gitter mit Start-Ziel-Aufträgen, auf dem die Pfade explodieren) und zwei feste Lehrnetze (die Preis-Wende und das Frachtnetz mit Bruch).

**Einordnung in die Reihe (die Kanten des Graphen):** Die Entkopplung durch Preise aus dem Vorgänger lieferte den richtigen Wert, aber Einzelflüsse, die in etwa 69 % der Netze Kanten überlasteten. Jeder dieser Einzelflüsse ist ein Pfad; der Master mischt die Pfade zu einer **zulässigen** Lösung – das ist die Dantzig-Wolfe-Zerlegung des Mehrgüterflusses. Das Pricing ist der Ein-Gut-Fluss der ersten Stücke mit Preisen (hier Dijkstra mit nichtnegativen Längen).
Die Folgestücke: **Garg–Könemann** (dieselben Kürzeste-Wege-Orakel, aber ohne LP-Löser und mit Güte-Garantie) und das **Netzwerkdesign mit Fixkosten** (Benders-Zerlegung, Slope Scaling). Bisher gebaut: alle zwölf Stücke der Hauptlinie.
```
edmonds-karp-demo (Wurzel: Restgraph, Rückkanten, Max-Flow = Min-Cut)                  [gebaut]
  ├─ dinic-demo (viele kürzeste Wege je Phase: Niveaugraph, blockierender Fluss)        [gebaut]
  ├─ push-relabel-demo (kein Weg: Überschüsse schieben, Höhen anheben)                 [gebaut]
  └─ ssp-demo (Kosten: der billigste Weg im Restgraphen, Potenziale)                    [gebaut]
       ├─ cycle-canceling-demo (negative Kreise löschen) → Netzwerksimplex               [gebaut]
       │    (network-flow-demo)                                                          [gebaut als Fall-Demo]
       ├─ cost-scaling-demo (Push-Relabel + ε-Skalierung, das nutzt OR-Tools)           [gebaut]
       └─ multicommodity-demo (mehrere Güter teilen Kapazität: Kanten-LP, Preise)       [gebaut]
            ├─ mcf-column-generation-demo (Pfade als Spalten, Pricing = Dijkstra)       [dieses Stück]
            ├─ garg-koenemann-demo (Näherung mit Preisen, ohne LP-Löser)                [gebaut]
            └─ fixkosten-netzdesign-demo (Fixkosten: Schranke und Schnitte)             [gebaut]
                 ├─ benders-demo (Entwurf im Master, Fluss im Teilproblem)              [gebaut]
                 └─ slope-scaling-demo (Fixkosten linearisieren, ohne Beweis)           [gebaut]
```

## Ergebnis (Zahlen aus den Tests)

Jede hier genannte Zahl ist in `tests/test_claims.py` belegt: die Lehrnetze von Hand, die Beispielnetze über ihre Seeds, die Verteilungen über 100 feste Netze (Seeds 100000–100099, dieselben wie in den Vorgänger-Demos). Standard: 3 Güter, 3 Werke, 3 Verteilzentren, 8 Filialen, Netzdichte 60 %, Streuung 50 %, Auslastung 90 %; Streckennetz: Gitter 5 × 4, 70 % der Gitterkanten, Kapazität bis 2, Menge bis 4, vier Güter. Belohnung $M = 1000$ je gelieferter Einheit (erst liefern, dann sparen).
Netz-, Pfad- und Variablenzahlen sind ganzzahlig und exakt; **Runden, Spalten und Iterationen hängen vom LP-Löser ab** (degenerierte Duallösungen, andere HiGHS-Version → leicht andere Zahlen) und stehen hier gerundet („etwa“); die Tests prüfen sie mit Bändern. Die Kopien aus den Vorgänger-Demos sind bewacht: SSP 53 907 durchsuchte Kanten über die 100 Netze, Kanten-LP 67 von 76 Einheiten für 1548 (114 Variablen).

| Frage | Ergebnis |
|---|---|
| Endet die Column Generation im Optimum des Kanten-LP? | ✅ Ja, in **allen 100 Netzen** für 2, 3, 4 und 5 Güter, im Distributionsnetz und im Streckennetz (Abweichung < 10⁻⁶). Gegenproben: das Pfad-LP mit **allen** aufgezählten Pfaden (Kleinstnetze) hat denselben Wert; mit den Preisen des letzten Masters hat **jeder** aufgezählte Pfad reduzierte Kosten ≥ 0 (Dualitätszertifikat unabhängig vom Pricing); komplementärer Schlupf (Preis > 0 nur auf ausgelasteten Kanten); die Farley-Schranke liegt für beliebige nichtnegative Preise unter dem Optimum. |
| Wie viele Spalten? | Distributionsnetz (drei Güter): 103 Variablen im Kanten-LP, im Mittel **52,1 mögliche Pfade** (17 bis 111), etwa **28 Spalten**, etwa 21 mit Fluss – die Column Generation braucht dort etwa die Hälfte aller Pfade. Streckennetz (vier Güter): 252 Variablen, im Mittel **494 mögliche Pfade** (30 bis 2 666), etwa **14 Spalten**, etwa 6 mit Fluss. |
| Wann explodieren die Pfade? | ✅ Auf vollen Gittern (drei Güter, 5 feste Netze je Größe, exakt gezählt): 3 × 3 **28**, 4 × 3 **74**, 5 × 4 **1 768**, 6 × 4 **8 725**, 6 × 5 **142 473** Pfade gegen 90 / 120 / 204 / 246 / 312 Variablen – die Spalten bleiben bei etwa 10 bis 16, etwa 6 tragen Fluss. |
| Wie viele Runden? | Distributionsnetz etwa **11** (2 / 3 / 4 / 5 Güter: etwa 11,1 / 11,4 / 10,9 / 10,3), Streckennetz etwa **4 bis 5** (etwa 4,3 / 4,5 / 4,9 / 5,2); Beispielnetz (Seed 155) etwa 14 Runden mit etwa 31 Spalten. Die Runden wachsen also nicht mit der Zahl der Güter, die Spalten schon. |
| Was liefert die erste Runde? | Nach dem ersten Pricing (jedes Gut allein, ohne Preise) liefert der Master im Mittel erst etwa **9,8 von 64,3** Einheiten des Optimums (Beispielnetz: 9 von 67). |
| Gibt es ein Tailing-off? | ❌ Nein: die Lücke zwischen Master (obere) und Farley-Schranke (untere) ist erst spät klein: **5 % nach etwa 87 % der Runden** (9,9 von 11,4), 1 % nach 88 %, 0,1 % nach 97 %. Bis dahin steht in der Schranke die volle Nachfrage mal $M$. |
| Eine Spalte oder eine je Gut? | Der beste Pfad **je Gut** und Runde: etwa 11,4 Runden; nur der **insgesamt beste**: etwa 26,3 (2,3-fach) mit kaum weniger Spalten (26 gegen 28). |
| Hilft ein Start aus dem Nacheinander-Fahren? | ✅ Ja: etwa **5,5 Runden statt 11,4**, gleich viele Spalten; die Simplex-Iterationen bleiben (etwa 82 gegen 81). Beispielnetz: etwa 6 Runden statt 14, die erste Runde liefert schon die 67 Einheiten des Nacheinander-Fahrens. |
| Hilft die Preisglättung? | ❌ Nein: α = 0,5 / 0,8: etwa 11,8 / 12,3 Runden gegen 11,4, dazu etwa doppelt so viele angesehene Kanten im Pricing (1 657 / 1 725 gegen 847); das geglättete Pricing greift nur selten ins Leere (im Mittel 0,02 bis 0,03 Fehlgriffe je Netz). Im Streckennetz gleich (5,0 gegen 4,9 Runden). |
| Ist die Negativkontrolle nötig? | ✅ Ohne die Preise der Gut-Obergrenzen ($\mu$: Werks- und Nachfragekanten je Gut) im Pricing endet die Column Generation in **0 von 100** Distributionsnetzen im Optimum (nach etwa 1,3 Runden, sie schlägt nur bekannte Pfade vor), im Streckennetz in etwa 20 %. Beispielnetz: etwa 17 statt 67 Einheiten. |
| Braucht sie weniger Simplex-Iterationen als das Kanten-LP? | ❌/✅ **Kommt drauf an:** im Distributionsnetz mehr (etwa 81 gegen 23), im kleinen Streckennetz weniger (etwa 25 gegen 74). Auf vollen Gittern mit fünf Gütern (6 feste Netze je Größe): 5 × 4 etwa 57 gegen 117 (**weniger**), ab 8 × 6 mehr (etwa 500 gegen 238), 16 × 10 etwa 2 650 gegen 730 – die Runden wachsen mit der Größe (etwa 6 auf 34), und scipy löst jeden Master neu. |
| Und in Sekunden? | ❌ In jeder gemessenen Größe langsamer als ein HiGHS-Lauf auf dem Kanten-LP (etwa 4- bis 5-fach, nur zur Information: Python-Pricing und ein scipy-Aufruf je Runde). Die Spalten sind trotzdem ein Bruchteil der Variablen: etwa 6 % bei 5 × 4, etwa 4 % bei 16 × 10. |
| Lehrnetze | **Preis-Wende:** 2 Runden; in Runde 1 fahren beide Güter direkt (nur 1 Einheit geht durch), der Preis der Direktstrecke liegt nahe $M$; in Runde 2 lohnt der Umweg und der Preis ist genau der Mehrpreis des Umwegs (**3** = 4 − 1); Kosten 5. **Frachtnetz mit Bruch:** das LP liefert 1,5 Einheiten für 24 (gebrochene Pfadmengen), ganzzahlig ginge nur 1 – die Column Generation liefert genau das LP-Optimum. |
| Beispielnetze | Distributionsnetz (Seed 155): 67 von 76 Einheiten für 1548, 79 mögliche Pfade, 5 bindende Kanten. Streckennetz (Seed 7): 7 von 12 Einheiten für 105, 242 mögliche Pfade, 256 Variablen, etwa 16 Spalten (etwa 7 mit Fluss) in etwa 5 Runden. Dichtes Gitter 8 × 5 (fünf Güter): 10 von 11 Einheiten für 239, 720 Variablen, mindestens 28 000 mögliche Pfade, etwa 32 Spalten (etwa 9 mit Fluss). |

## Was nicht funktioniert hat / Vorab-Hypothesen

Vor dem Schreiben der Texte wurde über die 100 Netze gemessen; einige Vermutungen aus dem Plan stimmten nicht oder nur teilweise:

- **„Column Generation gewinnt ab einer Größe gegen das Kanten-LP.“** Im gemessenen Bereich (bis 16 × 10 mit fünf Gütern, 2 990 Variablen) nicht: bei den Simplex-Iterationen gewinnt sie nur bei kleinen Gittern (5 × 4), verliert ab 8 × 6, und in Sekunden verliert sie immer. Der Grund ist nicht die Spaltenzahl (die bleibt bei 4 bis 6 % der Variablen), sondern die Zahl der Runden, die mit der Größe wächst, und dass scipy jeden Master ohne Warmstart neu löst. Der Kreuzungspunkt, den der Plan erwartete, liegt jenseits dessen, was die Demo rechnet.
- **„Die Spalten sind viel weniger als die möglichen Pfade.“** Nur auf tiefen Netzen: im dreistufigen Distributionsnetz braucht die Column Generation etwa die Hälfte aller Pfade (28 von 52), im Gitter dagegen 14 von 494 – und bei 6 × 5 etwa 14 von 142 473.
- **„Die Lücke schließt sich mit Tailing-off.“** Nein: sie schließt sich spät und dann schnell (5 % erst nach etwa 87 % der Runden). Die Farley-Schranke ist mit der Belohnung $M$ im Zielwert erst brauchbar, wenn jedes Gut einen Pfad hat.
- **„Preisglättung (Wentges) stabilisiert die Preise und spart Runden.“** Nein, hier nicht: etwas mehr Runden und doppelt so viele angesehene Kanten (das Pricing läuft zweimal je Runde).
- **„Kosten plus die Preise der gemeinsamen Kanten genügen im Pricing.“** Nein: auch die Preise der gutspezifischen Obergrenzen ($\mu$ auf den Werks- und Nachfragekanten) gehören in die Kantenlänge; ohne sie hält das Verfahren mit falschem Wert an (Negativkontrolle).
- **Fund beim Bau (Modell):** Mit der Belohnung $M$ je Einheit im Zielwert sind die Preise nahe $M$, wo eine Kante die Lieferung selbst begrenzt, und klein, wo sie nur verteuert. Die Karte zeigt beides; die Bildunterschrift erklärt es.
- **Fund beim Bau (Streamlit):** Ein Wert, der im Session-State eines Reglers in einem Lauf **ohne** diesen Regler gesetzt wird, erscheint später als Mindestwert im Regler, während die App mit dem gesetzten Wert rechnet (AppTest zeigt es nicht, nur der Browser). Netzabhängig ausgeblendete Regler werden deshalb erst unmittelbar vor dem Zeichnen initialisiert.
- **Abweichungen vom Plan:** Port 8682; kein PDF-Export; Farley-Schranke statt Lagrange-Schranke für die Konvergenzkurve; die Experimente „Preisstabilisierung“, „Start und Spalten je Runde“ und die Negativkontrolle sind eine Tabelle „Welche Option hilft?“; Sekunden nur zur Information neben den Iterationen; das Streckennetz hat eigene Regler statt geteilter Werke/Verteilzentren.

## Was die Demo zeigt

- **Rundenregler:** Runde 0 (Master leer oder aus dem Nacheinander-Fahren gestartet) bis zum Optimum. Links das Netz der Runde (je Gut eine Farbe, Breite ~ Fluss im Master, orange Unterlage mit dem **Preis λ** an den Kanten mit positivem Schattenpreis, schwarz gestrichelt die vom Pricing gefundenen und aufgenommenen Pfade; im Streckennetz Start (Raute) und Ziel (Stern) je Gut), rechts der **Wert −Z/M** (Master steigt, Farley-Schranke sinkt, gestrichelt das Kanten-LP) und die **Spalten je Runde** gegen die Variablen des Kanten-LP und alle möglichen Pfade. ▶️ spielt alle Runden ab; darunter die Tabelle der Pfade im Master (Menge, seit welcher Runde).
- **Was spart die Column Generation?** Wert (= Kanten-LP), Runden, Spalten, Iterationen; ein Urteil (optimal / angehalten bei Lücke / falscher Wert / nichts kommt an) und die Verteilung über 100 feste Netze (Histogramm der Runden mit der Marke „Ihre Ziehung“).
- **Experimente (🔬):** wie schnell sich die Lücke schließt (immer sichtbar), welche Option hilft (auf Abruf), Spalten gegen mögliche Pfade auf Gittern von 3 × 3 bis 6 × 5 (auf Abruf, exakte Pfadzählung), wann die Column Generation gegen das Kanten-LP gewinnt (auf Abruf, 5 × 4 bis 16 × 10).
- **Optionen:** ein Pfad je Gut oder nur der beste, Start leer oder aus dem Nacheinander-Fahren, Glättung α (aus / 0,5 / 0,8), Abbruch bei Lücke (bis zum Optimum / 1 % / 5 %), Negativkontrolle.
- **Feste Netze** (Preis-Wende, Frachtnetz mit Bruch) und zufällige Distributions- und Streckennetze; **Wo die Annahmen enden:** Branch-and-Price, Garg–Könemann, Pfadbeschränkungen, Fixkosten, Warmstart, Zeit.

## Modell und Verfahren

- **Netz:** wie im Vorgänger (Quelle S, Werke, Verteilzentren als Eingang und Ausgang gespalten, Filialen, Senke T; Streckennetz: Gitter mit Spannbaum, beide Richtungen mit gleicher Kapazität und gleichen Kosten). Ganzzahlig, eigener Zufallsgenerator SplitMix64 statt `numpy.random`.
- **Master (Pfad-LP):** $x_p\ge 0$ je bekanntem Pfad; Zeilen: gemeinsame Kapazität je gemeinsamer Kante (Summe aller Pfade über sie), gutspezifische Obergrenze je (Gut, Kante) mit endlicher Grenze; Ziel: Kosten des Pfades minus $M$ je Einheit. HiGHS über `scipy.optimize.linprog`; Schattenpreise = negative Marginale.
- **Pricing:** je Gut Dijkstra mit Kantenlänge Kosten + $\lambda_e$ + $\mu_{k,e}$; reduzierte Kosten = Länge − $M$; Spalte lohnt bei < 0.
- **Schranke (Farley):** $z^\*\ge -\pi^\top b+\sum_k D_k\min(0,\bar c_k^{\min})$ mit $D_k$ = Gesamtnachfrage von Gut $k$; gilt für **beliebige** nichtnegative Preise (Test).
- **Aufwand:** Simplex-Iterationen aller Master-Läufe, angesehene Kanten im Pricing, Spalten; Sekunden nur zur Information.
- **Pfade zählen:** im dreistufigen Netz exakt per Zählung von hinten, im Gitter per Tiefensuche mit Deckel („mindestens“ bei Abbruch).

## Dateien

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Oberfläche |
| `mcg_constants.py` | Regler-Grenzen, Presets und Hilfetexte, feste Seed-Mengen |
| `mcg_presets.py` | Permalink, Preset- und Zufalls-Seed-Logik; Regler, die je nach Netz ausgeblendet sind, werden erst vor dem Zeichnen initialisiert (`seed_widget`) |
| `mcg_scenario.py`, `mcg_model.py` | Distributionsnetz mit eigenem Zufallsgenerator (Kopie); Güter, Kostenfaktoren, Frachtnetze, Streckennetz (`generate_grid`) und Preis-Netz (`preis_net`) |
| `mcg_cg.py` | Master, Dijkstra-Pricing, Farley-Schranke, Optionen (Spalten je Runde, Start, Glättung, Lücke, Negativkontrolle), Trace je Runde, Pfad-LP mit allen Pfaden als Gegenprobe |
| `mcg_paths.py` | Nachbarschaftslisten je Gut, Zählung und Aufzählung einfacher Pfade, Pfadzerlegung eines Kantenflusses |
| `mcg_edge_lp.py` | Kanten-LP und ganzzahliges Programm des Vorgängers (Kopie, Gegenprobe und Vergleichsbasis), Nacheinander-Fahren für den Start |
| `mcg_ssp.py`, `mcg_edmonds_karp.py` | Kopien der Vorgänger-Demos (Min-Cost-Flow je Gut), ohne Import, SSP durch einen Wache-Test bewacht |
| `mcg_evaluation.py` | Urteil, Lücke und Runden, Verteilungen, Optionen-, Pfad- und Größentabelle |
| `mcg_visualization.py` | Plotly-Abbildungen (Achsen gesperrt für Touch-Geräte; Kantenbeschriftungen als Annotationen mit heller Hinterlegung; Hover über unsichtbare Marker entlang der Kanten) |
| `tests/` | Algorithmus (Kanten-LP, Pfad-LP mit allen Pfaden, Dualitätszertifikat über alle Pfade, Schlupf, Schranken, Optionen, Negativkontrolle, Pfadzählung und -zerlegung, Lehrnetze), Szenario und Auswertung, Presets, belegte Zahlen, AppTest-Rauchtests |

Alle Daten sind synthetisch; die Laufzeit braucht numpy, pandas, plotly, streamlit und **scipy** (der LP-Löser HiGHS), `networkx` ist ein reines Testorakel.

## Lokal starten

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\streamlit run app.py
```

## Tests ausführen

```bash
venv\Scripts\pip install -r requirements-dev.txt
venv\Scripts\python -m pytest tests -v
```

Die Netze sind ganzzahlig; die Zielwerte der LPs werden mit Toleranz verglichen (nicht die Basis des Simplex), Runden und Iterationen nur mit Bändern. Ein Lauf dauert einige Minuten (Verteilungen über 100 Netze, Experimente).
Die CI (`.github/workflows/tests.yml`) läuft auf Ubuntu mit Python 3.12, bei jedem Push und wöchentlich mit den jeweils neuesten Bibliotheksversionen.
