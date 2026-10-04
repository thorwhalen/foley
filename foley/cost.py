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
    "scoped_iter",
    "active_budget",
    "authorize",
    "charge",
]

#: The default cumulative cap for one run (a ``find`` / ``score`` / ``generate`` call).
DEFAULT_MAX_USD: float = 1.0

#: Set to 1 to approve calls whose cost is unknown, for every run that does not say.
APPROVE_UNKNOWN_COST_ENV = "FOLEY_APPROVE_UNKNOWN_COST"

#: The budgets in force, outermost first (see :func:`spend_scope`).
_ACTIVE_BUDGET: "ContextVar[tuple]" = ContextVar("foley_budget", default=())


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


def _stack() -> tuple:
    return _ACTIVE_BUDGET.get() or ()


def active_budget():
    """The innermost :class:`~foley.agent.policy.Budget` of the current run, or ``None``."""
    stack = _stack()
    return stack[-1] if stack else None


@contextmanager
def spend_scope(budget=None):
    """Put ``budget`` in force for the block; every enclosing budget stays in force too.

    Budgets stack: a paid call must fit **every** budget in force (so an explicit,
    stricter ``budget`` inside a ``find`` / ``score`` run still applies) and is charged
    to each of them once. With no ``budget``: inside a run, nothing changes; outside
    one, a fresh default :class:`~foley.agent.policy.Budget` is used ($1).

    Yields:
        The innermost budget in force.
    """
    stack = _stack()
    if budget is None and stack:
        yield stack[-1]
        return
    if budget is None:
        from .agent.policy import Budget

        budget = Budget()
    if any(b is budget for b in stack):
        yield budget
        return
    token = _ACTIVE_BUDGET.set((*stack, budget))
    try:
        yield budget
    finally:
        _ACTIVE_BUDGET.reset(token)


def scoped_iter(iterator_factory, budget=None):
    """Iterate ``iterator_factory()`` with ``budget`` in force only while it runs.

    A generator that holds a :func:`spend_scope` across ``yield`` would leave its
    budget active in the caller's context between items (so the caller's own calls, or
    another interleaved stream, would charge it). This re-enters the scope for each
    step and leaves it before handing the item out.
    """
    stack = _stack()
    if budget is None:
        if stack:
            budget = stack[-1]
        else:
            from .agent.policy import Budget

            budget = Budget()
    iterator = None
    while True:
        with spend_scope(budget):
            if iterator is None:
                iterator = iter(iterator_factory())
            try:
                item = next(iterator)
            except StopIteration:
                return
        yield item


def authorize(estimate_usd: Optional[float], *, what: str) -> None:
    """Refuse a paid call before it is made if any budget in force cannot afford it.

    With no budget in force, a fresh default one (this single call is the run).

    Raises:
        CostApprovalRequired: If ``estimate_usd`` is ``None`` and a budget in force has
            not approved unknown costs (``Budget.approve_unknown_cost`` /
            ``$FOLEY_APPROVE_UNKNOWN_COST``).
        BudgetExceeded: If a budget's spend plus ``estimate_usd`` exceeds its ``max_usd``.
    """
    stack = _stack()
    if not stack:
        from .agent.policy import Budget

        stack = (Budget(),)
    for budget in stack:
        budget.authorize(estimate_usd, what=what)


def charge(usd: Optional[float]) -> None:
    """Record ``usd`` against every budget in force (a no-op outside any run)."""
    for budget in _stack():
        budget.charge(usd)
