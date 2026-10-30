"""MCP server: the company's agent as tools for any MCP client (Claude Desktop, IDEs...).

Side-effecting tools are never exposed directly; an MCP client reaches them only through
`preguntar`, which stops at the same confirmation as the chat and the HTTP API.
"""

from collections.abc import Callable

from mcp.server import MCPServer

from agentes.agent import Agent, AgentError, AgentReply

DEFAULT_THREAD = "mcp"
PENDING_TEXT = "Acción pendiente: {description}. Llama a confirmar con aprobar=true o false."
MODEL_FAILED = "No se pudo obtener respuesta del modelo: {error}"


def _answer(action: Callable[[], AgentReply]) -> str:
    """Run one exchange; errors come back as Spanish text, never as a traceback."""
    try:
        reply = action()
    except ValueError as exc:
        return str(exc)
    except AgentError as exc:
        return MODEL_FAILED.format(error=exc)
    if reply.pending is not None:
        return PENDING_TEXT.format(description=reply.pending.description.rstrip("."))
    return reply.text


def build_mcp_server(agent: Agent) -> MCPServer:
    """An MCP server bound to an open agent; the caller closes the agent."""
    server: MCPServer = MCPServer(
        name=agent.config.company_name,
        instructions=(
            f"Asistente de {agent.config.company_name} ({agent.config.sector}). "
            "Usa preguntar para hablar con el agente; si responde con una acción pendiente, "
            "pregunta al usuario y llama a confirmar con su respuesta."
        ),
    )

    @server.tool(description="Envía un mensaje al agente de la empresa y devuelve su respuesta.")
    def preguntar(mensaje: str, conversacion: str = DEFAULT_THREAD) -> str:
        return _answer(lambda: agent.ask(conversacion, mensaje))

    @server.tool(description="Aprueba (true) o cancela (false) la acción pendiente del agente.")
    def confirmar(aprobar: bool, conversacion: str = DEFAULT_THREAD) -> str:
        return _answer(lambda: agent.confirm(conversacion, aprobar))

    descriptions = {tool.name: tool.description for tool in agent.tools}

    if "buscar_documentos" in descriptions:

        def buscar_documentos(consulta: str) -> str:
            return agent.run_tool("buscar_documentos", {"consulta": consulta})

        server.add_tool(buscar_documentos, description=descriptions["buscar_documentos"])

    if "calcular_plazo" in descriptions:

        def calcular_plazo(
            actuacion: str, fecha_notificacion: str, notificacion_electronica: bool = False
        ) -> str:
            args = {
                "actuacion": actuacion,
                "fecha_notificacion": fecha_notificacion,
                "notificacion_electronica": notificacion_electronica,
            }
            return agent.run_tool("calcular_plazo", args)

        server.add_tool(calcular_plazo, description=descriptions["calcular_plazo"])

    return server
