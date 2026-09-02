# Reversi (Othello) game messages

# Game info
game-name-reversi = Reversi

# Moves
reversi-move = { $player } places { $mark } at { $coord }.
reversi-flips = { $player } flips { $count } discs!
reversi-pass = { $player } has no legal moves and passes.

# Turns
reversi-your-turn = Your turn, you are { $mark }.
reversi-turn-start = { $player }'s turn ({ $mark }).

# Grid cells
reversi-cell-empty = { $coord }, empty
reversi-cell-playable = { $coord }, empty, playable
reversi-cell-filled = { $coord }, { $mark }

# Game end
reversi-winner = { $player } wins with { $score } discs!
reversi-tie = It's a tie at { $score } discs!
reversi-final = Final score — Black: { $black }, White: { $white }

# Disabled reasons
reversi-cell-taken = That cell is already occupied.
reversi-not-legal = That move is not legal.