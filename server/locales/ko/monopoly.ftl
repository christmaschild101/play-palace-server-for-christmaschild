# Monopoly board game messages

# Game info
game-name-monopoly = Monopoly

# Actions
monopoly-roll = Roll the dice
monopoly-buy = Buy for { $price }
monopoly-decline = Don't buy (auction)
monopoly-bid-action = Bid (currently { $bid })
monopoly-pass-action = Pass
monopoly-build = Build a house
monopoly-mortgage = Mortgage a property
monopoly-unmortgage = Unmortgage a property
monopoly-trade = Trade a property
monopoly-trade-target = Choose who to trade with
monopoly-trade-price = Set the price
monopoly-end-turn = End turn ({ $money })
monopoly-status = Money { $money }, on { $space }
monopoly-pick-build = Build a house on:
monopoly-pick-mortgage = Mortgage:
monopoly-pick-unmortgage = Unmortgage:
monopoly-pick-trade = Trade away:
monopoly-pick-trade-target = Trade with:
monopoly-enter-bid = Enter your bid:
monopoly-enter-trade-price = Enter the price:

# Board spaces
monopoly-space-go = Go
monopoly-space-mediterranean = Mediterranean Avenue
monopoly-space-chest = Community Chest
monopoly-space-baltic = Baltic Avenue
monopoly-space-income-tax = Income Tax
monopoly-space-reading-railroad = Reading Railroad
monopoly-space-oriental = Oriental Avenue
monopoly-space-chance = Chance
monopoly-space-vermont = Vermont Avenue
monopoly-space-connecticut = Connecticut Avenue
monopoly-space-jail = Jail
monopoly-space-st-charles = St. Charles Place
monopoly-space-electric-company = Electric Company
monopoly-space-states = States Avenue
monopoly-space-virginia = Virginia Avenue
monopoly-space-pennsylvania-railroad = Pennsylvania Railroad
monopoly-space-st-james = St. James Place
monopoly-space-tennessee = Tennessee Avenue
monopoly-space-new-york = New York Avenue
monopoly-space-free-parking = Free Parking
monopoly-space-kentucky = Kentucky Avenue
monopoly-space-indiana = Indiana Avenue
monopoly-space-illinois = Illinois Avenue
monopoly-space-bo-railroad = B. & O. Railroad
monopoly-space-atlantic = Atlantic Avenue
monopoly-space-ventnor = Ventnor Avenue
monopoly-space-water-works = Water Works
monopoly-space-marvin-gardens = Marvin Gardens
monopoly-space-go-to-jail = Go To Jail
monopoly-space-pacific = Pacific Avenue
monopoly-space-north-carolina = North Carolina Avenue
monopoly-space-pennsylvania = Pennsylvania Avenue
monopoly-space-short-line-railroad = Short Line Railroad
monopoly-space-park-place = Park Place
monopoly-space-luxury-tax = Luxury Tax
monopoly-space-boardwalk = Boardwalk
monopoly-space-unknown = the unknown space

# Start and turn flow
monopoly-start = Game on! Everyone collects starting money and begins at Go.
monopoly-rolled = { $player } rolled { $dice }.
monopoly-doubles-again = { $player } rolled doubles and goes again!
monopoly-three-doubles = { $player } rolled three doubles in a row and goes to jail!
monopoly-landed = { $player } lands on { $space }.
monopoly-passed-go = { $player } passed Go and collected 200!

# Buying and auctions
monopoly-landed-unowned = { $player } can buy { $space } for { $price }.
monopoly-bought = { $player } buys { $space } for { $price }!
monopoly-cannot-afford = You can't afford that ({ $amount } needed).
monopoly-auction = { $player } declines — { $space } goes to auction!
monopoly-auction-start = Auction for { $space }!
monopoly-bid = { $player } bids { $bid }.
monopoly-passed = { $player } passes.
monopoly-bid-higher = Your bid must be higher than { $bid }.
monopoly-auction-won = { $player } wins { $space } for { $bid }!
monopoly-auction-none = Nobody bid — { $space } stays unowned.

# Rent and money
monopoly-paid-rent = { $player } pays { $owner } rent of { $rent } on { $space }.
monopoly-tax = { $player } pays { $tax } tax at { $space }.
monopoly-mortgaged-no-rent = The property is mortgaged — no rent due.
monopoly-your-property = { $space } is yours. No rent.
monopoly-free-parking = Free Parking! Nothing happens.

# Jail
monopoly-sent-jail = { $player } is sent to jail!
monopoly-jail-doubles = { $player } rolled doubles and gets out of jail!
monopoly-jail-stays = { $player } stays in jail (turn { $turns } of 3).
monopoly-jail-pay = { $player } pays { $bail } bail to leave jail.

# Building and mortgages
monopoly-built = { $player } builds on { $space } ({ $houses } buildings).
monopoly-cannot-afford-build = You need { $cost } to build there.
monopoly-sell-houses-first = Sell the houses before mortgaging.
monopoly-mortgaged = { $player } mortgages { $space } for { $value }.
monopoly-unmortgaged = { $player } unmortgages { $space } for { $cost }.

# Trades
monopoly-traded = { $player } trades { $space } to { $target } for { $price }.
monopoly-target-afford = { $player } can't afford that.

# Chance and Community Chest
monopoly-chance = Chance
monopoly-chest = Community Chest
monopoly-card = { $player } draws a { $deck } card: { $card }
monopoly-card-collect = The bank pays you { $amount }.
monopoly-card-pay = You pay { $amount }.
monopoly-card-jail = Go directly to jail!
monopoly-card-move = Advance to the next space.
monopoly-card-back-3 = Go back three spaces.
monopoly-card-railroad = Advance to the nearest railroad (pay double rent if owned).
monopoly-card-utility = Advance to the nearest utility (pay ten times the roll if owned).
monopoly-card-chairman = You've been elected chairman — pay every player { $amount }!
monopoly-card-birthday = Collect { $amount } from every player!

# Bankrupt and winner
monopoly-bankrupt = { $player } goes bankrupt!
monopoly-bankrupt-to = { $player } goes bankrupt and transfers assets to { $creditor }!
monopoly-winner = { $player } is the last player standing and wins!
monopoly-winner-money = Round limit reached — { $player } wins with { $money }!
monopoly-score-line = { $player }: { $money }

# Disabled reasons
monopoly-not-your-phase = Not the right phase for that.
monopoly-not-available = That property isn't available.

# Options
monopoly-set-starting-money = Starting money: { $money }
monopoly-desc-starting-money = Cash each player starts with
monopoly-enter-starting-money = Enter starting money:
monopoly-option-changed-starting-money = Starting money set to { $money }.
monopoly-set-max-rounds = Max rounds: { $rounds }
monopoly-desc-max-rounds = End after this many full circuits (0 = until one player remains)
monopoly-enter-max-rounds = Enter max rounds (0 = classic):
monopoly-option-changed-max-rounds = Max rounds set to { $rounds }.