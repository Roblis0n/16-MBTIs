"""Synthetic matched control: remove the timer registered by this mount."""
active = []
def mount():
    active.append('timer')
def unmount():
    if active:
        active.pop()
