"""El proyecto debe funcionar en Python 3.11 (versión del devcontainer de Codespaces).

Python 3.12 permite cosas en f-strings que 3.11 rechaza con SyntaxError
(barras invertidas o comillas iguales dentro de {...}). Esta prueba las detecta
aunque se ejecute en una versión más nueva.
"""
from __future__ import annotations

import io
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(sys.version_info < (3, 12), reason="En 3.11 el propio intérprete ya lo detecta al importar")
def test_fstrings_compatibles_con_python_311():
    problems = []
    for path in list((ROOT / "app").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        toks = tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline)
        stack: list[dict] = []
        for t in toks:
            if t.type == tokenize.FSTRING_START:
                q = t.string.lstrip("rRfFbBuU")
                if stack and stack[-1]["depth"] > 0 and len(stack[-1]["q"]) == 1 and q[0] == stack[-1]["q"]:
                    problems.append(f"{path.name}:{t.start[0]} f-string anidada con las mismas comillas")
                stack.append({"q": q[:3] if q[:3] in ('"""', "'''") else q[0], "depth": 0})
            elif t.type == tokenize.FSTRING_END:
                stack.pop()
            elif stack and t.type == tokenize.OP and t.string in "{}":
                stack[-1]["depth"] += 1 if t.string == "{" else -1
            elif stack and stack[-1]["depth"] > 0 and t.type == tokenize.STRING:
                if "\\" in t.string:
                    problems.append(f"{path.name}:{t.start[0]} barra invertida dentro de {{...}}")
                q = stack[-1]["q"]
                if len(q) == 1 and t.string.lstrip("rRbBuU")[:1] == q:
                    problems.append(f"{path.name}:{t.start[0]} comillas iguales dentro de {{...}}")
    assert not problems, "Sintaxis incompatible con Python 3.11:\n" + "\n".join(problems)
