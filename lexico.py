from __future__ import annotations

from dataclasses import dataclass
import re


KEYWORDS = {
    "inicio": "INICIO",
    "fin": "FIN",
    "si": "SI",
    "entonces": "ENTONCES",
    "finsi": "FINSI",
    "escribir": "ESCRIBIR",
    "funcion": "FUNCION",
    "retornar": "RETORNAR",
    "finfuncion": "FINFUNCION",
}


TOKEN_SPEC = (
    ("NEWLINE", r"\r?\n"),
    ("COMMENT", r"#.*"),
    ("SKIP", r"[ \t]+"),
    ("REL_OP", r"<=|>=|==|!=|<|>"),
    ("ASSIGN", r"="),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("STAR", r"\*"),
    ("SLASH", r"/"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("COMMA", r","),
    ("NUMBER", r"\d+"),
    ("IDENTIFIER", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("MISMATCH", r"."),
)


TOKEN_REGEX = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC)
)


@dataclass(frozen=True, slots=True)
class Token:
    type: str
    value: str
    line: int
    column: int

    def as_tuple(self) -> tuple[str, str]:
        return (self.type, self.value)


def lex(source: str) -> list[Token]:
    tokens: list[Token] = []
    line = 1
    line_start = 0

    for match in TOKEN_REGEX.finditer(source):
        token_type = match.lastgroup
        value = match.group()
        column = match.start() - line_start + 1

        if token_type == "NEWLINE":
            tokens.append(Token("NEWLINE", "\\n", line, column))
            line += value.count("\n")
            line_start = match.end()
            continue

        if token_type in {"SKIP", "COMMENT"}:
            continue

        if token_type == "IDENTIFIER":
            normalized = value.lower()
            keyword_type = KEYWORDS.get(normalized)
            if keyword_type is not None:
                tokens.append(Token(keyword_type, normalized, line, column))
            else:
                tokens.append(Token("IDENTIFIER", value, line, column))
            continue

        if token_type == "MISMATCH":
            raise SyntaxError(
                f"Caracter inesperado {value!r} en linea {line}, columna {column}"
            )

        tokens.append(Token(token_type, value, line, column))

    tokens.append(Token("EOF", "", line, 1))
    return tokens


def tokens_by_line(tokens: list[Token]) -> dict[int, list[tuple[str, str]]]:
    grouped: dict[int, list[tuple[str, str]]] = {}

    for token in tokens:
        if token.type == "EOF":
            continue
        grouped.setdefault(token.line, []).append(token.as_tuple())

    return grouped


def token_tuples(tokens: list[Token]) -> list[tuple[str, str]]:
    return [token.as_tuple() for token in tokens if token.type != "EOF"]
