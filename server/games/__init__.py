"""Game implementations."""

from .base import Game
from .registry import GameRegistry, register_game, get_game_class

# Import all games to trigger registration
from .pig.game import PigGame
from .scopa.game import ScopaGame
from .lightturret.game import LightTurretGame
from .threes.game import ThreesGame
from .milebymile.game import MileByMileGame
from .chaosbear.game import ChaosBearGame
from .farkle.game import FarkleGame
from .yahtzee.game import YahtzeeGame
from .ninetynine.game import NinetyNineGame
from .tradeoff.game import TradeoffGame
from .pirates.game import PiratesGame
from .leftrightcenter.game import LeftRightCenterGame
from .ludo.game import LudoGame
from .tossup.game import TossUpGame
from .midnight.game import MidnightGame
from .ageofheroes.game import AgeOfHeroesGame
from .fivecarddraw.game import FiveCardDrawGame
from .holdem.game import HoldemGame
from .crazyeights.game import CrazyEightsGame

from .snakesandladders.game import SnakesAndLaddersGame
from .rollingballs.game import RollingBallsGame
from .sorry.game import SorryGame
from .metalpipe.game import MetalPipeGame
from .humanitycards.game import HumanityCardsGame
from .nine.game import NineGame
from .blackjack.game import BlackjackGame
from .twentyone import TwentyOneGame
from .chess.game import ChessGame
from .backgammon.game import BackgammonGame
from .senet.game import SenetGame

# PlayAural games
from .battleship.game import BattleshipGame
from .coup.game import CoupGame
from .dominos.game import DominosGame
from .lastcard.game import LastCardGame
from .pusoydos.game import PusoyDosGame
from .battle.game import BattleGame
from .bunko.game import BunkoGame
from .citadels.game import CitadelsGame
from .colorgame.game import ColorGameGame
from .deadmansdeck.game import DeadMansDeckGame
from .deadmanspoker.game import DeadMansPokerGame
from .tienlen.game import TienLenGame

# New games (2026 wave)
from .shipcaptaincrew.game import ShipCaptainCrewGame
from .tictactoe.game import TicTacToeGame
from .go_fish.game import GoFishGame
from .mancala.game import MancalaGame
from .shutthebox.game import ShutTheBoxGame
from .ceelo.game import CeeLoGame
from .reversi.game import ReversiGame
from .cantstop.game import CanTStopGame
from .liarsdice.game import LiarsDiceGame
from .hangman.game import HangmanGame
from .hearts.game import HeartsGame
from .monopoly.game import MonopolyGame

__all__ = [
    "Game",
    "GameRegistry",
    "register_game",
    "get_game_class",
    "PigGame",
    "ScopaGame",
    "LightTurretGame",
    "ThreesGame",
    "MileByMileGame",
    "ChaosBearGame",
    "FarkleGame",
    "YahtzeeGame",
    "NinetyNineGame",
    "TradeoffGame",
    "PiratesGame",
    "LeftRightCenterGame",
    "LudoGame",
    "TossUpGame",
    "MidnightGame",
    "AgeOfHeroesGame",
    "FiveCardDrawGame",
    "HoldemGame",
    "CrazyEightsGame",
    "SnakesAndLaddersGame",
    "RollingBallsGame",
    "SorryGame",
    "MetalPipeGame",
    "HumanityCardsGame",
    "NineGame",
    "BlackjackGame",
    "TwentyOneGame",
    "ChessGame",
    "BackgammonGame",
    "SenetGame",
    "BattleshipGame",
    "CoupGame",
    "DominosGame",
    "LastCardGame",
    "PusoyDosGame",
    "BattleGame",
    "BunkoGame",
    "CitadelsGame",
    "ColorGameGame",
    "DeadMansDeckGame",
    "DeadMansPokerGame",
    "TienLenGame",
    "ShipCaptainCrewGame",
    "TicTacToeGame",
    "GoFishGame",
    "MancalaGame",
    "ShutTheBoxGame",
    "CeeLoGame",
    "ReversiGame",
    "CanTStopGame",
    "LiarsDiceGame",
    "HangmanGame",
    "HeartsGame",
    "MonopolyGame",
]
