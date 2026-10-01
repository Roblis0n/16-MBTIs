"""Public, redacted error protocol. No input values are interpolated in errors."""
class MindsError(Exception):
    def __init__(self, code, message, *, layer="semantic", next_step="修正指定字段后重新提交。", retryable=False, side_effect_status="none"):
        super().__init__(message)
        self.code, self.message, self.layer = code, message, layer
        self.next_step, self.retryable = next_step, retryable
        self.side_effect_status = side_effect_status

    @property
    def exit_code(self):
        if self.code in {"E_BUDGET_TOO_SMALL", "E_BUDGET_EXHAUSTED"}: return 4
        if self.code in {"E_CAPABILITY", "E_PERMISSION"}: return 3
        if self.code == "E_INTERNAL": return 5
        return 2

    def as_dict(self):
        return {"status": "error", "error": {"machine_code": self.code,
            "public_message": self.message, "layer": self.layer,
            "retryable": self.retryable, "side_effect_status": self.side_effect_status,
            "safe_next_step": self.next_step}}

def fail(code, message, **kwargs):
    raise MindsError(code, message, **kwargs)
