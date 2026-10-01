"""Synthetic matched control: each omitted argument gets a fresh list."""
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
