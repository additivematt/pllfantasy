import os
from dotenv import load_dotenv
load_dotenv()

# ── Centralized Constants and Settings ────────────────────────────────────────

# --- Monte Carlo Simulation ---
LAMBDA_RECENCY = 0.05
N_MC_TRIALS = 10000

# --- Optimization Defaults ---
DEFAULT_WIN_SCORE_THRESHOLD = 165.0
LOCAL_SEARCH_RESTARTS = 10
DEFAULT_BUDGET = 200

# --- Roster Requirement Constraints ---
POSITION_REQUIREMENTS = {'A': 2, 'M': 2, 'D': 1, 'FO': 1, 'G': 1}

# --- Feature Toggles ─────────────────────────────────────────────────────────
# Toggle experimental features on/off without code edits. Each toggle controls
# a feature that has been implemented and can be A/B tested via the backtest
# pipeline. Set to True to enable, False to disable.

# Game Pace Scaling (Option C): Multiplies matchup ratings by a rolling game
# pace factor derived from team expected goals. Enabled by default.
GAME_PACE_ENABLED = True

# Pace Adjusted Rates (Item 46): Normalize player counting stats to per-10-possessions
# and compute game_pace based on estimated possessions instead of goals.
PACE_ADJUSTED_RATES_ENABLED = os.environ.get("PACE_ADJUSTED_RATES_ENABLED", "False") == "True"


# MC Ceiling Clamp Multiplier: Caps simulated player scores at
# max_historical * this value. Set to None to disable clamping entirely.
CEILING_CLAMP_MULTIPLIER = None  # Was 1.15; currently no clamp in production code

# Salary as Feature: Feed normalized salary percentile into the GBDT model
# as a market consensus signal.
SALARY_AS_FEATURE = False
SALARY_AS_FEATURE_POSITIONS = {
    "Attack": True,
    "Midfield": True,
    "Defense": True,
    "Faceoff": True,
    "Goalie": True
}

# Correlation Copula: Use the Gaussian copula correlation matrix in MC sims.
# Enabled by default; can be disabled for independent simulation comparison.
CORRELATION_COPULA_ENABLED = True

# Usage & Health Features: Weight defensive health by player quality,
# and introduce touches_anomaly delta features.
USAGE_HEALTH_FEATURES_ENABLED = False

# GBDT Matchup Leakage Fix: Compute expanding/cumulative ratings chronologically
# to prevent future lookup data leakage during model training. Enabled by default.
DATA_LEAKAGE_FIX_ENABLED = True

# Bayesian Shrinkage on Matchup Ratings: Blends raw matchup ratings with a prior
# of 1.0 based on sample size to prevent extreme noise for low-sample pairings.
SHRINKAGE_ENABLED = True
SHRINKAGE_K = 5

# Exponentially-Weighted Moving Average (EWMA) Rolling Features
EWMA_ENABLED = True

# Smooth MC Historical Pool Blending: blends player history with position pool
# to eliminate the hard cliff at 5 games.
MC_POOL_BLENDING_ENABLED = True
MC_POOL_BLENDING_K = 15

# --- API Tokens (with environment variable fallbacks) ─────────────────────────
API_TOKEN_STATS = os.environ.get("PLL_STATS_API_TOKEN", "N)eIKy1rZ%/%fm1WhM7tuVcrR*UIsc")
API_TOKEN_ROSTER = os.environ.get("PLL_ROSTER_API_TOKEN", "2<b}_K/x8JU1mn/")

# --- F2P Leaderboard & Rival Scraping ---
F2P_LEADERBOARD_GROUP_ID = int(os.environ.get("F2P_LEADERBOARD_GROUP_ID", 51185))
F2P_LOCAL_LEAGUE_GROUP_ID = int(os.environ.get("F2P_LOCAL_LEAGUE_GROUP_ID", 53205))
F2P_CONSENSUS_WEIGHT = float(os.environ.get("F2P_CONSENSUS_WEIGHT", 0.2))
F2P_FIREBASE_ID_TOKEN = os.environ.get("F2P_FIREBASE_ID_TOKEN", "")

