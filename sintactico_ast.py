from __future__ import annotations

from dataclasses import dataclass, field

from lexico import Token


class ASTNode:
    def to_dict(self) -> dict:
        raise NotImplementedError


class Statement(ASTNode):
    pass


class Expression(ASTNode):
    pass


@dataclass(slots=True)
class Program(ASTNode):
    functions: list["FunctionDef"] = field(default_factory=list)
    statements: list[Statement] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tipo": "programa",
            "funciones": [function.to_dict() for function in self.functions],
            "cuerpo": [statement.to_dict() for statement in self.statements],
        }


@dataclass(slots=True)
class FunctionDef(ASTNode):
    name: str
    parameters: list[str]
    body: list[Statement]

    def to_dict(self) -> dict:
        return {
            "tipo": "funcion",
            "nombre": self.name,
            "parametros": self.parameters,
            "cuerpo": [statement.to_dict() for statement in self.body],
        }


@dataclass(slots=True)
class Assignment(Statement):
    name: str
    expression: Expression

    def to_dict(self) -> dict:
        return {
            "tipo": "asignacion",
            "variable": self.name,
            "expresion": self.expression.to_dict(),
        }


@dataclass(slots=True)
class Write(Statement):
    expression: Expression

    def to_dict(self) -> dict:
        return {
            "tipo": "escribir",
            "expresion": self.expression.to_dict(),
        }


@dataclass(slots=True)
class IfStatement(Statement):
    condition: Expression
    body: list[Statement]

    def to_dict(self) -> dict:
        return {
            "tipo": "si",
            "condicion": self.condition.to_dict(),
            "entonces": [statement.to_dict() for statement in self.body],
        }


@dataclass(slots=True)
class Return(Statement):
    expression: Expression

    def to_dict(self) -> dict:
        return {
            "tipo": "retornar",
            "expresion": self.expression.to_dict(),
        }


@dataclass(slots=True)
class NumberLiteral(Expression):
    value: int

    def to_dict(self) -> dict:
        return {
            "tipo": "constante",
            "valor": self.value,
        }


@dataclass(slots=True)
class Variable(Expression):
    name: str

    def to_dict(self) -> dict:
        return {
            "tipo": "variable",
            "nombre": self.name,
        }


@dataclass(slots=True)
class BinaryOperation(Expression):
    left: Expression
    operator: str
    right: Expression

    def to_dict(self) -> dict:
        return {
            "tipo": "operacion_binaria",
            "operador": self.operator,
            "izquierda": self.left.to_dict(),
            "derecha": self.right.to_dict(),
        }


@dataclass(slots=True)
class FunctionCall(Expression):
    name: str
    arguments: list[Expression]

    def to_dict(self) -> dict:
        return {
            "tipo": "llamada_funcion",
            "nombre": self.name,
            "argumentos": [argument.to_dict() for argument in self.arguments],
        }


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.position = 0

    def parse(self) -> Program:
        self._consume_newlines()

        functions: list[FunctionDef] = []
        while self._current().type == "FUNCION":
            functions.append(self._parse_function())
            self._consume_newlines()

        self._expect("INICIO")
        self._consume_newlines()
        statements = self._parse_block({"FIN"})
        self._expect("FIN")
        self._consume_newlines()
        self._expect("EOF")
        return Program(functions=functions, statements=statements)

    def _parse_function(self) -> FunctionDef:
        self._expect("FUNCION")
        name = self._expect("IDENTIFIER").value
        self._expect("LPAREN")

        parameters: list[str] = []
        if self._current().type != "RPAREN":
            parameters.append(self._expect("IDENTIFIER").value)
            while self._match("COMMA"):
                parameters.append(self._expect("IDENTIFIER").value)

        self._expect("RPAREN")
        self._consume_newlines()
        body = self._parse_block({"FINFUNCION"})
        self._expect("FINFUNCION")
        return FunctionDef(name=name, parameters=parameters, body=body)

    def _parse_block(self, end_tokens: set[str]) -> list[Statement]:
        statements: list[Statement] = []
        self._consume_newlines()

        while self._current().type not in end_tokens and self._current().type != "EOF":
            statements.append(self._parse_statement())

            if self._current().type == "NEWLINE":
                self._consume_newlines()
            elif self._current().type not in end_tokens:
                token = self._current()
                raise SyntaxError(
                    "Se esperaba un salto de linea antes de "
                    f"{token.value!r} en linea {token.line}"
                )

        return statements

    def _parse_statement(self) -> Statement:
        token = self._current()

        if token.type == "IDENTIFIER" and self._peek().type == "ASSIGN":
            return self._parse_assignment()
        if token.type == "ESCRIBIR":
            return self._parse_write()
        if token.type == "SI":
            return self._parse_if()
        if token.type == "RETORNAR":
            return self._parse_return()

        raise SyntaxError(
            f"Instruccion no reconocida {token.value!r} en linea {token.line}"
        )

    def _parse_assignment(self) -> Assignment:
        name = self._expect("IDENTIFIER").value
        self._expect("ASSIGN")
        expression = self._parse_expression()
        return Assignment(name=name, expression=expression)

    def _parse_write(self) -> Write:
        self._expect("ESCRIBIR")
        self._expect("LPAREN")
        expression = self._parse_expression()
        self._expect("RPAREN")
        return Write(expression=expression)

    def _parse_if(self) -> IfStatement:
        self._expect("SI")
        self._expect("LPAREN")
        condition = self._parse_expression()
        self._expect("RPAREN")
        self._expect("ENTONCES")
        self._consume_newlines()
        body = self._parse_block({"FINSI"})
        self._expect("FINSI")
        return IfStatement(condition=condition, body=body)

    def _parse_return(self) -> Return:
        self._expect("RETORNAR")
        expression = self._parse_expression()
        return Return(expression=expression)

    def _parse_expression(self) -> Expression:
        return self._parse_comparison()

    def _parse_comparison(self) -> Expression:
        expression = self._parse_addition()

        while self._current().type == "REL_OP":
            operator = self._expect("REL_OP").value
            right = self._parse_addition()
            expression = BinaryOperation(expression, operator, right)

        return expression

    def _parse_addition(self) -> Expression:
        expression = self._parse_multiplication()

        while self._current().type in {"PLUS", "MINUS"}:
            operator = self._advance().value
            right = self._parse_multiplication()
            expression = BinaryOperation(expression, operator, right)

        return expression

    def _parse_multiplication(self) -> Expression:
        expression = self._parse_unary()

        while self._current().type in {"STAR", "SLASH"}:
            operator = self._advance().value
            right = self._parse_unary()
            expression = BinaryOperation(expression, operator, right)

        return expression

    def _parse_unary(self) -> Expression:
        if self._match("MINUS"):
            return BinaryOperation(NumberLiteral(0), "-", self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> Expression:
        token = self._current()

        if token.type == "NUMBER":
            return NumberLiteral(int(self._advance().value))

        if token.type == "IDENTIFIER":
            name = self._advance().value
            if self._match("LPAREN"):
                arguments: list[Expression] = []
                if self._current().type != "RPAREN":
                    arguments.append(self._parse_expression())
                    while self._match("COMMA"):
                        arguments.append(self._parse_expression())
                self._expect("RPAREN")
                return FunctionCall(name=name, arguments=arguments)
            return Variable(name=name)

        if token.type == "LPAREN":
            self._advance()
            expression = self._parse_expression()
            self._expect("RPAREN")
            return expression

        raise SyntaxError(
            f"Expresion invalida {token.value!r} en linea {token.line}"
        )

    def _current(self) -> Token:
        return self.tokens[self.position]

    def _peek(self, offset: int = 1) -> Token:
        index = min(self.position + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def _advance(self) -> Token:
        token = self._current()
        self.position += 1
        return token

    def _expect(self, token_type: str) -> Token:
        token = self._current()
        if token.type != token_type:
            raise SyntaxError(
                f"Se esperaba {token_type} y se encontro {token.type} "
                f"({token.value!r}) en linea {token.line}"
            )
        self.position += 1
        return token

    def _match(self, token_type: str) -> bool:
        if self._current().type == token_type:
            self.position += 1
            return True
        return False

    def _consume_newlines(self) -> None:
        while self._current().type == "NEWLINE":
            self.position += 1
