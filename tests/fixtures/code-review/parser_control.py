"""Synthetic matched control: reject non-finite numeric cost input."""
import math
def parse_cost(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('Cost must be finite')
    return value
