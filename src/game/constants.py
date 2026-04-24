# ── Actions ────────────────────────────────────────────────────────────
ACTION_WAVE  = "wave"
ACTION_CLAP  = "clap"
ACTION_MEOW  = "meow"

ALL_ACTIONS = [ACTION_WAVE, ACTION_CLAP, ACTION_MEOW]

# ── Instruction timing (seconds) ───────────────────────────────────────
INSTRUCTION_TIME_EASY   = 8.0
INSTRUCTION_TIME_MEDIUM = 6.0
INSTRUCTION_TIME_HARD   = 4.5

# ── Scoring ────────────────────────────────────────────────────────────
POINTS_CORRECT      = 10
POINTS_STREAK_BONUS = 5
STREAK_THRESHOLD    = 3

# ── Lives ──────────────────────────────────────────────────────────────
STARTING_LIVES = 5

# ── Difficulty progression ─────────────────────────────────────────────
DIFFICULTY_STEP = 10

# ── Trap probability ───────────────────────────────────────────────────
SIMON_SAYS_PROBABILITY = 0.80

# ── Game states ────────────────────────────────────────────────────────
STATE_IDLE      = "idle"
STATE_COUNTDOWN = "countdown"
STATE_PLAYING   = "playing"
STATE_WAITING   = "waiting"
STATE_FEEDBACK  = "feedback"
STATE_GAME_OVER = "game_over"

# ── Timing ─────────────────────────────────────────────────────────────
FEEDBACK_DURATION  = 1.2
COUNTDOWN_DURATION = 3.0
