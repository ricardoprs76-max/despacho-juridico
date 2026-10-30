"""Names of the built-in tools, kept dependency-free so the config schema can use them."""

TOOL_NAMES: frozenset[str] = frozenset({"buscar_documentos", "registrar_en_hoja", "enviar_correo"})
SIDE_EFFECT_TOOLS: frozenset[str] = frozenset({"registrar_en_hoja", "enviar_correo"})
