"""Synthetic lifecycle defect: a logical timer registry, no actual clock threads."""
active = []
def mount():
    active.append('timer')
def unmount():
    pass
