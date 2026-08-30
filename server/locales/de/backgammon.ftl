# Backgammon localization

game-name-backgammon = Backgammon

# Game start
backgammon-game-started = { $red } plays Red, { $white } plays White.
backgammon-opening-roll = Opening roll: { $red } rolls { $red_die }, { $white } rolls { $white_die }.
backgammon-opening-tie = Both rolled { $die }, re-rolling.
backgammon-opening-winner = { $player } goes first with { $die1 } and { $die2 }.

# Dice
backgammon-roll = { $player } rolls { $die1 } and { $die2 }.

# No moves
backgammon-no-moves = { $player } has no legal moves.

# Move commentary (shorthand)
backgammon-move-normal = { $player }: { $src } to { $dest }, { $remain } { $count }.
backgammon-move-emptying = { $player }: Emptying { $src } to { $dest }, { $count }.
backgammon-move-hit = { $player }: { $src } to capture on { $dest }, { $remain }.
backgammon-move-bar = { $player }: Bar to { $dest }, { $count }.
backgammon-move-bar-hit = { $player }: Bar to capture on { $dest }, { $count }.
backgammon-move-bearoff = { $player }: Bearing off from { $src }, { $remain }.

# Doubling
backgammon-doubles = { $player } doubles to { $value }.
backgammon-accepts = { $player } accepts.
backgammon-drops = { $player } drops.
backgammon-accept = Accept
backgammon-drop = Drop

# Selection feedback
backgammon-selected-point = Selected point { $point }, { $count } checkers.
backgammon-selected-bar = Selected bar.
backgammon-deselected = Deselected.
backgammon-no-checkers-there = No checkers there.
backgammon-no-moves-from-here = No legal moves from here.
backgammon-must-enter-from-bar = Must enter from bar first.
backgammon-illegal-move = Illegal move.
backgammon-nothing-to-undo = Nothing to undo.
backgammon-undone = Move undone.

# Hints
backgammon-hint = { $player } asks for a hint: { $hint }
backgammon-hint-not-now = Hints are only available during the moving phase.
backgammon-hints-disabled = Hints are disabled. Enable them in game options.
backgammon-hint-unavailable = Hint engine not available.
backgammon-gnubg-fallback = GNUBG engine unavailable. Bot is using simple fallback.

# Info keybinds
backgammon-check-status = Status
backgammon-check-pip = Pip count
backgammon-check-score = Score
backgammon-check-dice = Dice
backgammon-status = Red bar: { $bar_red }. White bar: { $bar_white }. Red off: { $off_red }. White off: { $off_white }. Dice: { $dice }.
backgammon-dice = { $dice }
backgammon-dice-none = No dice.
backgammon-pip-count = Red pip count: { $red_pip }. White pip count: { $white_pip }.
backgammon-match-score = { $red } { $red_score }, { $white } { $white_score }. Match to { $match_length }. Cube: { $cube }.

# Scoring
backgammon-wins-game = { $player } wins { $points } point{ $points ->
    [one] {""}
    *[other] s
}.
backgammon-new-game = Starting game { $number }.
backgammon-match-winner = { $player } wins the match!
backgammon-crawford = Crawford game: no doubling this game.
backgammon-resigns = { $player } resigns.
backgammon-resign = Resign

# Difficulty levels
backgammon-difficulty-random = Random
backgammon-difficulty-simple = Simple
backgammon-difficulty-gnubg-0ply = GNUBG 0-ply
backgammon-difficulty-gnubg-1ply = GNUBG 1-ply
backgammon-difficulty-gnubg-2ply = GNUBG 2-ply
backgammon-difficulty-whackgammon = Whackgammon

# Options
backgammon-option-match-length = Match length: { $match_length }
backgammon-option-select-match-length = Set match length (1-25)
backgammon-option-changed-match-length = Match length set to { $match_length }.
backgammon-option-bot-difficulty = Bot difficulty: { $bot_difficulty }
backgammon-option-select-bot-difficulty = Select bot difficulty
backgammon-option-changed-bot-difficulty = Bot difficulty set to { $bot_difficulty }.
backgammon-option-verbose-commentary = Verbose commentary: { $verbose_commentary }
backgammon-option-changed-verbose-commentary = Verbose commentary set to { $verbose_commentary }.
backgammon-option-hints = Hints: { $hints_enabled }
backgammon-option-changed-hints = Hints set to { $hints_enabled }.

backgammon-bearoff-blocked = Du kannst nicht vom { $point }-Punkt abräumen, wenn du eine { $die } hast, weil Steine auf deinem { $blocking_point }-Punkt liegen.
backgammon-bearoff-no-die = Du kannst nicht vom { $point }-Punkt mit deinen verbleibenden Würfeln ({ $die }) abräumen.
backgammon-cannot-double = Du kannst gerade nicht verdoppeln.
backgammon-cannot-undo = Nichts rückgängig zu machen.
backgammon-check-cube = Würfel
backgammon-cube-hint = { $player } bittet um Würfeltipp: { $hint }
backgammon-cube-hint-not-now = Würfeltipps sind nur vor dem Würfeln oder beim Antworten auf ein Doppeln verfügbar.
backgammon-cube-hint-response =
    { $player } bittet um Würfeltipp: { $advice ->
        [take] Nehmen.
       *[drop] Ablegen.
    }
backgammon-cube-hints-disabled = Würfeltipps sind deaktiviert. Aktiviere sie in den Spieleinstellungen.
backgammon-cube-no-match = Kein Verdopplungswürfel in Einzelspielen.
backgammon-cube-status =
    Würfel auf { $value }. { $owner ->
        [center] In der Mitte, beide Spieler dürfen verdoppeln.
       *[other] Im Besitz von { $owner }.
    } { $can_double ->
        [yes] Verdoppeln ist jetzt möglich.
        [crawford] Dies ist ein Crawford-Spiel, kein Verdoppeln erlaubt.
       *[no] Verdoppeln ist gerade nicht möglich.
    }
backgammon-end-score = { $red } { $red_score } - { $white } { $white_score }. Spiel bis { $match_length }.
# Lokaler Tipp
backgammon-hint-bar = bar
backgammon-hint-off = aus
backgammon-label-cube-hint = Würfeltipp
# Aktionsbeschriftungen
backgammon-label-double = Doppeln
backgammon-label-hint = Tipp
backgammon-label-undo = Rückgängig
backgammon-move-emptying-hit = Leeren von { $src }, um auf { $dest } zu schlagen.
backgammon-not-doubling-phase = Kein Doppeln zum Antworten vorhanden.
backgammon-not-your-checkers = Das sind nicht deine Steine.
backgammon-option-changed-cube-hints = Würfeltipps auf { $cube_hints_enabled } gesetzt.
backgammon-option-cube-hints = Würfeltipps: { $cube_hints_enabled }
# Punktbeschriftungen
backgammon-point-empty = { $point }
backgammon-point-empty-selected = { $point } ausgewählt
backgammon-point-occupied = { $point } { $color }, { $count }
backgammon-point-occupied-selected = { $point } { $color }, { $count } ausgewählt
backgammon-verbose-move-bar =
    { $is_self ->
        [yes] Du ziehst vom Brett auf Punkt { $dest }.
       *[no] { $player } zieht vom Brett auf Punkt { $dest }.
    } { $dest_count } jetzt auf Punkt { $dest }.
backgammon-verbose-move-bar-hit =
    { $is_self ->
        [yes] Du ziehst vom Brett, um { $opponent }s Stein auf Punkt { $dest } zu schlagen.
        [spectator] { $player } zieht vom Brett, um { $opponent }s Stein auf Punkt { $dest } zu schlagen.
       *[no] { $player } zieht vom Brett, um deinen Stein auf Punkt { $dest } zu schlagen.
    }
backgammon-verbose-move-bearoff =
    { $is_self ->
        [yes] Du räumst von Punkt { $src } ab.
       *[no] { $player } räumt von Punkt { $src } ab.
    } { $src_count ->
        [0] Punkt { $src } ist jetzt leer.
       *[other] { $src_count } verbleiben auf Punkt { $src }.
    }
backgammon-verbose-move-hit =
    { $is_self ->
        [yes] Du bewegst einen Stein von Punkt { $src }, um { $opponent }s Stein auf Punkt { $dest } zu schlagen.
        [spectator] { $player } bewegt einen Stein von Punkt { $src }, um { $opponent }s Stein auf Punkt { $dest } zu schlagen.
       *[no] { $player } bewegt einen Stein von Punkt { $src }, um deinen Stein auf Punkt { $dest } zu schlagen.
    } { $src_count ->
        [0] Punkt { $src } ist jetzt leer.
       *[other] { $src_count } verbleiben auf Punkt { $src }.
    }
# Ausführlicher Zugkommentar
backgammon-verbose-move-normal =
    { $is_self ->
        [yes] Du bewegst einen Stein von Punkt { $src } auf Punkt { $dest }.
       *[no] { $player } bewegt einen Stein von Punkt { $src } auf Punkt { $dest }.
    } { $src_count ->
        [0] Punkt { $src } ist jetzt leer, { $dest_count } auf Punkt { $dest }.
       *[other] { $src_count } jetzt auf Punkt { $src }, { $dest_count } auf Punkt { $dest }.
    }

