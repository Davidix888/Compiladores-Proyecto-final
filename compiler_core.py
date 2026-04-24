from __future__ import annotations

from dataclasses import dataclass
import re


KEYWORDS = {
    "funcion",
    "finfuncion",
    "inicio",
    "fin",
    "si",
    "entonces",
    "finsi",
    "retornar",
    "escribir",
}

TOKEN_REGEX = re.compile(
    r"""
    (?P<SPACE>\s+)
    |(?P<NUMBER>\d+)
    |(?P<OPERATOR>==|!=|>=|<=|[+\-*/<>==])
    |(?P<LPAREN>\()
    |(?P<RPAREN>\))
    |(?P<COMMA>,)
    |(?P<ASSIGN>=)
    |(?P<IDENTIFIER>[A-Za-z_][A-Za-z0-9_]*)
    |(?P<MISMATCH>.)
    """,
    re.VERBOSE,
)


class CompilerError(Exception):
    pass


@dataclass(slots=True)
class NumberLiteral:
    value: int


@dataclass(slots=True)
class Variable:
    name: str


@dataclass(slots=True)
class FunctionCall:
    name: str
    arguments: list[Expression]


@dataclass(slots=True)
class BinaryOperation:
    left: Expression
    operator: str
    right: Expression


Expression = NumberLiteral | Variable | FunctionCall | BinaryOperation


@dataclass(slots=True)
class Assignment:
    name: str
    expression: Expression


@dataclass(slots=True)
class Write:
    expression: Expression


@dataclass(slots=True)
class IfStatement:
    condition: Expression
    body: list[Statement]


@dataclass(slots=True)
class Return:
    expression: Expression


Statement = Assignment | Write | IfStatement | Return | FunctionCall


@dataclass(slots=True)
class FunctionDef:
    name: str
    parameters: list[str]
    body: list[Statement]


@dataclass(slots=True)
class Program:
    functions: list[FunctionDef]
    statements: list[Statement]


@dataclass(slots=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


def tokenize_expression(text: str, line: int) -> list[Token]:
    tokens: list[Token] = []

    for match in TOKEN_REGEX.finditer(text):
        kind = match.lastgroup
        value = match.group()
        column = match.start() + 1

        if kind == "SPACE":
            continue
        if kind == "MISMATCH":
            raise CompilerError(
                f"Token inesperado '{value}' en linea {line}, columna {column}."
            )
        if kind == "IDENTIFIER" and value in KEYWORDS:
            kind = "KEYWORD"
        if kind == "ASSIGN":
            kind = "OPERATOR"

        tokens.append(Token(kind, value, line, column))

    tokens.append(Token("EOF", "", line, len(text) + 1))
    return tokens


class ExpressionParser:
    def __init__(self, text: str, line: int) -> None:
        self.tokens = tokenize_expression(text, line)
        self.position = 0

    def parse(self) -> Expression:
        expression = self._comparison()
        self._expect("EOF")
        return expression

    def _current(self) -> Token:
        return self.tokens[self.position]

    def _advance(self) -> Token:
        token = self._current()
        self.position += 1
        return token

    def _expect(self, kind: str, value: str | None = None) -> Token:
        token = self._current()
        if token.kind != kind or (value is not None and token.value != value):
            expected = value if value is not None else kind
            raise CompilerError(
                f"Se esperaba {expected} en linea {token.line}, columna {token.column}, "
                f"pero se encontro '{token.value}'."
            )
        return self._advance()

    def _match_operator(self, *operators: str) -> str | None:
        token = self._current()
        if token.kind == "OPERATOR" and token.value in operators:
            self._advance()
            return token.value
        return None

    def _comparison(self) -> Expression:
        expression = self._addition()
        while operator := self._match_operator(">", "<", ">=", "<=", "==", "!="):
            expression = BinaryOperation(expression, operator, self._addition())
        return expression

    def _addition(self) -> Expression:
        expression = self._multiplication()
        while operator := self._match_operator("+", "-"):
            expression = BinaryOperation(expression, operator, self._multiplication())
        return expression

    def _multiplication(self) -> Expression:
        expression = self._primary()
        while operator := self._match_operator("*", "/"):
            expression = BinaryOperation(expression, operator, self._primary())
        return expression

    def _primary(self) -> Expression:
        token = self._current()

        if token.kind == "NUMBER":
            self._advance()
            return NumberLiteral(int(token.value))

        if token.kind == "IDENTIFIER":
            name = self._advance().value
            if self._current().kind == "LPAREN":
                self._advance()
                arguments: list[Expression] = []
                if self._current().kind != "RPAREN":
                    while True:
                        arguments.append(self._comparison())
                        if self._current().kind != "COMMA":
                            break
                        self._advance()
                self._expect("RPAREN")
                return FunctionCall(name, arguments)
            return Variable(name)

        if token.kind == "LPAREN":
            self._advance()
            expression = self._comparison()
            self._expect("RPAREN")
            return expression

        raise CompilerError(
            f"Expresion invalida en linea {token.line}, columna {token.column}."
        )


class LineParser:
    def __init__(self, source: str) -> None:
        raw_lines = source.splitlines()
        self.lines = [(index + 1, line.rstrip()) for index, line in enumerate(raw_lines)]
        self.position = 0

    def parse_program(self) -> Program:
        functions: list[FunctionDef] = []

        while self._peek_content().startswith("funcion "):
            functions.append(self._parse_function())

        self._expect_line("inicio")
        statements = self._parse_block({"fin"})
        self._expect_line("fin")

        if self._has_more_content():
            line_number, line = self._current()
            raise CompilerError(f"Contenido inesperado en linea {line_number}: '{line}'.")

        return Program(functions, statements)

    def _parse_function(self) -> FunctionDef:
        line_number, line = self._current()
        match = re.fullmatch(r"funcion\s+([A-Za-z_][A-Za-z0-9_]*)\((.*)\)", line.strip())
        if not match:
            raise CompilerError(f"Cabecera de funcion invalida en linea {line_number}.")

        name = match.group(1)
        params_text = match.group(2).strip()
        parameters = [item.strip() for item in params_text.split(",") if item.strip()]
        self.position += 1
        body = self._parse_block({"finfuncion"})
        self._expect_line("finfuncion")
        return FunctionDef(name, parameters, body)

    def _parse_block(self, end_tokens: set[str]) -> list[Statement]:
        statements: list[Statement] = []

        while self._has_more_content():
            line_number, line = self._current()
            content = line.strip()

            if content in end_tokens:
                break

            if content.startswith("si "):
                statements.append(self._parse_if())
                continue

            if content.startswith("escribir"):
                statements.append(self._parse_write())
                continue

            if content.startswith("retornar "):
                expression = parse_expression(content[len("retornar ") :], line_number)
                statements.append(Return(expression))
                self.position += 1
                continue

            if "=" in content:
                name, expression_text = content.split("=", 1)
                variable_name = name.strip()
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable_name):
                    raise CompilerError(
                        f"Nombre de variable invalido en linea {line_number}."
                    )
                expression = parse_expression(expression_text.strip(), line_number)
                statements.append(Assignment(variable_name, expression))
                self.position += 1
                continue

            expression = parse_expression(content, line_number)
            if not isinstance(expression, FunctionCall):
                raise CompilerError(
                    f"Sentencia no reconocida en linea {line_number}: '{content}'."
                )
            statements.append(expression)
            self.position += 1

        return statements

    def _parse_if(self) -> IfStatement:
        line_number, line = self._current()
        match = re.fullmatch(r"si\s*\((.*)\)\s*entonces", line.strip())
        if not match:
            raise CompilerError(f"Estructura de 'si' invalida en linea {line_number}.")

        condition = parse_expression(match.group(1).strip(), line_number)
        self.position += 1
        body = self._parse_block({"finsi"})
        self._expect_line("finsi")
        return IfStatement(condition, body)

    def _parse_write(self) -> Write:
        line_number, line = self._current()
        match = re.fullmatch(r"escribir\s*\((.*)\)", line.strip())
        if not match:
            raise CompilerError(f"Sentencia 'escribir' invalida en linea {line_number}.")
        expression = parse_expression(match.group(1).strip(), line_number)
        self.position += 1
        return Write(expression)

    def _expect_line(self, expected: str) -> None:
        line_number, line = self._current()
        if line.strip() != expected:
            raise CompilerError(
                f"Se esperaba '{expected}' en linea {line_number}, pero se encontro '{line.strip()}'."
            )
        self.position += 1

    def _has_more_content(self) -> bool:
        while self.position < len(self.lines):
            _, line = self.lines[self.position]
            if line.strip():
                return True
            self.position += 1
        return False

    def _current(self) -> tuple[int, str]:
        if not self._has_more_content():
            last_line = self.lines[-1][0] if self.lines else 1
            return last_line, ""
        return self.lines[self.position]

    def _peek_content(self) -> str:
        line_number, line = self._current()
        _ = line_number
        return line.strip()


def parse_expression(text: str, line: int) -> Expression:
    return ExpressionParser(text, line).parse()


def parse_source(source: str) -> Program:
    return LineParser(source).parse_program()


def expression_to_text(expression: Expression) -> str:
    if isinstance(expression, NumberLiteral):
        return str(expression.value)
    if isinstance(expression, Variable):
        return expression.name
    if isinstance(expression, FunctionCall):
        args = ", ".join(expression_to_text(argument) for argument in expression.arguments)
        return f"{expression.name}({args})"
    if isinstance(expression, BinaryOperation):
        return (
            f"{expression_to_text(expression.left)} {expression.operator} "
            f"{expression_to_text(expression.right)}"
        )
    raise TypeError(f"Expresion no soportada: {type(expression).__name__}")


def _collect_assigned_names(statements: list[Statement]) -> list[str]:
    names: list[str] = []
    for statement in statements:
        if isinstance(statement, Assignment) and statement.name not in names:
            names.append(statement.name)
        if isinstance(statement, IfStatement):
            for name in _collect_assigned_names(statement.body):
                if name not in names:
                    names.append(name)
    return names


def _render_statement_as_c(statement: Statement, indent: int) -> list[str]:
    prefix = " " * indent

    if isinstance(statement, Assignment):
        return [f"{prefix}{statement.name} = {expression_to_text(statement.expression)};"]
    if isinstance(statement, Write):
        return [f'{prefix}printf("%d\\n", {expression_to_text(statement.expression)});']
    if isinstance(statement, Return):
        return [f"{prefix}return {expression_to_text(statement.expression)};"]
    if isinstance(statement, FunctionCall):
        return [f"{prefix}{expression_to_text(statement)};"]
    if isinstance(statement, IfStatement):
        lines = [f"{prefix}if ({expression_to_text(statement.condition)}) {{"]
        for child in statement.body:
            lines.extend(_render_statement_as_c(child, indent + 4))
        lines.append(f"{prefix}}}")
        return lines
    raise TypeError(f"Sentencia no soportada: {type(statement).__name__}")


def _render_function_as_c(function: FunctionDef) -> list[str]:
    params = ", ".join(f"int {param}" for param in function.parameters)
    local_names = [name for name in _collect_assigned_names(function.body) if name not in function.parameters]

    lines = [f"int {function.name}({params}) {{"]
    for name in local_names:
        lines.append(f"    int {name} = 0;")
    if local_names and function.body:
        lines.append("")
    for statement in function.body:
        lines.extend(_render_statement_as_c(statement, 4))
    lines.append("}")
    return lines


def generate_c_code(program: Program) -> str:
    lines = ["#include <stdio.h>", ""]

    for function in program.functions:
        lines.extend(_render_function_as_c(function))
        lines.append("")

    main_locals = _collect_assigned_names(program.statements)
    lines.append("int main(void) {")
    for name in main_locals:
        lines.append(f"    int {name} = 0;")
    if main_locals and program.statements:
        lines.append("")
    for statement in program.statements:
        lines.extend(_render_statement_as_c(statement, 4))
    lines.append("    return 0;")
    lines.append("}")
    return "\n".join(lines).strip()


class RegisterPool:
    def __init__(self) -> None:
        self.available = ["$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7"]

    def acquire(self) -> str:
        if not self.available:
            raise CompilerError("No hay registros temporales disponibles.")
        return self.available.pop(0)

    def release(self, register: str) -> None:
        if register.startswith("$t") and register not in self.available:
            self.available.insert(0, register)


class MIPSGenerator:
    ARG_REGISTERS = ["$a0", "$a1", "$a2", "$a3"]

    def __init__(self) -> None:
        self.registers = RegisterPool()
        self.label_counter = 0

    def generate(self, program: Program) -> str:
        data_labels = self._collect_data_labels(program)
        lines = [
            ".data",
            'msg_nl: .asciiz "\\n"',
        ]
        for label in data_labels:
            lines.append(f"{label}: .word 0")

        lines.extend(["", ".text", ".globl main"])

        for function in program.functions:
            lines.extend(self._emit_function(function))
            lines.append("")

        lines.extend(self._emit_main(program.statements))
        return "\n".join(lines).strip()

    def _collect_data_labels(self, program: Program) -> list[str]:
        labels: list[str] = []

        def add(label: str) -> None:
            if label not in labels:
                labels.append(label)

        for name in _collect_assigned_names(program.statements):
            add(name)

        for function in program.functions:
            for name in _collect_assigned_names(function.body):
                if name not in function.parameters:
                    add(f"{function.name}_{name}")

        return labels

    def _emit_function(self, function: FunctionDef) -> list[str]:
        emitted = [f"{function.name}:"]
        bindings = {
            parameter: self.ARG_REGISTERS[index]
            for index, parameter in enumerate(function.parameters[: len(self.ARG_REGISTERS)])
        }

        for name in _collect_assigned_names(function.body):
            if name not in bindings:
                bindings[name] = f"{function.name}_{name}"

        for statement in function.body:
            emitted.extend(self._emit_statement(statement, bindings))

        if not any(isinstance(statement, Return) for statement in function.body):
            emitted.append("    jr $ra")

        return emitted

    def _emit_main(self, statements: list[Statement]) -> list[str]:
        bindings = {name: name for name in _collect_assigned_names(statements)}
        emitted = ["main:"]

        for statement in statements:
            emitted.extend(self._emit_statement(statement, bindings))

        emitted.extend(
            [
                "    li $v0, 10",
                "    syscall",
            ]
        )
        return emitted

    def _emit_statement(self, statement: Statement, bindings: dict[str, str]) -> list[str]:
        emitted: list[str] = []

        if isinstance(statement, Assignment):
            register = self._emit_expression(statement.expression, bindings, emitted)
            emitted.append(f"    sw {register}, {bindings[statement.name]}")
            self.registers.release(register)
            return emitted

        if isinstance(statement, Write):
            register = self._emit_expression(statement.expression, bindings, emitted)
            emitted.extend(
                [
                    f"    move $a0, {register}",
                    "    li $v0, 1",
                    "    syscall",
                    "    li $v0, 4",
                    "    la $a0, msg_nl",
                    "    syscall",
                ]
            )
            self.registers.release(register)
            return emitted

        if isinstance(statement, Return):
            register = self._emit_expression(statement.expression, bindings, emitted)
            emitted.extend(
                [
                    f"    move $v0, {register}",
                    "    jr $ra",
                ]
            )
            self.registers.release(register)
            return emitted

        if isinstance(statement, FunctionCall):
            register = self._emit_expression(statement, bindings, emitted)
            self.registers.release(register)
            return emitted

        if isinstance(statement, IfStatement):
            end_label = self._new_label()
            condition_register = self._emit_expression(statement.condition, bindings, emitted)
            emitted.append(f"    beq {condition_register}, $zero, {end_label}")
            self.registers.release(condition_register)
            for child in statement.body:
                emitted.extend(self._emit_statement(child, bindings))
            emitted.append(f"{end_label}:")
            return emitted

        raise TypeError(f"Sentencia no soportada: {type(statement).__name__}")

    def _emit_expression(
        self,
        expression: Expression,
        bindings: dict[str, str],
        emitted: list[str],
    ) -> str:
        result = self.registers.acquire()

        if isinstance(expression, NumberLiteral):
            emitted.append(f"    li {result}, {expression.value}")
            return result

        if isinstance(expression, Variable):
            source = bindings.get(expression.name, expression.name)
            if source.startswith("$"):
                emitted.append(f"    move {result}, {source}")
            else:
                emitted.append(f"    lw {result}, {source}")
            return result

        if isinstance(expression, FunctionCall):
            temp_registers: list[str] = []
            for index, argument in enumerate(expression.arguments):
                if index >= len(self.ARG_REGISTERS):
                    raise CompilerError("Solo se soportan hasta 4 argumentos por funcion.")
                argument_register = self._emit_expression(argument, bindings, emitted)
                emitted.append(f"    move {self.ARG_REGISTERS[index]}, {argument_register}")
                temp_registers.append(argument_register)
            for register in temp_registers:
                self.registers.release(register)
            emitted.append(f"    jal {expression.name}")
            emitted.append(f"    move {result}, $v0")
            return result

        if isinstance(expression, BinaryOperation):
            left = self._emit_expression(expression.left, bindings, emitted)
            right = self._emit_expression(expression.right, bindings, emitted)

            if expression.operator == "+":
                emitted.append(f"    add {result}, {left}, {right}")
            elif expression.operator == "-":
                emitted.append(f"    sub {result}, {left}, {right}")
            elif expression.operator == "*":
                emitted.append(f"    mul {result}, {left}, {right}")
            elif expression.operator == "/":
                emitted.append(f"    div {left}, {right}")
                emitted.append(f"    mflo {result}")
            elif expression.operator == ">":
                emitted.append(f"    sgt {result}, {left}, {right}")
            elif expression.operator == "<":
                emitted.append(f"    slt {result}, {left}, {right}")
            elif expression.operator == ">=":
                emitted.append(f"    sge {result}, {left}, {right}")
            elif expression.operator == "<=":
                emitted.append(f"    sle {result}, {left}, {right}")
            elif expression.operator == "==":
                emitted.append(f"    seq {result}, {left}, {right}")
            elif expression.operator == "!=":
                emitted.append(f"    sne {result}, {left}, {right}")
            else:
                raise CompilerError(f"Operador no soportado: {expression.operator}")

            self.registers.release(left)
            self.registers.release(right)
            return result

        raise TypeError(f"Expresion no soportada: {type(expression).__name__}")

    def _new_label(self) -> str:
        self.label_counter += 1
        return f"L{self.label_counter}"


def generate_assembler(program: Program) -> str:
    return MIPSGenerator().generate(program)


def statement_to_flow_label(statement: Statement) -> str:
    if isinstance(statement, Assignment):
        return f"{statement.name} = {expression_to_text(statement.expression)}"
    if isinstance(statement, Write):
        return f"escribir({expression_to_text(statement.expression)})"
    if isinstance(statement, Return):
        return f"retornar {expression_to_text(statement.expression)}"
    if isinstance(statement, FunctionCall):
        return expression_to_text(statement)
    if isinstance(statement, IfStatement):
        return f"si ({expression_to_text(statement.condition)})"
    raise TypeError(f"Sentencia no soportada: {type(statement).__name__}")


EXAMPLE_SOURCE = """funcion suma(x, y)
    retornar x + y
finfuncion

inicio
    a = 10
    b = 20
    total = suma(a, b)
    si (total > 20) entonces
        escribir(total)
    finsi
    escribir(a + b)
fin
"""
