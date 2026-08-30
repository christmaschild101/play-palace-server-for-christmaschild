game-name-tienlen = Tien Len

tienlen-set-variant = Variante: { $choice }
tienlen-select-variant = Wähle die Tien-Len-Variante:
tienlen-option-changed-variant = Variante auf { $choice } festgelegt.

tienlen-set-match-length = Spiellänge: { $choice }
tienlen-select-match-length = Wähle die Spiellänge:
tienlen-option-changed-match-length = Spiellänge auf { $choice } festgelegt.

tienlen-set-turn-timer = Zug-Timer: { $choice }
tienlen-select-turn-timer = Wähle die Zug-Timer-Dauer:
tienlen-option-changed-turn-timer = Zug-Timer auf { $choice } festgelegt.

tienlen-variant-south = Südliches Tien Len
tienlen-variant-north = Nördliches Tien Len
tienlen-match-1 = Einzelhand
tienlen-match-3 = Best of 3
tienlen-match-5 = Best of 5

tienlen-timer-10 = 10 Sekunden
tienlen-timer-15 = 15 Sekunden
tienlen-timer-20 = 20 Sekunden
tienlen-timer-30 = 30 Sekunden
tienlen-timer-45 = 45 Sekunden
tienlen-timer-60 = 60 Sekunden
tienlen-timer-90 = 90 Sekunden
tienlen-timer-unlimited = Unbegrenzt

tienlen-game-start = Tien Len startet.
tienlen-new-hand = Hand { $round }.
tienlen-dealt = 13 Karten ausgeteilt: { $cards }.
tienlen-variant-status = Dieses Spiel läuft als { $variant }.

tienlen-card-unselected = { $card }
tienlen-card-selected = { $card } (ausgewählt)

tienlen-play-none = Wähle Karten zum Ausspielen.
tienlen-play-invalid = Ungültige Kombination.
tienlen-play-combo = { $combo } spielen

tienlen-pass = Passen
tienlen-check-trick = Stich prüfen
tienlen-read-hand = Hand lesen
tienlen-read-card-counts = Kartenzahl lesen
tienlen-check-variant = Variante prüfen
tienlen-check-turn-timer = Zug-Timer prüfen
tienlen-timer-disabled = Der Zug-Timer ist deaktiviert.
tienlen-timer-remaining = Noch { $seconds } Sekunden.

tienlen-error-no-cards = Du hast keine Karten ausgewählt.
tienlen-error-invalid-combo = Die ausgewählten Karten bilden keine gültige Kombination.
tienlen-error-first-turn-3s = Du musst das Pik-3 in den Eröffnungszug einbeziehen.
tienlen-error-pass-lock = Du hast bei diesem Stich bereits gepasst und musst auf den nächsten Stich warten.
tienlen-error-pass-lock-two = Du hast bei diesem Stich bereits gepasst. Du darfst nur mit einem legalen Schlag gegen die aktuellen 2en zurückkehren.
tienlen-error-wrong-length = Du musst genau { $count } Karten spielen, um den aktuellen Stich zu schlagen.
tienlen-error-must-match-type = Dein Zug muss dem Kombinationstyp des aktuellen Stichs entsprechen.
tienlen-error-structure-mismatch = Im nördlichen Tien Len muss dein Zug der erforderlichen Farbe- oder Farbstruktur des aktuellen Stichs entsprechen.
tienlen-error-lower-combo = Deine Kombination schlägt den aktuellen Stich nicht.
tienlen-error-must-play = Du kannst nicht passen, wenn du einen neuen Stich beginnst.
tienlen-error-cannot-finish-on-two = Im nördlichen Tien Len kannst du die Hand nicht mit 2en beenden oder nur 2en zurücklassen.
tienlen-error-cannot-lead-three-consecutive-pairs = Im südlichen Tien Len können drei aufeinanderfolgende Paare nicht zum Eröffnen eines Stichs verwendet werden.

tienlen-player-plays-single = { $player } spielt { $card }.
tienlen-player-plays-combo = { $player } spielt { $combo }: { $cards }.
tienlen-player-passes = { $player } passt.
tienlen-trick-empty = Der Stich ist leer.
tienlen-trick-status = { $player } führt mit { $combo }: { $cards }.
tienlen-your-hand = Deine Hand: { $cards }.
tienlen-card-count-line = { $player } hat { $count } Karten

tienlen-combo-single = einzelne
tienlen-combo-pair = Paar
tienlen-combo-triple = Drilling
tienlen-combo-four_of_a_kind = Vierling
tienlen-combo-straight = Straße
tienlen-combo-consecutive_pairs = aufeinanderfolgende Paare

tienlen-hand-winner = { $player } gewinnt die Hand. Sie haben nun { $wins } von { $target } Handsiegen.
tienlen-game-over = Das Spiel ist vorbei. { $player } gewinnt Tien Len.
tienlen-line-format = { $rank }. { $player }: { $score ->
    [one] 1 Handsiege
   *[other] { $score } Handsiege
}