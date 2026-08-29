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

# --- Item 47 Feature Ablation Toggles ---
FEATURE_DEF_STATS_ENABLED = os.environ.get("FEATURE_DEF_STATS_ENABLED", os.environ.get("FEATURE_MID_DEF_STATS_ENABLED", "False")) == "True"
FEATURE_MID_DEF_STATS_ENABLED = FEATURE_DEF_STATS_ENABLED
FEATURE_MID_ASSISTS_ONLY_ENABLED = os.environ.get("FEATURE_MID_ASSISTS_ONLY_ENABLED", "False") == "True"
FEATURE_GOALIE_GB_CT_ENABLED = os.environ.get("FEATURE_GOALIE_GB_CT_ENABLED", "False") == "True"
FEATURE_OPP_DEF_FORM_POS_ENABLED = os.environ.get("FEATURE_OPP_DEF_FORM_POS_ENABLED", "False") == "True"
FEATURE_SQUAD_CHURN_ENABLED = os.environ.get("FEATURE_SQUAD_CHURN_ENABLED", "False") == "True"
FEATURE_RETIRE_1V1_PAIRINGS_ENABLED = os.environ.get("FEATURE_RETIRE_1V1_PAIRINGS_ENABLED", "False") == "True"

# --- Item 50 & Baseline 14 Recency Sample Weighting ---
FEATURE_ATTACK_2PT_GOALS_ENABLED = os.environ.get("FEATURE_ATTACK_2PT_GOALS_ENABLED", "False") == "True"
FEATURE_ATTACK_GOALIE_FORM_ENABLED = os.environ.get("FEATURE_ATTACK_GOALIE_FORM_ENABLED", "False") == "True"
FEATURE_GOALIE_OPP_SHOTS_ENABLED = os.environ.get("FEATURE_GOALIE_OPP_SHOTS_ENABLED", "False") == "True"
RECENCY_WEIGHT_DEFAULT = float(os.environ.get("RECENCY_WEIGHT_DEFAULT", "0.3"))
ATTACK_RECENCY_WEIGHT = RECENCY_WEIGHT_DEFAULT
ALL_POSITIONS_RECENCY_WEIGHT = RECENCY_WEIGHT_DEFAULT

# --- Item 61 Positional Scoring Variance & Salary-Scaled Sample Loss Weighting ---
ITEM61_SALARY_VARIANCE_WEIGHTING_ENABLED = os.environ.get("ITEM61_SALARY_VARIANCE_WEIGHTING_ENABLED", "False") == "True"
ITEM61_ALPHA = float(os.environ.get("ITEM61_ALPHA", "0.0"))

# --- Item 60 Position-Tailored Decision Thresholds (Part A) ---
ITEM60_TAILORED_THRESHOLDS_ENABLED = os.environ.get("ITEM60_TAILORED_THRESHOLDS_ENABLED", "False") == "True"
ITEM60_THRESHOLDS = {
    "Attack": float(os.environ.get("ITEM60_THRESH_ATTACK", "0.45")),
    "Midfield": float(os.environ.get("ITEM60_THRESH_MIDFIELD", "0.35")),
    "Defense": float(os.environ.get("ITEM60_THRESH_DEFENSE", "0.42")),
    "Goalie": float(os.environ.get("ITEM60_THRESH_GOALIE", "0.58")),
    "Faceoff": float(os.environ.get("ITEM60_THRESH_FACEOFF", "0.50")),
}

# --- Item 60 Part B: Risk Asymmetry / Positional Variance Steepness in MC Simulation ---
ITEM60_POSITIONAL_STEEPNESS_ENABLED = os.environ.get("ITEM60_POSITIONAL_STEEPNESS_ENABLED", "False") == "True"
ITEM60_STEEPNESS = {
    "Attack": float(os.environ.get("ITEM60_STEEPNESS_ATTACK", "1.26")),
    "Goalie": float(os.environ.get("ITEM60_STEEPNESS_GOALIE", "1.03")),
    "Midfield": float(os.environ.get("ITEM60_STEEPNESS_MIDFIELD", "0.96")),
    "Faceoff": float(os.environ.get("ITEM60_STEEPNESS_FACEOFF", "0.82")),
    "Defense": float(os.environ.get("ITEM60_STEEPNESS_DEFENSE", "0.69")),
}
# --- Baseline 11 Monte Carlo EV Anchoring ---
# Player-Anchored EV: EV = player_fp_avg * (0.5 + BoomProb / 100)
# Anchors baseline expectation to player caliber while using BoomProb as a dynamic matchup factor.
USE_PLAYER_ANCHORED_EV = os.environ.get("USE_PLAYER_ANCHORED_EV", "True") == "True"


# MC Ceiling Clamp Multiplier: Caps simulated player scores at
# max_historical * this value. Set to None to disable clamping entirely.
CEILING_CLAMP_MULTIPLIER = None  # Was 1.15; currently no clamp in production code

# Salary as Feature: Feed normalized salary percentile into the GBDT model
# as a market consensus signal.
SALARY_AS_FEATURE = True
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

# Faceoff Bradley-Terry & Generative Heuristic (Item 52): Bypass GBDT and use a generative
# matchup-level model for the Faceoff position with temporal decay and specialist share scaling.
FACEOFF_HEURISTIC_ENABLED = True
FACEOFF_BT_EXP_DECAY = float(os.environ.get("FACEOFF_BT_EXP_DECAY", "0.5"))
FACEOFF_BT_REGULARIZATION_C = float(os.environ.get("FACEOFF_BT_REGULARIZATION_C", "0.5"))
FACEOFF_SHRINKAGE_K_FOW = float(os.environ.get("FACEOFF_SHRINKAGE_K_FOW", "10.0"))
FACEOFF_SHRINKAGE_K_GAMES = float(os.environ.get("FACEOFF_SHRINKAGE_K_GAMES", "2.0"))
FACEOFF_STAT_RECENCY_WEIGHT = float(os.environ.get("FACEOFF_STAT_RECENCY_WEIGHT", "0.5"))
FACEOFF_SHARE_SCALING_ENABLED = os.environ.get("FACEOFF_SHARE_SCALING_ENABLED", "True") == "True"
FACEOFF_SHARE_WINDOW_GAMES = int(os.environ.get("FACEOFF_SHARE_WINDOW_GAMES", "5"))

# --- API Tokens (with environment variable fallbacks) ─────────────────────────
API_TOKEN_STATS = os.environ.get("PLL_STATS_API_TOKEN", "N)eIKy1rZ%/%fm1WhM7tuVcrR*UIsc")
API_TOKEN_ROSTER = os.environ.get("PLL_ROSTER_API_TOKEN", "2<b}_K/x8JU1mn/")

# --- F2P Leaderboard & Rival Scraping ---
F2P_LEADERBOARD_GROUP_ID = int(os.environ.get("F2P_LEADERBOARD_GROUP_ID", 51185))
F2P_LOCAL_LEAGUE_GROUP_ID = int(os.environ.get("F2P_LOCAL_LEAGUE_GROUP_ID", 53205))
F2P_CONSENSUS_WEIGHT = float(os.environ.get("F2P_CONSENSUS_WEIGHT", 0.2))
F2P_FIREBASE_ID_TOKEN = os.environ.get("F2P_FIREBASE_ID_TOKEN", "")
F2P_MY_TEAM_NAME = os.environ.get("F2P_MY_TEAM_NAME", "SogMutts")

