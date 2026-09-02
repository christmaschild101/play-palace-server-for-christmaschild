# Hangman word game messages

# Game info
game-name-hangman = Hangman

# Actions
hangman-guess-letter = Guess a letter
hangman-guess-word = Guess the word
hangman-enter-letter = Enter a letter:
hangman-enter-word = Enter the whole word:
hangman-guess-letter-label = Guess a letter — { $mask } ({ $wrong } of { $max_wrong } wrong)
hangman-guess-word-label = Guess the word — { $mask } ({ $wrong } of { $max_wrong } wrong)

# Round flow
hangman-round-start = Round { $round }. { $player } keeps the word ({ $letters } letters)!
hangman-you-are-keeper = You are the word keeper. The word is: { $word }.
hangman-your-turn = Your turn. The word so far: { $mask }.
hangman-turn-start = { $player }'s turn. The word so far: { $mask }.

# Guessing
hangman-correct = { $player } reveals the letter { $letter }!
hangman-wrong = { $player } is wrong ({ $wrong } of { $max_wrong }). Guessed: { $guessed }
hangman-wrong-word = { $player } guessed { $word } — wrong ({ $wrong } of { $max_wrong }).
hangman-solved = { $player } solved the word: { $word }!
hangman-out = { $player } is out of this round!
hangman-word-finished = { $player } completes the word { $word } and scores a point!
hangman-keeper-wins = Everyone is out! { $player } keeps the point: { $word }.
hangman-scores = Scores: { $scores }

# Feedback
hangman-letters-only = Letters only, please.
hangman-already-guessed = { $letter } was already guessed.

# Game end
hangman-winner = { $player } wins with { $score } points!
hangman-tie = { $players } tie with { $score } points!
hangman-score-line = { $player }: { $score }

# Disabled reasons
hangman-keeper-cannot-guess = You keep the word this round — you don't guess.
hangman-out-already = You're out of this round.
hangman-word-done = The word is complete.

# Options
hangman-set-rounds = Rounds: { $rounds }
hangman-desc-rounds = How many rounds to play
hangman-enter-rounds = Enter number of rounds:
hangman-option-changed-rounds = Rounds set to { $rounds }.
hangman-set-misses = Misses before out: { $misses }
hangman-desc-misses = Wrong guesses before a player is out of the round
hangman-enter-misses = Enter misses allowed:
hangman-option-changed-misses = Misses set to { $misses }.