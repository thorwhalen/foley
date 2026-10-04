"""Cost: what a call will cost before it is made, and a cumulative cap on a run (#57).

Three pieces, each small:

* **Pricing as data.** Each source declares ``SOURCE_CONFIG['pricing']`` — the falaw
  convention (``unit``, ``amount_usd``, plus the ``source`` and ``seen`` date the price
  was read from). :func:`estimate_call` turns it into dollars for one call, and returns
  ``None`` — never ``0.0`` — when the cost cannot be known (no pricing, or a
  per-second price with no duration and no maximum).
* **A run-scoped budget.** :func:`spend_scope` makes a
  :class:`~foley.agent.policy.Budget` the active one for a ``find`` / ``score`` /
  ``generate`` run; :func:`authorize` is called before every paid call and refuses the
  first one that would take the run past ``max_usd`` (default :data:`DEFAULT_MAX_USD`,
  $1 — maintainer decision on #57), or whose cost is unknown unless the budget
  approves unknown costs.
* **Two errors.** :class:`BudgetExceeded` and its subclass :class:`CostApprovalRequired`.

Stdlib-only.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

__all__ = [
    "DEFAULT_MAX_USD",
    "APPROVE_UNKNOWN_COST_ENV",
    "BudgetExceeded",
    "CostApprovalRequired",
    "estimate_call",
    "spend_scope",
    "active_budget",
    "authorize",
    "charge",
]

#: The default cumulative cap for one run (a ``find`` / ``score`` / ``generate`` call).
DEFAULT_MAX_USD: float = 1.0

#: Set to 1 to approve calls whose cost is unknown, for every run that does not say.
APPROVE_UNKNOWN_COST_ENV = "FOLEY_APPROVE_UNKNOWN_COST"

_ACTIVE_BUDGET: "ContextVar[object | None]" = ContextVar("foley_budget", default=None)


class BudgetExceeded(RuntimeError):
    """Raised before a paid call that would take the run past its ``max_usd`` cap."""


class CostApprovalRequired(BudgetExceeded):
    """Raised before a call whose cost is unknown, when the budget has not approved that."""


def estimate_call(config: dict, **affordances) -> Optional[float]:
    """The USD cost of one call to the source ``config`` declares, or ``None`` if unknown.

    ``config['pricing']`` units:

    * ``'free'`` (local inference, a free API tier) → ``0.0``;
    * ``'per_call'`` → ``amount_usd``;
    * ``'per_second'`` → ``amount_usd`` × the requested ``duration``, or × the backend's
      ``native_defaults['duration_max_s']`` when the duration is left to the backend
      (an upper bound), else ``None``.

    Args:
        config: A ``SOURCE_CONFIG``.
        **affordances: The canonical affordances of the call (``duration``, …).
    """
    pricing = config.get("pricing")
    if not pricing:
        return None
    unit = pricing.get("unit")
    amount = pricing.get("amount_usd")
    if unit == "free":
        return 0.0
    if amount is None:
        return None
    if unit == "per_call":
        return float(amount)
    if unit == "per_second":
        seconds = affordances.get("duration")
        if seconds is None:
            seconds = (config.get("native_defaults") or {}).get("duration_max_s")
        return None if seconds is None else float(amount) * float(seconds)
    return None


def active_budget():
    """The :class:`~foley.agent.policy.Budget` of the current run, or ``None``."""
    return _ACTIVE_BUDGET.get()


@contextmanager
def spend_scope(budget=None):
    """Make ``budget`` the active one for the block (nested scopes keep the outer one).

    A ``find`` that generates opens one scope; the ``generate`` calls inside it charge
    the same budget, so the cap is cumulative across the whole run. With no
    ``budget`` and no active one, a fresh default :class:`~foley.agent.policy.Budget`
    is used.

    Yields:
        The budget in force.
    """
    outer = _ACTIVE_BUDGET.get()
    if outer is not None:
        yield outer
        return
    if budget is None:
        from .agent.policy import Budget

        budget = Budget()
    token = _ACTIVE_BUDGET.set(budget)
    try:
        yield budget
    finally:
        _ACTIVE_BUDGET.reset(token)


def authorize(estimate_usd: Optional[float], *, what: str) -> None:
    """Refuse a paid call before it is made if the active run cannot afford it.

    No active budget means a fresh default one (this single call is the run).

    Raises:
        CostApprovalRequired: If ``estimate_usd`` is ``None`` and unknown costs are not
            approved (``Budget.approve_unknown_cost`` or ``$FOLEY_APPROVE_UNKNOWN_COST``).
        BudgetExceeded: If the run's spend plus ``estimate_usd`` exceeds ``max_usd``.
    """
    budget = _ACTIVE_BUDGET.get()
    if budget is None:
        from .agent.policy import Budget

        budget = Budget()
    budget.authorize(estimate_usd, what=what)


def charge(usd: Optional[float]) -> None:
    """Record ``usd`` against the active run's budget (a no-op with no active run)."""
    budget = _ACTIVE_BUDGET.get()
    if budget is not None:
        budget.charge(usd)
