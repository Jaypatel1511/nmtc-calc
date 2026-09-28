"""Money formatting with the sign before the currency symbol: -$1,234, not $-1,234."""


def money(value: float, spec: str = ",.0f") -> str:
    """Format ``value`` as dollars with ``spec``, sign first: money(-2.5, ',.2f') == '-$2.50'."""
    text = format(abs(value), spec)
    return ("-$" if value < 0 else "$") + text
