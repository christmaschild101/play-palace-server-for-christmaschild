# Aircraft Extreme localization (English)

game-name-aircraftextreme = Aircraft Extreme

# =============================================================================
# Intro / map briefing
# =============================================================================

aircraftextreme-intro = Welcome to Aircraft Extreme! Each pilot flies from their own corner runway around the storm-filled sky. First to fly { $laps } laps and land back home wins — or be the last plane still flying!
aircraftextreme-map-briefing = The sky map is { $size } by { $size } squares with a thunderstorm block in the middle. Fly to the corner opposite your runway to complete each lap, then land on your runway to win. Each turn you get { $actions } actions: flying costs 1 engine power.
aircraftextreme-your-base = You start on the { $base }. Touch the opposite corner to bank a lap; first to { $laps } laps and home wins!

# =============================================================================
# Zones and positions
# =============================================================================

aircraftextreme-position = row { $row }, column { $col }
aircraftextreme-base-nw = northwest base
aircraftextreme-base-ne = northeast base
aircraftextreme-base-sw = southwest base
aircraftextreme-base-se = southeast base
aircraftextreme-zone-north = the north sky
aircraftextreme-zone-south = the south sky
aircraftextreme-zone-west = the west sky
aircraftextreme-zone-east = the east sky
aircraftextreme-zone-storm = inside the thunderstorm block!

# =============================================================================
# Turn flow
# =============================================================================

aircraftextreme-turn-start = { $player }'s turn — { $zone }.
aircraftextreme-your-turn = Your turn, pilot! { $position }, engine at { $power } power, health { $health }. { $left }
aircraftextreme-actions-one = 1 action left this turn.
aircraftextreme-actions-two = 2 actions left this turn.
aircraftextreme-fly-home = All laps complete — fly home and land on your runway to win!

# =============================================================================
# Flying
# =============================================================================

aircraftextreme-flies = { $player } flies { $direction } to { $position }.
aircraftextreme-you-fly = You fly { $direction } to { $position }. Engine at { $power } power.
aircraftextreme-fly-blocked-edge = The map edge blocks that path — pick another direction!
aircraftextreme-fly-blocked-storm = You can't fly into a thunderstorm!
aircraftextreme-fly-blocked-occupied = That square is occupied — you can't fly into another plane.
aircraftextreme-lap-complete = { $player } completes lap { $lap } of { $total }!

# =============================================================================
# Engine power
# =============================================================================

aircraftextreme-climb = { $player } climbs into the jet stream — engine charged to { $power } power.
aircraftextreme-you-climb = You climb into the jet stream — engine charged to { $power } power.
aircraftextreme-climb-nothing = Engine already charged — you hold altitude instead.

# =============================================================================
# Combat
# =============================================================================

aircraftextreme-fire-at = { $player } opens fire at { $target }!
aircraftextreme-fire-hit = { $player } hits { $target } for { $damage } damage — { $target }'s plane is at { $health } health.
aircraftextreme-fire-miss = { $player } fires at { $target } and misses — engines cool to { $power } power.
aircraftextreme-fire-no-target = No enemy in firing range. Fly closer!
aircraftextreme-fire-own-base = You can't fire while parked on your own runway.
aircraftextreme-fire-target-safe = { $target } is safe on their own runway — no shot.
aircraftextreme-shot-down = { $killer } shoots down { $victim }!
aircraftextreme-pilot-out = { $victim } has been shot down three times and is out of the game!
aircraftextreme-respawn-after-down = { $player } is back on their runway with a fresh plane.
aircraftextreme-last-plane = { $winner } is the last plane still flying — victory!

# =============================================================================
# Maneuvers
# =============================================================================

aircraftextreme-barrel-roll = { $player } barrel rolls — incoming fire this turn will miss.
aircraftextreme-you-barrel-roll = You barrel roll — evasive!
aircraftextreme-cloud-shield = { $player } dives into a cloud bank — the next hit is absorbed.
aircraftextreme-you-cloud = You dive into a cloud bank — protected!
aircraftextreme-cloud-shield-used = { $player }'s cloud cover absorbs the hit!

# =============================================================================
# Thunderstorms
# =============================================================================

aircraftextreme-storm-hit = Thunder cracks — { $player } takes a storm hit for { $damage } damage! Health: { $health }.
aircraftextreme-storm-miss = { $player } threads past the storm on the edge of chaos — no damage.
aircraftextreme-storm-downed = The storm downs { $player }!

# =============================================================================
# Status readouts
# =============================================================================

aircraftextreme-pilot-status = { $position }. Health { $health }, engine { $power } power. { $status }
aircraftextreme-status-clear = All systems green.
aircraftextreme-status-downed = Waiting to respawn on the runway.
aircraftextreme-status-clouded = Hidden in cloud cover.
aircraftextreme-status-evasive = Flying evasive.
aircraftextreme-status-no-power = Engine dead — restart with Climb.
aircraftextreme-sky-status = Sky report:
aircraftextreme-sky-line = { $name }: { $position }, health { $health }, { $status }
aircraftextreme-sky-storms = Thunderstorms rumble at rows 3-4, columns 3-4.
aircraftextreme-cell-empty = { $coord } — clear sky.
aircraftextreme-cell-plane = { $coord } — { $plane }'s plane.
aircraftextreme-cell-storm = { $coord } — thunderstorm!

# =============================================================================
# Actions menu / keybinds
# =============================================================================

aircraftextreme-action-fly-north = Fly north
aircraftextreme-action-fly-south = Fly south
aircraftextreme-action-fly-west = Fly west
aircraftextreme-action-fly-east = Fly east
aircraftextreme-action-fire = Fire cannons
aircraftextreme-action-barrel-roll = Barrel roll
aircraftextreme-action-climb = Climb
aircraftextreme-action-cloud = Dive into clouds
aircraftextreme-action-pilot-status = Pilot status
aircraftextreme-action-sky-status = Sky report

# =============================================================================
# Options
# =============================================================================

aircraftextreme-set-laps = Set laps to win
aircraftextreme-enter-laps = Laps to win (1-10):
aircraftextreme-option-changed-laps = Laps to win set to { $value }.
aircraftextreme-desc-laps = How many laps a pilot must complete before landing home to win.
aircraftextreme-set-storm-damage = Set storm damage
aircraftextreme-enter-storm-damage = Storm damage per strike (0-3):
aircraftextreme-option-changed-storm-damage = Storm damage set to { $value }.
aircraftextreme-desc-storm-damage = Damage a plane takes when a thunderstorm strikes it.
aircraftextreme-set-start-health = Set plane health
aircraftextreme-enter-start-health = Health per plane (4-20):
aircraftextreme-option-changed-start-health = Plane health set to { $value }.
aircraftextreme-desc-start-health = How much damage a plane can take before it is shot down.
aircraftextreme-set-respawn-health = Set respawn health
aircraftextreme-enter-respawn-health = Health after respawning (2-20):
aircraftextreme-option-changed-respawn-health = Respawn health set to { $value }.
aircraftextreme-desc-respawn-health = Health a plane returns with after being shot down and respawning.
aircraftextreme-error-respawn-too-high = Respawn health cannot be higher than plane health.

# =============================================================================
# Reasons / errors
# =============================================================================

aircraftextreme-reason-no-power = Engine dead — play Climb to restart it.
aircraftextreme-reason-no-actions = No actions left this turn.
aircraftextreme-reason-downed = You're waiting to respawn.

# =============================================================================
# Results
# =============================================================================

aircraftextreme-winner-laps = { $player } wins by flying { $laps } laps and landing home!
aircraftextreme-final-standings = Final standings — laps flown and planes remaining:
aircraftextreme-standings-line = { $name }: { $laps } lap(s), health { $health }.

# =============================================================================
# Leaderboards
# =============================================================================

leaderboard-type-most-laps = Most laps flown
leaderboard-type-avg-laps = Average laps per game
