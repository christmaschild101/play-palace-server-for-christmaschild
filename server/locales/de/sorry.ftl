# Sorry localization

game-name-sorry = Sorry!
category-board-games = Board Games

# Turn actions
sorry-draw-card = Draw card
sorry-move-slot = Move option { $slot }
sorry-move-slot-fallback = Choose move

# Move labels (for dynamic move menu entries)
sorry-move-start = Move pawn { $pawn } out of start
sorry-move-forward = Move pawn { $pawn } forward { $steps }
sorry-move-backward = Move pawn { $pawn } backward { $steps }
sorry-move-swap = Swap pawn { $pawn } with { $target_player } pawn { $target_pawn }
sorry-move-sorry = Move pawn { $pawn } to replace { $target_player } pawn { $target_pawn }
sorry-move-split7 = Split 7: pawn { $pawn_a } moves { $steps_a }, pawn { $pawn_b } moves { $steps_b }

# Gameplay announcements
sorry-card-sorry = Sorry!
sorry-draw-announcement = { $player } draws { $card }.
sorry-no-legal-moves = { $player } has no legal moves for { $card }.
sorry-play-start = { $player } moves pawn { $pawn } out of start. Pawn { $pawn } is now { $zone ->
        [track] on track square { $position }
        [home_path] on home path step { $home_steps }
        [home] home
       *[other] in start
    }.
sorry-play-forward = { $player } moves pawn { $pawn } forward { $steps }. Pawn { $pawn } is now { $zone ->
        [track] on track square { $position }
        [home_path] on home path step { $home_steps }
        [home] home
       *[other] in start
    }.
sorry-play-backward = { $player } moves pawn { $pawn } backward { $steps }. Pawn { $pawn } is now { $zone ->
        [track] on track square { $position }
        [home_path] on home path step { $home_steps }
        [home] home
       *[other] in start
    }.
sorry-play-swap = { $player } swaps pawn { $pawn } with { $target_player } pawn { $target_pawn }. Pawn { $pawn } is now { $zone ->
        [track] on track square { $position }
        [home_path] on home path step { $home_steps }
        [home] home
       *[other] in start
    }, { $target_player } pawn { $target_pawn } is now { $target_zone ->
        [track] on track square { $target_position }
        [home_path] on home path step { $target_home_steps }
        [home] home
       *[other] in start
    }.
sorry-play-sorry = Sorry! { $player } replaces { $target_player } pawn { $target_pawn } with pawn { $pawn }. Pawn { $pawn } is now { $zone ->
        [track] on track square { $position }
        [home_path] on home path step { $home_steps }
        [home] home
       *[other] in start
    }.
sorry-play-split7 = { $player } splits 7: pawn { $pawn_a } moves { $steps_a }, pawn { $pawn_b } moves { $steps_b }. Pawn { $pawn_a } is now { $a_zone ->
        [track] on track square { $a_position }
        [home_path] on home path step { $a_home_steps }
        [home] home
       *[other] in start
    }, pawn { $pawn_b } is now { $b_zone ->
        [track] on track square { $b_position }
        [home_path] on home path step { $b_home_steps }
        [home] home
       *[other] in start
    }.



# Home arrival announcements
sorry-pawn-home = { $player } pawn { $pawn } has arrived home!
sorry-you-pawn-home = Your pawn { $pawn } has arrived home!

# Options
sorry-option-rules-profile = Rules profile: { $rules_profile }
sorry-option-select-rules-profile = Select rules profile
sorry-option-changed-rules-profile = Rules profile set to { $rules_profile }.
sorry-rules-profile-classic-00390 = Classic 00390
sorry-rules-profile-a5065-core = A5065 Core
sorry-option-auto-apply-single-move = Auto apply single move: { $auto_apply_single_move }
sorry-option-faster-setup-one-pawn-out = Faster setup (one pawn out): { $faster_setup_one_pawn_out }
sorry-option-changed-auto-apply-single-move = Auto apply single move set to { $auto_apply_single_move }.
sorry-option-changed-faster-setup-one-pawn-out = Faster setup set to { $faster_setup_one_pawn_out }.

sorry-board-pawn-brief = Spielstein { $pawn } { $zone }
sorry-board-player-line = { $player }: { $pawns }
sorry-move-split7-option = Spielstein { $pawn_a } bewegt sich um { $steps_a }, Spielstein { $pawn_b } um { $steps_b }
sorry-move-split7-pick = Teile 7 zwischen Spielstein { $pawn_a } und Spielstein { $pawn_b } auf
sorry-pawn-captured = { $player } schickte den Spielstein { $pawn } von { $target_player } zurück zum Start.
# Brettansicht
sorry-view-board = Brett anzeigen
sorry-view-pawns = Deine Spielsteine anzeigen
sorry-view-your-pawn = Dein Spielstein { $pawn }: { $zone }.
sorry-you-captured-pawn = Du hast den Spielstein { $pawn } von { $target_player } zurück zum Start geschickt.
sorry-you-draw-announcement = Du ziehst { $card }.
sorry-you-no-legal-moves = Du hast keine legalen Züge für { $card }.
sorry-you-play-backward =
    Du bewegst Spielstein { $pawn } um { $steps } zurück. Spielstein { $pawn } ist jetzt { $zone ->
        [track] auf Spielfeld { $position }
        [home_path] im Zielpfadschritt { $home_steps }
        [home] zu Hause
       *[other] im Start
    }.
sorry-you-play-forward =
    Du bewegst Spielstein { $pawn } um { $steps } vor. Spielstein { $pawn } ist jetzt { $zone ->
        [track] auf Spielfeld { $position }
        [home_path] im Zielpfadschritt { $home_steps }
        [home] zu Hause
       *[other] im Start
    }.
sorry-you-play-sorry =
    Sorry! Du ersetzt den Spielstein { $target_pawn } von { $target_player } durch Spielstein { $pawn }. Spielstein { $pawn } ist jetzt { $zone ->
        [track] auf Spielfeld { $position }
        [home_path] im Zielpfadschritt { $home_steps }
        [home] zu Hause
       *[other] im Start
    }.
sorry-you-play-split7 =
    Du teilst 7: Spielstein { $pawn_a } bewegt sich um { $steps_a }, Spielstein { $pawn_b } um { $steps_b }. Spielstein { $pawn_a } ist jetzt { $a_zone ->
        [track] auf Spielfeld { $a_position }
        [home_path] im Zielpfadschritt { $a_home_steps }
        [home] zu Hause
       *[other] im Start
    }, Spielstein { $pawn_b } ist jetzt { $b_zone ->
        [track] auf Spielfeld { $b_position }
        [home_path] im Zielpfadschritt { $b_home_steps }
        [home] zu Hause
       *[other] im Start
    }.
sorry-you-play-start =
    Du bewegst Spielstein { $pawn } aus dem Start. Spielstein { $pawn } ist jetzt { $zone ->
        [track] auf Spielfeld { $position }
        [home_path] im Zielpfadschritt { $home_steps }
        [home] zu Hause
       *[other] im Start
    }.
sorry-you-play-swap =
    Du tauschst Spielstein { $pawn } mit dem Spielstein { $target_pawn } von { $target_player }. Spielstein { $pawn } ist jetzt { $zone ->
        [track] auf Spielfeld { $position }
        [home_path] im Zielpfadschritt { $home_steps }
        [home] zu Hause
       *[other] im Start
    }, der Spielstein { $target_pawn } von { $target_player } ist jetzt { $target_zone ->
        [track] auf Spielfeld { $target_position }
        [home_path] im Zielpfadschritt { $target_home_steps }
        [home] zu Hause
       *[other] im Start
    }.
# Gefangen-Ansagen
sorry-your-pawn-captured = Dein Spielstein { $pawn } wurde von { $by_player } zurück zum Start geschickt.
sorry-zone-home = zu Hause
sorry-zone-home-path = im Zielpfadschritt { $steps }
sorry-zone-start = im Start
sorry-zone-track = auf Spielfeld { $position }

