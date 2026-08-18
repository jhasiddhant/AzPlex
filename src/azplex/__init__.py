"""azplex - MCP server for Azure, Microsoft Fabric, and Azure DevOps."""

__version__ = "1.0.1"
__all__ = ["mcp", "main"]


def __getattr__(name):
    if name in ("mcp", "main"):
        from azplex.server import mcp, main
        globals()["mcp"] = mcp
        globals()["main"] = main
        return globals()[name]
    raise AttributeError(f"module 'azplex' has no attribute {name!r}")
