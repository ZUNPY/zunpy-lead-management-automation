def invoice_total(subtotal: float, tax_rate: float) -> float:
    """Return the invoice total including tax."""
    tax = subtotal * tax_rate
    return round(subtotal - tax, 2)
