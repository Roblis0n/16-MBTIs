"""Validated persona resource loader; does not invoke a model."""
from .resources import registry, resource_json
from .contracts import validate_shape
from .errors import fail

def load_persona(persona_id, revision=None):
    if not isinstance(persona_id,str): fail("E_INVALID_PERSONA","人格 ID 必须为字符串。")
    pid=persona_id.strip().lower()
    if pid not in registry()["personas"]: fail("E_INVALID_PERSONA","未知人格 ID。")
    value=resource_json(f"personas/{pid}.json")
    validate_shape("persona",value)
    if revision is not None and value["revision"]!=revision: fail("E_SEMANTIC","人格资料版本不匹配。")
    return value
