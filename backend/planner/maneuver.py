"""Adapter for the supplied maneuver-time model (lookup table from scenario.json)."""

from collections.abc import Mapping

TransitionTable = Mapping[str, Mapping[str, float]]


class UnknownTransitionError(KeyError):
    """Raised for a missing or unknown target pair: an input error, never a zero-duration maneuver."""


def transition_seconds(table: TransitionTable, previous_target_id: str, next_target_id: str) -> float:
    """Return the nonnegative, possibly asymmetric maneuver duration from one target to another."""
    try:
        value = float(table[previous_target_id][next_target_id])
    except KeyError:
        raise UnknownTransitionError(f"no transition {previous_target_id!r} -> {next_target_id!r}") from None
    if value < 0:
        raise ValueError(f"negative transition {previous_target_id!r} -> {next_target_id!r}: {value}")
    return value
