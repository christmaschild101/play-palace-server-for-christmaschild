game-name-deadmansdeck = Dead Man's Deck

deadmansdeck-call-liar = Lügner rufen
deadmansdeck-play-selected = Ausgewählte Karten spielen
deadmansdeck-clear-selection = Auswahl löschen
deadmansdeck-read-hand = Hand lesen
deadmansdeck-read-table = Tisch lesen
deadmansdeck-read-revolvers = Revolver lesen
deadmansdeck-read-card-counts = Kartenzahl lesen

deadmansdeck-rank-ace = Ass
deadmansdeck-rank-ace-plural = Asse
deadmansdeck-rank-king = König
deadmansdeck-rank-king-plural = Könige
deadmansdeck-rank-queen = Dame
deadmansdeck-rank-queen-plural = Damen
deadmansdeck-rank-joker = Joker
deadmansdeck-rank-joker-plural = Joker
deadmansdeck-claim-text = { $count } { $rank }

deadmansdeck-card-label = { $card }
deadmansdeck-selected-card-label = Ausgewählt: { $card }
deadmansdeck-card-selected = { $card } ausgewählt.
deadmansdeck-card-unselected = { $card } abgewählt.
deadmansdeck-selection-cleared = Auswahl gelöscht.
deadmansdeck-card-not-found = Diese Karte ist nicht mehr verfügbar.
deadmansdeck-too-many-selected = Du kannst höchstens drei Karten beanspruchen.
deadmansdeck-select-card-first = Wähle zuerst ein bis drei Karten.
deadmansdeck-no-claim-to-challenge = Es gibt keinen Anspruch zum Anfechten.
deadmansdeck-cannot-challenge-self = Du kannst deinen eigenen Anspruch nicht anfechten.
deadmansdeck-action-sequence-running = Warte, bis die aktuelle Sequenz beendet ist.
deadmansdeck-action-eliminated = Du wurdest eliminiert.

deadmansdeck-prepare-revolver = Die Revolver werden vorbereitet.
deadmansdeck-round-start = Runde { $round }. Die Tischkarte ist { $target }.
deadmansdeck-turn-order = Zugreihenfolge diese Runde: { $order }.
deadmansdeck-your-hand = Deine Hand: { $cards }.
deadmansdeck-hand-empty = Deine Hand ist leer.
deadmansdeck-no-cards = keine Karten
deadmansdeck-player-skipped-no-cards = { $player } hat keine Karten und wird übersprungen.
deadmansdeck-player-out-of-cards = { $player } hat keine Karten mehr.
deadmansdeck-forced-challenge = { $player } muss anfechten, da die Runde nicht fortgesetzt werden kann.
deadmansdeck-player-claims = { $player } beansprucht { $claim }.
deadmansdeck-player-calls-liar = { $challenger } ruft { $accused } als Lügner.
deadmansdeck-forced-liar-call = { $challenger } ist gezwungen, { $accused } als Lügner zu rufen.
deadmansdeck-revealed-cards = { $player } deckte auf: { $cards }.
deadmansdeck-bluff-caught = Der Bluff wurde erwischt. { $accused } verliert die Anfechtung und muss ziehen.
deadmansdeck-truthful-claim = Der Anspruch war wahr. { $challenger } verliert die Anfechtung und muss ziehen.
deadmansdeck-roulette-start = { $player } stellt sich dem Revolver.
deadmansdeck-roulette-survived = Leere Kammer. { $player } überlebt. Sein nächster Zug hat ein Risiko von 1 zu { $remaining }.
deadmansdeck-player-eliminated = Die Waffe feuert. { $player } wurde eliminiert.
deadmansdeck-player-wins = { $player } ist der letzte verbleibende Spieler und gewinnt Dead Man's Deck.
deadmansdeck-no-winner = Es konnte kein Sieger ermittelt werden.
deadmansdeck-you-are-eliminated = Du wurdest aus diesem Spiel eliminiert.

deadmansdeck-table-round = Runde { $round }. Ziel: { $target }.
deadmansdeck-table-target-pending = noch nicht festgelegt
deadmansdeck-table-current-turn = Aktueller Zug: { $player }.
deadmansdeck-table-last-claim = Letzter Anspruch: { $player } beanspruchte { $claim }.
deadmansdeck-table-no-claim = Es gibt keinen aktiven Anspruch.
deadmansdeck-table-alive = Noch dabei: { $players }.
deadmansdeck-table-eliminated = Eliminiert: { $players }.

deadmansdeck-card-count-line = { $player }: { $count ->
    [one] 1 Karte
   *[other] { $count } Karten
} übrig.
deadmansdeck-card-count-eliminated = { $player }: eliminiert.

deadmansdeck-revolvers-header = Revolver-Status
deadmansdeck-revolver-status = { $player }: { $survived } leere Kammern benutzt; der nächste Zug ist 1 zu { $remaining }.
deadmansdeck-revolver-eliminated = { $player }: eliminiert.

deadmansdeck-results-header = Ergebnisse von Dead Man's Deck
deadmansdeck-results-winner = Sieger: { $player }.
deadmansdeck-results-survived = überlebt
deadmansdeck-results-eliminated = eliminiert
deadmansdeck-results-line = { $player }: { $status }, richtige Rufe { $correct }, erfolgreiche Bluffs { $bluffs }, Roulette-Überlebende { $survivals }.