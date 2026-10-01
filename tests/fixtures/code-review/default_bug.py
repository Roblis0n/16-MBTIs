"""Synthetic mutable-default defect: independent calls share a list."""
def add_item(item, items=[]):
    items.append(item)
    return items
