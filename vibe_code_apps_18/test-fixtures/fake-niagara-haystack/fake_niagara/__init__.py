"""A small, dependency-free Project Haystack server for BAS/FDD experiments."""

__all__ = ["FakeBASData", "FakeHaystackServer", "ServerConfig"]


def __getattr__(name):
    # Lazy imports keep ``python -m fake_niagara.server`` warning-free.
    if name == "FakeBASData":
        from .data import FakeBASData
        return FakeBASData
    if name in {"FakeHaystackServer", "ServerConfig"}:
        from .server import FakeHaystackServer, ServerConfig
        return {"FakeHaystackServer": FakeHaystackServer, "ServerConfig": ServerConfig}[name]
    raise AttributeError(name)
