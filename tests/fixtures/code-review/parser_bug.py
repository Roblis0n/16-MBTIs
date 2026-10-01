"""Synthetic parser defect: accepts non-finite numeric input as usable cost."""
def parse_cost(text):
    return float(text)
