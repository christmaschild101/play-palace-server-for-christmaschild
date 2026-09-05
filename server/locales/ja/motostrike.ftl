# Moto Strike localization (English)

# =============================================================================
# Cards
# =============================================================================

motostrike-card-easy-ride = Easy Ride
motostrike-card-speed-boost = Speed Boost
motostrike-card-power-dash = Power Dash
motostrike-card-mud-trap = Mud Trap
motostrike-card-spike-trap = Spike Trap
motostrike-card-rock-trap = Rock Trap
motostrike-card-smoke-bomb = Smoke Bomb
motostrike-card-electric-shock = Electric Shock
motostrike-card-police-chase = Police Chase
motostrike-card-quick-kick = Quick Kick
motostrike-card-deadly-kick = Deadly Kick
motostrike-card-kick-shield = Kick Shield
motostrike-card-emergency-swerve = Emergency Swerve
motostrike-card-slight-left = Slight Turn Left
motostrike-card-slight-right = Slight Turn Right
motostrike-card-full-left = Full Turn Left
motostrike-card-full-right = Full Turn Right
motostrike-card-rebalance = Rebalance
motostrike-card-repair = Repair
motostrike-card-escape = Escape

# =============================================================================
# Race flow
# =============================================================================

motostrike-race-start = The race begins! First rider to cross { $meters } meters wins. Riders were dealt 5 cards.
motostrike-rides = { $player } rides { $distance } meters to { $total } meters.
motostrike-maneuvers = { $player } turns and gains { $distance } meters, reaching { $total } meters.
motostrike-maneuvers-no-move = { $player } turns but can't move right now.
motostrike-recovers = { $player } plays a { $card } and gets their bike back in shape.
motostrike-discards = { $player } discards a { $card }.
motostrike-deck-reshuffled = The deck ran out and the discard pile was reshuffled.

# =============================================================================
# Traps
# =============================================================================

motostrike-trap-blocked = { $player } sets a { $trap }, but { $target } swerves to dodge it!
motostrike-mud-hit = { $player } sets a Mud Trap! { $target } is stuck in the mud and needs a Rebalance card to move.
motostrike-wreck-hit = { $player } sets a { $trap }! { $target }'s bike falls and their wheel is damaged. They need a Repair and a Rebalance card.

# =============================================================================
# Attacks
# =============================================================================

motostrike-smoke-hit = { $player } throws a smoke bomb at { $target }, slowing them down { $distance } meters to { $total } meters.
motostrike-shock-hit = { $player } shocks { $target }, who drops a { $card } at random!
motostrike-shock-empty = { $player } shocks { $target }, but their hand is empty!
motostrike-chase-started = { $player } calls the police on { $target }! { $target } has { $turns } turns to play a Maneuver card.
motostrike-chase-window = { $target } has { $turns } turn left to play a Maneuver card and escape the police.
motostrike-chase-escaped = { $target } maneuvers away and escapes the police!
motostrike-chase-immobilized = { $target } failed to escape! The police immobilize them until they play an Escape card.

# =============================================================================
# Specials
# =============================================================================

motostrike-kick-blocked = { $player } tries a kick, but { $target }'s Kick Shield absorbs it!
motostrike-quick-kick = { $player } delivers a quick kick, knocking { $target } back { $distance } meters to { $total } meters!
motostrike-deadly-kick = { $player } lands a DEADLY KICK on { $target }! { $target } is out of the race!

# =============================================================================
# End of race
# =============================================================================

motostrike-winner = { $winner } crosses the finish line and wins the race!
motostrike-winner-elimination = { $winner } is the last rider standing and wins the race!
motostrike-final-standings = Final standings:

# =============================================================================
# Play feedback
# =============================================================================

motostrike-cant-play = Can't play { $card }. { $reason }
motostrike-no-card-selected = No card selected. Navigate to a card in the menu first.
motostrike-no-valid-target = No valid target for that card.
motostrike-target-prompt = Choose a target

# =============================================================================
# Status
# =============================================================================

motostrike-bike-status-action = Bike status
motostrike-race-status-action = Race status
motostrike-bike-status = You are at { $distance } meters. Status: { $status }.{ $hint }
motostrike-race-status-line = { $name }: { $distance } meters, { $status }
motostrike-status-stuck = stuck
motostrike-status-wheel = wheel damaged
motostrike-status-immobilized = immobilized by the police
motostrike-status-chased = police chase, { $turns } turns to escape
motostrike-status-eliminated = eliminated
motostrike-status-clear = bike is fine
motostrike-bike-hint-wheel = Your wheel is damaged; play a Repair card, then Rebalance.
motostrike-bike-hint-stuck = You need a Rebalance card to move.
motostrike-bike-hint-immobilized = You need an Escape card to move.
motostrike-bike-hint-chase = The police are chasing you; play a Maneuver card within { $turns } turns.

# =============================================================================
# Unplayable reasons
# =============================================================================

motostrike-reason-eliminated = You are out of the race.
motostrike-reason-stuck = Your bike is stuck; play a Rebalance card first.
motostrike-reason-wheel = Your wheel is damaged; play a Repair card first.
motostrike-reason-immobilized = You are immobilized by the police; play an Escape card.
motostrike-reason-not-stuck = Your bike is not stuck.
motostrike-reason-wheel-fine = Your wheel is not damaged.
motostrike-reason-not-immobilized = You are not immobilized.
motostrike-reason-no-target = No valid target.
motostrike-reason-no-one-behind = No opponent is directly behind you.
motostrike-reason-no-one-within = No opponent is within 50 meters.
motostrike-reason-no-one-ahead = No opponent is ahead of you.
motostrike-reason-chase-active = That opponent is already being chased or immobilized.
motostrike-reason-need-1000 = You must have covered 1000 meters to use the Deadly Kick.
motostrike-reason-disabled = The Deadly Kick is disabled for this race.
motostrike-reason-hold-only = This card protects you automatically while held; it can't be played.
motostrike-reason-generic = This card can't be used right now.

# =============================================================================
# Options
# =============================================================================

motostrike-set-track-length = Set track length
motostrike-enter-track-length = Enter the track length in meters
motostrike-option-changed-track-length = Track length changed to { $meters } meters
motostrike-desc-track-length = The distance riders must cover to win (default 2000 meters).

motostrike-toggle-deadly-kick = Enable Deadly Kick
motostrike-option-changed-deadly-kick = Deadly Kick { $enabled ->
    [true] enabled
    *[false] disabled
}
motostrike-desc-deadly-kick = When enabled, riders who have covered 1000 meters can play the Deadly Kick to eliminate an opponent from the race.