"""Compatibilidad de RAGAS con Python 3.14.

RAGAS 0.2.x aplica `nest_asyncio` al importarse, lo que en Python 3.14 hace que
`asyncio.current_task()` devuelva None y rompe `asyncio.wait_for`. Como no
necesitamos bucles anidados, desactivamos ese parche antes de importar RAGAS.
"""
import sys
import types

if sys.version_info >= (3, 14) and "nest_asyncio" not in sys.modules:
    _stub = types.ModuleType("nest_asyncio")
    _stub.apply = lambda loop=None: None  # type: ignore[attr-defined]
    sys.modules["nest_asyncio"] = _stub
