# Liar's Dice game messages

# Game info
game-name-liarsdice = Liar's Dice

# Actions
liarsdice-bid = Bid
liarsdice-bid-face = Choose the face
liarsdice-challenge-no-bid = Challenge
liarsdice-challenge = Challenge { $qty } { $face }s
liarsdice-pick-qty = How many dice do you claim?
liarsdice-pick-face = Of what face value?
liarsdice-qty = { $qty } dice

# Round flow
liarsdice-round-start = Round { $round }. Everyone rolls!
liarsdice-your-dice = Your dice: { $dice }.
liarsdice-bid = { $player } bids { $qty } { $face }s.

# Challenges
liarsdice-challenge-true = { $challenger } challenges { $bidder }'s { $qty } { $face }s… True! There are { $actual }. { $challenger } loses a die!
liarsdice-challenge-false = { $challenger } challenges { $bidder }'s { $qty } { $face }s… False! There are only { $actual }. { $bidder } loses a die!
liarsdice-lost-die = { $player } loses a die ({ $dice } remaining).
liarsdice-eliminated = { $player } is eliminated!

# Game end
liarsdice-winner = { $player } is the last liar standing and wins!
liarsdice-score-line = { $player }: { $dice } dice

# Disabled reasons
liarsdice-pick-face-first = Pick a face first.
liarsdice-pick-qty-first = Pick a quantity first.
liarsdice-no-bid = No bid to challenge yet.
liarsdice-lower-bid = Your bid must be higher than the current one.

# Options
liarsdice-set-wild-ones = Ones are wild: { $enabled }
liarsdice-desc-wild-ones = Count ones toward every face value
liarsdice-option-changed-wild-ones = Wild ones: { $enabled }.