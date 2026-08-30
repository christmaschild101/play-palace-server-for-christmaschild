game-name-deadmanspoker = Dead Man's Poker

deadmanspoker-call = Mitgehen
deadmanspoker-match-all-in = All-in mitgehen
deadmanspoker-fold = Aufgeben
deadmanspoker-coward-fold = Feiglings-Fold
deadmanspoker-switch-card = Karte wechseln
deadmanspoker-all-in = All-in
deadmanspoker-read-hand = Hand lesen
deadmanspoker-read-community-cards = Gemeinschaftskarten lesen
deadmanspoker-read-hand-value = Handstärke lesen
deadmanspoker-read-table = Tisch lesen
deadmanspoker-read-card-counts = Kartenzahl lesen
deadmanspoker-read-revolvers = Revolver lesen

deadmanspoker-action-sequence-running = Warte, bis die aktuelle Sequenz beendet ist.
deadmanspoker-action-eliminated = Du wurdest eliminiert.
deadmanspoker-action-folded = Du bist aus dieser Hand raus.
deadmanspoker-not-decision-phase = Das kannst du in dieser Phase nicht tun.
deadmanspoker-max-bullets = Du hast bereits die maximale Anzahl an Kugeln fällig.
deadmanspoker-no-opponents = Es gibt keinen Gegner mehr in dieser Hand.
deadmanspoker-already-matched-all-in = Du bist dem All-in bereits mitgegangen.
deadmanspoker-coward-used = Du hast den Feiglings-Fold in diesem Match bereits benutzt.
deadmanspoker-coward-first-decision-only = Der Feiglings-Fold ist nur bei deiner ersten Entscheidung einer Hand verfügbar.
deadmanspoker-fold-first-decision-use-coward = Der normale Fold ist bei deiner ersten Entscheidung mit einer Kugel nicht verfügbar. Nur der Feiglings-Fold kann zu diesem Zeitpunkt ausscheiden.
deadmanspoker-switch-not-now = Du kannst gerade keine Karte wechseln.
deadmanspoker-switch-used = Du hast in diesem Match bereits eine Karte gewechselt.
deadmanspoker-switch-too-late = Es ist zu spät, eine Karte zu wechseln.
deadmanspoker-switch-no-cards = Du hast keine private Karte zum Wechseln.
deadmanspoker-switch-no-deck = Das Deck hat nicht genügend Ersatzkarten.
deadmanspoker-switch-choice-missing = Diese Ersatzkarte ist nicht mehr verfügbar.

deadmanspoker-match-start = Dead Man's Poker beginnt. Jede Kugel auf dem Tisch ist eine Wette mit deinem Leben im Hintergrund.
deadmanspoker-hand-start = Hand { $hand }. Jeder Überlebende setzt die erste Kugel.
deadmanspoker-community-arrives = Fünf Gemeinschaftskarten werden verdeckt ausgelegt.
deadmanspoker-your-hand = Deine privaten Karten: { $cards }.
deadmanspoker-hand-empty = Deine Hand ist leer.
deadmanspoker-round-stage = Wettrunde { $round_stage }.
deadmanspoker-community-revealed = Gemeinschaftskarten aufgedeckt: { $cards }. Tisch: { $table }.
deadmanspoker-player-calls = { $player } geht mit und legt { $added ->
    [one] 1 Kugel
   *[other] { $added } Kugeln
} auf den Tisch. Insgesamt fällig: { $total }.
deadmanspoker-player-matches-all-in = { $player } geht dem All-in mit { $added ->
    [one] 1 Kugel
   *[other] { $added } Kugeln
} mit. Insgesamt fällig: { $total }.
deadmanspoker-player-all-in = { $player } geht all-in und legt { $added ->
    [one] 1 Kugel
   *[other] { $added } Kugeln
} auf den Tisch. Insgesamt fällig: { $total }.
deadmanspoker-player-folds = { $player } gibt auf und muss sich mit { $bullets ->
    [one] 1 Kugel
   *[other] { $bullets } Kugeln
} dem Revolver stellen.
deadmanspoker-player-coward-folds = { $player } benutzt den Feiglings-Fold und stellt sich dem Revolver mit 1 Kugel.
deadmanspoker-switch-select-card = Wähle die private Karte zum Wechseln.
deadmanspoker-switch-card-option = { $card } wechseln
deadmanspoker-switch-candidates = Ersatzoptionen: { $cards }.
deadmanspoker-choose-switch-placeholder = Ersatz { $index }
deadmanspoker-choose-switch-card = { $card } wählen
deadmanspoker-player-switches = { $player } wechselt eine private Karte und legt { $card } ab.
deadmanspoker-private-reveal = { $player } deckt { $cards } auf. Beste Hand: { $hand }.
deadmanspoker-showdown-winners = { $players } gewinnen das Showdown mit { $hand }.
deadmanspoker-showdown-tie-no-penalty = Das Showdown endet unentschieden. Niemand stellt sich diese Hand dem Revolver.
deadmanspoker-hand-winner = { $player } gewinnt die Hand ohne Widerstand.
deadmanspoker-hand-no-winner = Niemand gewinnt diese Hand.

deadmanspoker-roulette-start = Das Roulette beginnt für { $players }.
deadmanspoker-load-bullets = { $player } lädt { $bullets ->
    [one] 1 Kugel
   *[other] { $bullets } Kugeln
}.
deadmanspoker-roulette-survived = Leere Kammer. { $player } überlebt nach dem Risiko von { $bullets ->
    [one] 1 Kugel
   *[other] { $bullets } Kugeln
}.
deadmanspoker-player-eliminated = Die Waffe feuert. { $player } wird nach dem Risiko von { $bullets ->
    [one] 1 Kugel
   *[other] { $bullets } Kugeln
} eliminiert.
deadmanspoker-player-wins = { $player } ist der letzte Überlebende und gewinnt Dead Man's Poker.
deadmanspoker-no-winner = Es konnte kein Sieger ermittelt werden.
deadmanspoker-you-are-eliminated = Du wurdest aus diesem Spiel eliminiert.

deadmanspoker-table-hand = Hand { $hand }, Wettrunde { $round_stage }.
deadmanspoker-table-community = Gemeinschaft: { $cards }. Verdeckt: { $hidden }.
deadmanspoker-community-status = Gemeinschaftskarten: { $cards }. Verdeckt: { $hidden }.
deadmanspoker-table-turn = Aktueller Zug: { $player }.
deadmanspoker-table-no-turn = Kein Spieler hat derzeit den Zug.
deadmanspoker-table-player = { $player }: { $bullets ->
    [one] 1 Kugel
   *[other] { $bullets } Kugeln
} fällig, { $status }.
deadmanspoker-community-none = keine aufgedeckt
deadmanspoker-hidden-community = { $count ->
    [one] 1 verdeckte Karte
   *[other] { $count } verdeckte Karten
}
deadmanspoker-status-active = aktiv
deadmanspoker-status-folded = aufgegeben
deadmanspoker-status-eliminated = eliminiert
deadmanspoker-status-waiting = wartet

deadmanspoker-card-count-line = { $player }: { $count ->
    [one] 1 Karte
   *[other] { $count } Karten
}.
deadmanspoker-card-count-eliminated = { $player }: eliminiert.

deadmanspoker-revolvers-header = Revolver-Risiko
deadmanspoker-revolver-status = { $player }: { $bullets ->
    [one] 1 Kugel
   *[other] { $bullets } Kugeln
} fällig; { $risk }.
deadmanspoker-revolver-eliminated = { $player }: eliminiert.
deadmanspoker-risk-none = kein aktuelles Roulette-Risiko
deadmanspoker-risk-normal = Todeschance { $bullets } in 8
deadmanspoker-risk-eight = 95 Prozent Todeschance, 5 Prozent Gott-rette-Überleben

deadmanspoker-results-header = Ergebnisse von Dead Man's Poker
deadmanspoker-results-winner = Sieger: { $player }.
deadmanspoker-results-survived = überlebt
deadmanspoker-results-eliminated = eliminiert
deadmanspoker-results-line = { $player }: { $status }, gewonnene Hände { $hands }, gestartete All-ins { $allins }, Roulette-Überlebende { $survivals }, riskierte Kugeln { $bullets }.