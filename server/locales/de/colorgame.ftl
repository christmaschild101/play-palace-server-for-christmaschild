game-name-colorgame = Farbenspiel

colorgame-set-starting-bankroll = Startkasse: { $amount }
colorgame-enter-starting-bankroll = Gib das Startkapital ein:
colorgame-option-changed-starting-bankroll = Startkasse auf { $amount } festgelegt.

colorgame-set-minimum-bet = Mindesteinsatz: { $amount }
colorgame-enter-minimum-bet = Gib den Mindesteinsatz ein:
colorgame-option-changed-minimum-bet = Mindesteinsatz auf { $amount } festgelegt.

colorgame-set-maximum-total-bet = Maximaler Gesamteinsatz pro Runde: { $amount }
colorgame-enter-maximum-total-bet = Gib den maximalen Gesamteinsatz pro Runde ein:
colorgame-option-changed-maximum-total-bet = Maximaler Gesamteinsatz pro Runde auf { $amount } festgelegt.

colorgame-set-betting-timer = Wett-Timer: { $seconds } Sekunden
colorgame-enter-betting-timer = Gib den Wett-Timer in Sekunden ein:
colorgame-option-changed-betting-timer = Wett-Timer auf { $seconds } Sekunden festgelegt.

colorgame-set-round-limit = Rundenlimit: { $count }
colorgame-enter-round-limit = Gib das Rundenlimit ein:
colorgame-option-changed-round-limit = Rundenlimit auf { $count } festgelegt.

colorgame-set-win-condition = Siegbedingung: { $mode }
colorgame-select-win-condition = Wähle die Siegbedingung:
colorgame-option-changed-win-condition = Siegbedingung auf { $mode } festgelegt.
colorgame-win-condition-last-player = Letzter verbleibender Spieler
colorgame-win-condition-highest-bankroll = Höchste Kasse beim Rundenlimit

colorgame-color-red = rot
colorgame-color-blue = blau
colorgame-color-yellow = gelb
colorgame-color-green = grün
colorgame-color-white = weiß
colorgame-color-orange = orange

colorgame-game-start = Das Farbenspiel beginnt. Spieler: { $players }.
colorgame-round-start = Runde { $round } von { $limit }. Wetten sind für { $seconds } Sekunden offen.
colorgame-roll-result = Die Würfel zeigen { $colors }.
colorgame-player-locked-bets = { $player } legt { $total } Chips fest.
colorgame-player-sits-out = { $player } setzt diese Runde aus.
colorgame-player-sat-out = { $player } setzte aus und bleibt bei { $bankroll } Chips.
colorgame-player-won = { $player } gewinnt { $amount } Chips und steigt auf { $bankroll }.
colorgame-player-even = { $player } spielt unentschieden und bleibt bei { $bankroll } Chips.
colorgame-player-lost = { $player } verliert { $amount } Chips und fällt auf { $bankroll }.

colorgame-set-bet-color = { $color }-Einsatz festlegen: { $amount }
colorgame-clear-bets = Einsätze löschen
colorgame-confirm-bets = Einsätze festlegen ({ $total })
colorgame-confirm-sit-out = Kein Einsatz festlegen
colorgame-check-status = Status prüfen
colorgame-check-bets = Einsätze prüfen
colorgame-check-last-roll = Letzten Wurf prüfen

colorgame-enter-bet-amount = Gib den Einsatzbetrag für diese Farbe ein. Gib 0 ein, um ihn zu löschen.
colorgame-invalid-bet-amount = Gib einen gültigen ganzen Einsatzbetrag ein.
colorgame-bet-below-minimum = Jeder Farbeinsatz muss mindestens { $amount } betragen.
colorgame-bet-exceeds-bankroll = Deine Gesamteinsätze dürfen { $amount } nicht überschreiten.
colorgame-bet-updated = { $color } ist jetzt auf { $amount } festgelegt. Diese Runde insgesamt fällig: { $total }.
colorgame-bets-cleared = Alle deine Einsätze wurden gelöscht.
colorgame-bankrupt = Du hast keine Chips mehr.
colorgame-bets-already-locked = Deine Einsätze sind für diese Runde bereits festgelegt.
colorgame-no-bets-placed = Du hast keine Einsätze platziert.

colorgame-no-bets = kein Einsatz
colorgame-bet-entry = { $color } { $amount }
colorgame-bets-header = Aktuelle Einsätze:
colorgame-bets-line = { $player }: { $bets }. Insgesamt { $total }. { $locked }.
colorgame-bets-open-status = Einsätze sind noch offen
colorgame-bets-locked-status = Einsätze sind festgelegt

colorgame-last-roll-none = Es wurde noch kein Wurf aufgezeichnet.
colorgame-last-roll-header = Letzter Wurf: { $colors }.
colorgame-last-roll-line = { $player }: { $bets }. Netto { $net }. Kasse { $bankroll }.

colorgame-status-betting = Wettphase. Runde { $round } von { $limit }. Noch { $seconds } Sekunden. Siegbedingung: { $win_mode }.
colorgame-status-rolling = Die Würfel rollen für Runde { $round } von { $limit }. Siegbedingung: { $win_mode }.
colorgame-status-resolving = Runde { $round } von { $limit } wird ausgewertet. Siegbedingung: { $win_mode }.
colorgame-status-bankroll = Deine Kasse beträgt { $bankroll }. Diese Runde hast du { $total } fällig. Dein Limit diese Runde ist { $cap }.
colorgame-status-bet-lock = Dein Wettstatus: { $state }.
colorgame-status-leader = Der aktuelle Führende ist { $player } mit { $bankroll } Chips.

colorgame-whose-turn-betting = Wettphase. Alle aktiven Spieler können handeln. Noch { $seconds } Sekunden.
colorgame-whose-turn-rolling = Die Würfel rollen gerade.
colorgame-whose-turn-resolving = Die Runde wird gerade ausgewertet.

colorgame-standings-header = Wertung:
colorgame-standing-live = noch dabei
colorgame-standing-bust = pleite
colorgame-score-line = { $rank }. { $player }: { $bankroll } Chips, { $profitable_rounds } gewinnbringende Runden, größter Gewinn { $biggest_win }, { $status }.

colorgame-error-max-bet-too-small = Der maximale Gesamteinsatz muss mindestens dem Mindesteinsatz entsprechen.
colorgame-error-max-bet-too-large = Der maximale Gesamteinsatz darf die Startkasse nicht überschreiten.