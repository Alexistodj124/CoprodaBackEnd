from agent.llm import Claude  # noqa: F401
from agent.runtime import Agente  # noqa: F401
from agent.session import Sesion  # noqa: F401
from settings import settings


def crear_agente(ctx, sesion, on_tool=None):
    """Arma el agente segun AGENTE_BACKEND: "suscripcion" (Claude Code) o "api"."""
    if settings.BACKEND == "api":
        return Agente(Claude(), ctx, sesion, on_tool=on_tool)
    from agent.suscripcion import AgenteSuscripcion  # requiere claude-agent-sdk

    return AgenteSuscripcion(ctx, sesion, on_tool=on_tool)
