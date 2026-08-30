game-name-pusoydos = Pusoy Dos

pusoydos-set-min-entry = Minimum Entry Coins: { $count }
pusoydos-enter-min-entry = Enter minimum entry coins (min: 100, max: 100000):
pusoydos-option-changed-min-entry = Minimum entry coins set to { $count }.

pusoydos-set-turn-timer = Turn Timer: { $choice }
pusoydos-select-turn-timer = Select turn timer duration:
pusoydos-option-changed-turn-timer = Turn timer set to { $choice }.

pusoydos-timer-10 = 10 Seconds
pusoydos-timer-15 = 15 Seconds
pusoydos-timer-20 = 20 Seconds
pusoydos-timer-30 = 30 Seconds
pusoydos-timer-45 = 45 Seconds
pusoydos-timer-60 = 60 Seconds
pusoydos-timer-90 = 90 Seconds
pusoydos-timer-unlimited = Unlimited

pusoydos-set-penalty = Penalty Multiplier: { $count }
pusoydos-enter-penalty = Enter penalty multiplier (min: 1, max: 500):
pusoydos-option-changed-penalty = Penalty multiplier set to { $count }.

pusoydos-game-start = Starting Pusoy Dos!
pusoydos-new-hand = Round { $round }
pusoydos-dealt = Dealt 13 cards: { $cards }.

pusoydos-card-unselected = { $card }
pusoydos-card-selected = { $card } (selected)

pusoydos-play-none = Select cards to play.
pusoydos-play-invalid = Invalid combination.
pusoydos-play-combo = Play { $combo }

pusoydos-pass = Pass
pusoydos-check-trick = Check trick
pusoydos-read-hand = Read hand
pusoydos-check-turn-timer = Check turn timer
pusoydos-timer-disabled = The turn timer is disabled.
pusoydos-timer-remaining = { $seconds } seconds remaining.

pusoydos-error-no-cards = You have not selected any cards.
pusoydos-error-invalid-combo = The selected cards do not form a valid combination.
pusoydos-error-first-turn-3c = You must include the 3 of Clubs in the first play.
pusoydos-error-wrong-length = You must play exactly { $count } cards to beat the current trick.
pusoydos-error-lower-combo = Your combination is lower than the current trick.
pusoydos-error-must-play = You cannot pass when starting a new trick.

pusoydos-player-plays-single = { $player } plays { $card }.
pusoydos-player-plays-combo = { $player } plays a { $combo } of { $cards }.
pusoydos-player-passes = { $player } passes.
pusoydos-trick-won = { $player } won the trick.

pusoydos-trick-empty = The trick is empty.
pusoydos-trick-status = { $player } played a { $combo } of { $cards }.
pusoydos-your-hand = Your hand: { $cards }.
pusoydos-read-card-counts = Read card counts
pusoydos-card-count-line = { $player } has { $count } cards

pusoydos-combo-single = Single
pusoydos-combo-pair = Pair
pusoydos-combo-three_of_a_kind = Three of a Kind
pusoydos-combo-straight = Straight
pusoydos-combo-flush = Flush
pusoydos-combo-full_house = Full House
pusoydos-combo-four_of_a_kind = Four of a Kind
pusoydos-combo-straight_flush = Straight Flush

pusoydos-hand-winner = { $player } won the round and earned { $amount } coins!
pusoydos-hand-loser = { $player } lost { $amount } coins.
pusoydos-game-over = The game is over! { $player } is the ultimate winner!
pusoydos-line-format = { $rank }. { $player }: { $score } coins

pusoydos-cards-exchanged = Karten getauscht.
pusoydos-checking-instant-wins = Prüfe auf Instant-Gewinn-Hände ...
# Namen von Instant-Gewinn-Händen
pusoydos-combo-dragon = Drache
pusoydos-combo-four_twos = Vier 2en
pusoydos-combo-six_pairs = Sechs Paare
pusoydos-confirm-pass = Benutze die Pass-Aktion erneut, um zu bestätigen.
pusoydos-desc-allow-2-in-straights = Ob die 2 in Straights verwendet werden darf (z. B. A-2-3-4-5).
pusoydos-desc-card-passing = Ob Karten nach dem Austeilen zwischen Gewinnern und Verlierern getauscht werden.
pusoydos-desc-game-mode = Elimination: Gewinne Runden, um rauszukommen, der letzte Spieler ist der Verlierer. Losses: Letztplatzierte sammeln Strafen, wer zuerst das Limit erreicht, verliert. Points: Der Rundensieger kassiert Strafpunkte von den Verlierern, wer zuerst das Ziel erreicht, gewinnt. Points Elimination: Verlierer sammeln ihre eigenen Strafpunkte, erreiche das Limit und du bist raus, der letzte verbleibende Spieler gewinnt.
pusoydos-desc-instant-wins = Ob besondere ausgeteilte Hände (Drache, Vier 2en, Sechs Paare) die Runde sofort gewinnen.
pusoydos-desc-losses-to-lose = Wie viele Letztplatzierungen, bevor ein Spieler das Spiel verliert.
pusoydos-desc-penalty-per-two = Ob jede verbleibende 2 auf der Hand die Strafe verdoppelt.
pusoydos-desc-penalty-tier = Wie aggressiv verbleibende Karten am Ende einer Runde bestraft werden.
pusoydos-desc-rounds-to-win = Wie viele Runden ein Spieler gewinnen muss, bevor er als Sieger eliminiert wird.
pusoydos-desc-target-score = Die Punktzahl, die ein Spieler erreichen muss, um das Spiel zu gewinnen (Punktemodus) oder eliminiert zu werden (Punkte-Eliminationsmodus).
pusoydos-desc-turn-timer = Zeitlimit pro Zug. Auf Unbegrenzt setzen, um kein Limit zu haben.
pusoydos-enter-losses-to-lose = Zum Verlieren nötige Niederlagen eingeben (min: 1, max: 10):
pusoydos-enter-rounds-to-win = Zum Eliminieren nötige Runden eingeben (min: 1, max: 10):
pusoydos-enter-target-score = Zielpunktzahl eingeben (min: 10, max: 10000):
pusoydos-error-full-passing-players = Volles Kartentauschen erfordert genau 2 oder 4 Spieler.
pusoydos-first-player = { $player } hat das Kreuz-3 und beginnt.
pusoydos-first-player-lowest = { $player } hat die niedrigste Karte und beginnt.
pusoydos-game-over-losses = Das Spiel ist vorbei! { $player } verliert mit { $count } Niederlagen!
pusoydos-game-over-points = Das Spiel ist vorbei! { $player } gewinnt mit { $score } Punkten!
# Instant-Gewinne
pusoydos-instant-win-dragon = { $player } hat einen Drachen (13-Karten-Straight)! Sofortiger Gewinn!
pusoydos-instant-win-four-twos = { $player } hat alle vier 2en! Sofortiger Gewinn!
pusoydos-instant-win-six-pairs = { $player } hat sechs Paare! Sofortiger Gewinn!
pusoydos-key-counts = Kartenzahlen
pusoydos-key-hand = Deine Hand lesen
pusoydos-key-pass = Passen
# Tastenbelegungsbeschriftungen
pusoydos-key-play = Ausgewählte Karten spielen
pusoydos-key-timer = Zug-Timer
pusoydos-key-trick = Aktuellen Stich prüfen
pusoydos-last-player = { $player } ist der letzte verbleibende Spieler. Spiel vorbei!
pusoydos-line-format-losses =
    { $rank }. { $player }: { $losses } { $losses ->
        [one] Niederlage
       *[other] Niederlagen
    }
pusoydos-line-format-wins =
    { $rank }. { $player }: { $wins } { $wins ->
        [one] Sieg
       *[other] Siege
    }
pusoydos-loser-gives =
    { $loser } gibt { $count ->
        [one] seine höchste Karte
       *[other] seine { $count } höchsten Karten
    } an { $winner }.
pusoydos-losses-game-over = { $player } erreicht { $count } Niederlagen und verliert das Spiel!
pusoydos-mode-elimination = Elimination
pusoydos-mode-losses = Niederlagen
pusoydos-mode-points = Punkte
pusoydos-mode-points-elimination = Punkte-Elimination
pusoydos-no-instant-wins = Keine sofortigen Gewinne in dieser Runde.
pusoydos-one-card = { $player } hat noch eine Karte übrig!
pusoydos-option-changed-allow-2-in-straights = 2 in Straights erlaubt auf { $enabled } gesetzt.
pusoydos-option-changed-card-passing = Kartentausch auf { $choice } gesetzt.
pusoydos-option-changed-game-mode = Spielmodus auf { $choice } gesetzt.
pusoydos-option-changed-instant-wins = Sofortige Gewinne auf { $enabled } gesetzt.
pusoydos-option-changed-losses-to-lose = Niederlagen zum Verlieren auf { $count } gesetzt.
pusoydos-option-changed-penalty-per-two = Strafe pro 2 auf { $enabled } gesetzt.
pusoydos-option-changed-penalty-tier = Strafstufe auf { $choice } gesetzt.
pusoydos-option-changed-rounds-to-win = Runden zum Gewinnen auf { $count } gesetzt.
pusoydos-option-changed-target-score = Zielpunktzahl auf { $score } gesetzt.
pusoydos-passed-cards = Du hast { $cards } an { $recipient } gegeben.
pusoydos-passing-full = Voll (1./letzter tauscht 2, 2./3. tauscht 1)
pusoydos-passing-off = Aus
# Kartentausch
pusoydos-passing-phase = Phase des Kartentauschs.
pusoydos-passing-simple = Einfach (1. und letzter tauschen 1 Karte)
pusoydos-penalty-aggressive = Aggressiv (8-9: x2, 10-12: x3, 13: x4)
pusoydos-penalty-flat = Flach (1 Punkt pro Karte, kein Multiplikator)
pusoydos-penalty-standard = Standard (10+ Karten: x2, 13 Karten: x3)
# Punktemodus
pusoydos-penalty-summary = { $player } gewinnt die Runde: { $breakdown }. ({ $gained } diese Runde, { $total } insgesamt.)
# Eliminationsmodus
pusoydos-player-eliminated = { $player } gewinnt { $count } Runden und ist raus! Gut gespielt.
pusoydos-player-goes-out = { $player } ist raus!
pusoydos-players-remaining =
    { $count } { $count ->
        [one] Spieler
       *[other] Spieler
    } verbleibend.
pusoydos-points-elim-eliminated = { $player } erreicht { $score } Punkte und ist eliminiert!
# Punkte-Eliminationsmodus
pusoydos-points-elim-penalty = { $player } erhält { $points } Punkte. ({ $total } insgesamt.)
pusoydos-points-elim-winner = { $player } ist der letzte verbleibende Spieler. { $player } gewinnt!
pusoydos-points-winner = { $player } erreicht { $score } Punkte und gewinnt das Spiel!
pusoydos-received-cards = Du hast { $cards } von { $sender } erhalten.
# Niederlagenmodus
pusoydos-round-loser =
    { $player } wird Letzter und kassiert eine Niederlage! ({ $count } { $count ->
        [one] Niederlage
       *[other] Niederlagen
    } insgesamt.)
pusoydos-round-winner = { $player } gewinnt die Runde!
pusoydos-select-card-passing = Kartentausch-Modus auswählen:
pusoydos-select-cards-to-give =
    Wähle { $count ->
        [one] 1 Karte
       *[other] { $count } Karten
    }, um sie an { $recipient } zurückzugeben:
pusoydos-select-game-mode = Spielmodus auswählen:
pusoydos-select-penalty-tier = Strafstufe auswählen:
pusoydos-set-allow-2-in-straights = 2 in Straights erlaubt: { $enabled }
pusoydos-set-card-passing = Kartentausch: { $choice }
pusoydos-set-game-mode = Spielmodus: { $choice }
pusoydos-set-instant-wins = Sofortige Gewinne: { $enabled }
pusoydos-set-losses-to-lose = Niederlagen zum Verlieren: { $count }
pusoydos-set-penalty-per-two = Strafe pro 2: { $enabled }
pusoydos-set-penalty-tier = Strafstufe: { $choice }
pusoydos-set-rounds-to-win = Runden zum Gewinnen: { $count }
pusoydos-set-target-score = Zielpunktzahl: { $score }
pusoydos-winner-gives-back =
    { $winner } gibt { $count ->
        [one] eine Karte
       *[other] { $count } Karten
    } an { $loser } zurück.

