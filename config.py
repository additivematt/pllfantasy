import os

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

# Opponent-Stratified Bootstrap: Weights MC bootstrap draws by opponent
# defensive similarity using a Gaussian kernel. Rolled back after Baseline 3
# showed degradation on 2026 and scale conflicts with game pace features.
OPPONENT_STRATIFIED_BOOTSTRAP = False
OPPONENT_BOOTSTRAP_SIGMA = 0.15

# MC Ceiling Clamp Multiplier: Caps simulated player scores at
# max_historical * this value. Set to None to disable clamping entirely.
CEILING_CLAMP_MULTIPLIER = None  # Was 1.15; currently no clamp in production code

# Salary as Feature: Feed normalized salary percentile into the GBDT model
# as a market consensus signal. Not yet implemented.
SALARY_AS_FEATURE = False

# Correlation Copula: Use the Gaussian copula correlation matrix in MC sims.
# Enabled by default; can be disabled for independent simulation comparison.
CORRELATION_COPULA_ENABLED = True

# --- API Tokens (with environment variable fallbacks) ─────────────────────────
API_TOKEN_STATS = os.environ.get("PLL_STATS_API_TOKEN", "N)eIKy1rZ%/%fm1WhM7tuVcrR*UIsc")
API_TOKEN_ROSTER = os.environ.get("PLL_ROSTER_API_TOKEN", "2<b}_K/x8JU1mn/")
