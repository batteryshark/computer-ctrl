"""Tool results in the one shape every harness forwards: a JSON text block plus at most one image."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolResult:
    data: dict = field(default_factory=dict)
    image: bytes | None = None
    mime: str = "image/png"
    is_error: bool = False


class ToolError(Exception):
    """An expected failure the model can act on: code, message and a hint for what to do next."""

    def __init__(self, code: str, message: str, hint: str | None = None, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.extra = extra

    def result(self) -> ToolResult:
        data = {"error": self.code, "message": self.message, **self.extra}
        if self.hint:
            data["hint"] = self.hint
        return ToolResult(data=data, is_error=True)
