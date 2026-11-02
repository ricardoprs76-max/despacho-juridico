"""Pydantic schema for a company's agent configuration."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agentes.tool_names import TOOL_NAMES

NO_INVENT_LINE = "Si no sabes la respuesta, dilo claramente; nunca inventes datos."


class ModelConfig(BaseModel):
    """Which LLM provider and model the agent uses."""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["gemini", "anthropic", "openai"] = "gemini"
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0, le=1)


class AgentConfig(BaseModel):
    """Everything that makes one company's agent different from another's."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    company_name: str
    fictitious: bool = Field(
        default=False, description="True for example companies; the web chat says so."
    )
    sector: str
    language: str = "es"
    tone: str
    rules: list[str] = []
    model: ModelConfig = ModelConfig()
    tools: list[str] = []
    confirm_tools: list[str] = []
    knowledge_dir: Path | None = None

    @field_validator("tools")
    @classmethod
    def _tools_exist(cls, tools: list[str]) -> list[str]:
        unknown = [name for name in tools if name not in TOOL_NAMES]
        if unknown:
            raise ValueError("Herramienta desconocida: " + ", ".join(unknown))
        return tools

    @model_validator(mode="after")
    def _confirm_tools_are_enabled(self) -> "AgentConfig":
        unknown = sorted(set(self.confirm_tools) - set(self.tools))
        if unknown:
            raise ValueError(
                "confirm_tools incluye herramientas que no están en tools: " + ", ".join(unknown)
            )
        return self

    def system_prompt(self) -> str:
        """Build the Spanish system prompt sent to the model on every turn."""
        lines = [
            f"Eres el asistente virtual de {self.company_name}, una empresa del sector "
            f"{self.sector}.",
            f"Tono: {self.tone}.",
            "Responde siempre en español.",
        ]
        if self.rules:
            lines.append("Reglas que debes cumplir:")
            lines.extend(f"- {rule}" for rule in self.rules)
        lines.append(NO_INVENT_LINE)
        return "\n".join(lines)
