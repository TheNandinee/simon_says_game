"""
Simon Says — Game Logic (State Machine)
"""

import time
import random
from typing import Optional

from src.game.constants import (
    ACTION_WAVE, ACTION_CLAP, ALL_ACTIONS,
    INSTRUCTION_TIME_EASY, INSTRUCTION_TIME_MEDIUM, INSTRUCTION_TIME_HARD,
    POINTS_CORRECT, POINTS_STREAK_BONUS, STREAK_THRESHOLD,
    STARTING_LIVES, DIFFICULTY_STEP, SIMON_SAYS_PROBABILITY,
    STATE_IDLE, STATE_COUNTDOWN, STATE_PLAYING, STATE_WAITING,
    STATE_FEEDBACK, STATE_GAME_OVER,
    FEEDBACK_DURATION, COUNTDOWN_DURATION,
)


class Instruction:
    def __init__(self, action: str, simon_says: bool):
        self.action     = action
        self.simon_says = simon_says
        self.created_at = time.time()

    @property
    def display_text(self) -> str:
        base = self.action.upper()
        return f"Simon says {base}!" if self.simon_says else f"{base}!"

    @property
    def is_trap(self) -> bool:
        return not self.simon_says


class ActionResult:
    CORRECT   = "correct"
    WRONG     = "wrong"
    TRAP_FAIL = "trap_fail"
    TRAP_PASS = "trap_pass"
    TIMEOUT   = "timeout"

    def __init__(self, kind: str, points: int, message: str, lives_lost: int = 0):
        self.kind       = kind
        self.points     = points
        self.message    = message
        self.lives_lost = lives_lost

    @property
    def is_positive(self) -> bool:
        return self.kind in (self.CORRECT, self.TRAP_PASS)


class SimonSaysGame:
    def __init__(self):
        self._state           = STATE_IDLE
        self._score           = 0
        self._lives           = STARTING_LIVES
        self._streak          = 0
        self._correct_count   = 0
        self._round_number    = 0
        self._difficulty      = 0
        self._instruction: Optional[Instruction]  = None
        self._last_result: Optional[ActionResult] = None
        self._state_entered_at: float = 0.0
        self._action_submitted        = "__none__"
        self._history: list           = []

    # ── Public API ─────────────────────────────────────────────────────

    def start(self):
        self._score           = 0
        self._lives           = STARTING_LIVES
        self._streak          = 0
        self._correct_count   = 0
        self._round_number    = 0
        self._difficulty      = 0
        self._instruction     = None
        self._last_result     = None
        self._history         = []
        self._enter_state(STATE_COUNTDOWN)

    def submit_action(self, action: Optional[str]):
        if self._state == STATE_WAITING and self._action_submitted == "__none__":
            self._action_submitted = action

    def tick(self) -> dict:
        now     = time.time()
        elapsed = now - self._state_entered_at

        if self._state == STATE_COUNTDOWN:
            if elapsed >= COUNTDOWN_DURATION:
                self._next_round()

        elif self._state == STATE_PLAYING:
            if elapsed >= 0.8:
                self._enter_state(STATE_WAITING)

        elif self._state == STATE_WAITING:
            time_limit = self._get_time_limit()
            action_in  = self._action_submitted
            if action_in != "__none__":
                result = self._evaluate(action_in)
                self._apply_result(result)
                self._enter_state(STATE_FEEDBACK)
            elif elapsed >= time_limit:
                result = self._evaluate(None)
                self._apply_result(result)
                self._enter_state(STATE_FEEDBACK)

        elif self._state == STATE_FEEDBACK:
            if elapsed >= FEEDBACK_DURATION:
                if self._lives <= 0:
                    self._enter_state(STATE_GAME_OVER)
                else:
                    self._next_round()

        return self._snapshot(now)

    # ── Internal state machine ─────────────────────────────────────────

    def _enter_state(self, new_state: str):
        self._state            = new_state
        self._state_entered_at = time.time()
        if new_state == STATE_WAITING:
            self._action_submitted = "__none__"

    def _next_round(self):
        self._round_number += 1
        self._difficulty    = min(2, self._correct_count // DIFFICULTY_STEP)
        self._instruction   = self._generate_instruction()
        self._enter_state(STATE_PLAYING)

    def _generate_instruction(self) -> Instruction:
        action     = random.choice(ALL_ACTIONS)
        simon_says = random.random() < SIMON_SAYS_PROBABILITY
        return Instruction(action=action, simon_says=simon_says)

    def _get_time_limit(self) -> float:
        return [INSTRUCTION_TIME_EASY, INSTRUCTION_TIME_MEDIUM, INSTRUCTION_TIME_HARD][self._difficulty]

    # ── Evaluation ─────────────────────────────────────────────────────

    def _evaluate(self, action: Optional[str]) -> ActionResult:
        inst = self._instruction
        if inst is None:
            return ActionResult(ActionResult.WRONG, 0, "No instruction?", lives_lost=1)

        player_acted = action is not None

        if inst.is_trap:
            if player_acted:
                return ActionResult(
                    kind       = ActionResult.TRAP_FAIL,
                    points     = 0,
                    message    = f"Oops! Simon didn't say {inst.action.upper()}!",
                    lives_lost = 1,
                )
            else:
                return ActionResult(
                    kind    = ActionResult.TRAP_PASS,
                    points  = POINTS_CORRECT + self._streak_bonus(),
                    message = "Nice! You ignored the trap! 🎯",
                )

        if not player_acted:
            return ActionResult(
                kind       = ActionResult.TIMEOUT,
                points     = 0,
                message    = f"Too slow! Should have {inst.action.upper()}ed!",
                lives_lost = 1,
            )

        if action == inst.action:
            return ActionResult(
                kind    = ActionResult.CORRECT,
                points  = POINTS_CORRECT + self._streak_bonus(),
                message = self._positive_message(action),
            )
        else:
            return ActionResult(
                kind       = ActionResult.WRONG,
                points     = 0,
                message    = f"Wrong! Needed {inst.action.upper()}, got {action.upper()}",
                lives_lost = 1,
            )

    def _streak_bonus(self) -> int:
        if self._streak > 0 and self._streak % STREAK_THRESHOLD == 0:
            return POINTS_STREAK_BONUS * (self._streak // STREAK_THRESHOLD)
        return 0

    def _positive_message(self, action: str) -> str:
        msgs = {
            ACTION_WAVE: ["Great wave! 👋", "Smooth! 👋", "Wave on! 👋"],
            ACTION_CLAP: ["Clap clap! 👏", "Nice clap! 👏", "Loud and clear! 👏"],

        }
        return random.choice(msgs.get(action, ["Correct! ✅"]))

    def _apply_result(self, result: ActionResult):
        self._last_result  = result
        self._score       += result.points
        self._lives       -= result.lives_lost
        if result.is_positive:
            self._streak        += 1
            self._correct_count += 1
        else:
            self._streak = 0
        self._history.append({
            "round"       : self._round_number,
            "instruction" : self._instruction.display_text if self._instruction else "",
            "result_kind" : result.kind,
            "points"      : result.points,
            "message"     : result.message,
        })

    # ── Snapshot ───────────────────────────────────────────────────────

    def _snapshot(self, now: float) -> dict:
        elapsed    = now - self._state_entered_at
        time_limit = self._get_time_limit()
        time_left  = max(0.0, time_limit - elapsed) if self._state == STATE_WAITING else 0.0
        cd_left    = max(0.0, COUNTDOWN_DURATION - elapsed) if self._state == STATE_COUNTDOWN else 0.0

        return {
            "state"          : self._state,
            "round"          : self._round_number,
            "difficulty"     : ["Easy", "Medium", "Hard"][self._difficulty],
            "instruction"    : self._instruction.display_text if self._instruction else "",
            "action_required": self._instruction.action       if self._instruction else "",
            "is_trap"        : self._instruction.is_trap      if self._instruction else False,
            "simon_says"     : self._instruction.simon_says   if self._instruction else False,
            "score"          : self._score,
            "lives"          : self._lives,
            "streak"         : self._streak,
            "max_lives"      : STARTING_LIVES,
            "time_left"      : round(time_left, 2),
            "time_limit"     : time_limit,
            "countdown_left" : round(cd_left, 1),
            "last_result"    : {
                "kind"       : self._last_result.kind        if self._last_result else "",
                "message"    : self._last_result.message     if self._last_result else "",
                "points"     : self._last_result.points      if self._last_result else 0,
                "is_positive": self._last_result.is_positive if self._last_result else False,
            },
            "history"        : list(self._history[-5:]),
        }

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def score(self) -> int:
        return self._score

    @property
    def lives(self) -> int:
        return self._lives

    @property
    def is_over(self) -> bool:
        return self._state == STATE_GAME_OVER

    @property
    def history(self) -> list:
        return list(self._history)
