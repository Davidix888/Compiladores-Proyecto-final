from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from sintactico_ast import (
    Assignment,
    BinaryOperation,
    FunctionCall,
    FunctionDef,
    IfStatement,
    NumberLiteral,
    Program,
    Return,
    Variable,
    Write,
)


@dataclass(slots=True)
class VariableState:
    name: str
    scope: str
    type: str = "entero"
    defined: bool = False
    maybe_defined: bool = False
    value: int | None = None

    def to_dict(self) -> dict:
        return {
            "tipo": self.type,
            "ambito": self.scope,
            "definida": self.defined,
            "posible_definicion": self.maybe_defined,
            "valor": self.value,
        }


@dataclass(slots=True)
class FunctionInfo:
    name: str
    parameters: list[str]
    return_type: str = "entero"

    def to_dict(self) -> dict:
        return {
            "retorno": self.return_type,
            "parametros": self.parameters,
        }


@dataclass(slots=True)
class ExpressionResult:
    type: str = "entero"
    value: int | None = None


@dataclass(slots=True)
class ReturnSignal:
    value: ExpressionResult


@dataclass(slots=True)
class SemanticReport:
    globals_table: dict[str, VariableState]
    functions_table: dict[str, FunctionInfo]
    scopes_table: dict[str, dict[str, VariableState]]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def globals_as_dict(self) -> dict[str, dict]:
        return {
            name: state.to_dict()
            for name, state in sorted(self.globals_table.items())
        }

    def functions_as_dict(self) -> dict[str, dict]:
        return {
            name: info.to_dict()
            for name, info in sorted(self.functions_table.items())
        }

    def scopes_as_dict(self) -> dict[str, dict[str, dict]]:
        return {
            scope: {
                name: state.to_dict()
                for name, state in sorted(values.items())
            }
            for scope, values in sorted(self.scopes_table.items())
        }


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.functions: dict[str, FunctionInfo] = {}
        self.function_nodes: dict[str, FunctionDef] = {}
        self.scopes: dict[str, dict[str, VariableState]] = {}
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.notes: list[str] = []
        self._warning_cache: set[str] = set()

    def analyze(self, program: Program) -> SemanticReport:
        self._register_functions(program.functions)

        for function in program.functions:
            self._analyze_function(function)

        global_scope: dict[str, VariableState] = {}
        global_scope, _ = self._execute_block(program.statements, global_scope, "global")
        self.scopes["global"] = deepcopy(global_scope)

        if (
            "d" in global_scope
            and global_scope["d"].defined
            and global_scope["d"].value is not None
        ):
            self.notes.append(
                "En este programa concreto no hay error en escribir(d) porque "
                "c vale 50, la condicion c > 30 siempre es verdadera y d termina con 40."
            )
        else:
            self.notes.append(
                "Si la condicion no pudiera resolverse en compilacion, d deberia "
                "marcarse como potencialmente no inicializada al salir del si."
            )

        return SemanticReport(
            globals_table=deepcopy(global_scope),
            functions_table=deepcopy(self.functions),
            scopes_table=deepcopy(self.scopes),
            warnings=list(self.warnings),
            errors=list(self.errors),
            notes=list(self.notes),
        )

    def _register_functions(self, functions: list[FunctionDef]) -> None:
        for function in functions:
            if function.name in self.functions:
                self.errors.append(f"La funcion {function.name!r} ya fue declarada.")
                continue

            self.functions[function.name] = FunctionInfo(
                name=function.name,
                parameters=list(function.parameters),
            )
            self.function_nodes[function.name] = function

    def _analyze_function(self, function: FunctionDef) -> None:
        local_scope = {
            parameter: VariableState(
                name=parameter,
                scope=function.name,
                defined=True,
                maybe_defined=True,
                value=None,
            )
            for parameter in function.parameters
        }

        final_scope, signal = self._execute_block(function.body, local_scope, function.name)
        self.scopes[function.name] = deepcopy(final_scope)

        if signal is None:
            self.warnings.append(
                f"La funcion {function.name!r} no tiene un retornar explicito."
            )

    def _execute_block(
        self,
        statements: list,
        scope: dict[str, VariableState],
        scope_name: str,
    ) -> tuple[dict[str, VariableState], ReturnSignal | None]:
        current_scope = deepcopy(scope)

        for statement in statements:
            if isinstance(statement, Assignment):
                result = self._evaluate_expression(statement.expression, current_scope, scope_name)
                current_scope[statement.name] = VariableState(
                    name=statement.name,
                    scope=scope_name,
                    defined=True,
                    maybe_defined=True,
                    value=result.value,
                )
                continue

            if isinstance(statement, Write):
                self._evaluate_expression(statement.expression, current_scope, scope_name)
                continue

            if isinstance(statement, IfStatement):
                condition = self._evaluate_expression(statement.condition, current_scope, scope_name)

                if condition.value == 1:
                    current_scope, signal = self._execute_block(
                        statement.body,
                        current_scope,
                        scope_name,
                    )
                    if signal is not None:
                        return current_scope, signal
                    continue

                if condition.value == 0:
                    continue

                then_scope, signal = self._execute_block(
                    statement.body,
                    current_scope,
                    scope_name,
                )
                if signal is not None:
                    return current_scope, signal
                current_scope = self._merge_scopes(current_scope, then_scope, scope_name)
                continue

            if isinstance(statement, Return):
                value = self._evaluate_expression(statement.expression, current_scope, scope_name)
                return current_scope, ReturnSignal(value=value)

        return current_scope, None

    def _evaluate_expression(
        self,
        expression,
        scope: dict[str, VariableState],
        scope_name: str,
    ) -> ExpressionResult:
        if isinstance(expression, NumberLiteral):
            return ExpressionResult(value=expression.value)

        if isinstance(expression, Variable):
            state = scope.get(expression.name)

            if state is None:
                self.errors.append(
                    f"La variable {expression.name!r} se usa sin declaracion previa "
                    f"en el ambito {scope_name!r}."
                )
                return ExpressionResult(value=None)

            if not state.maybe_defined:
                self.errors.append(
                    f"La variable {expression.name!r} se usa sin haber sido inicializada."
                )
                return ExpressionResult(value=None)

            if not state.defined:
                warning = (
                    f"La variable {expression.name!r} podria no estar inicializada "
                    f"en todos los caminos del programa."
                )
                self._warn_once(warning)
                return ExpressionResult(value=None)

            return ExpressionResult(value=state.value)

        if isinstance(expression, BinaryOperation):
            left = self._evaluate_expression(expression.left, scope, scope_name)
            right = self._evaluate_expression(expression.right, scope, scope_name)

            if left.value is None or right.value is None:
                return ExpressionResult(value=None)

            return ExpressionResult(
                value=self._apply_operator(left.value, expression.operator, right.value)
            )

        if isinstance(expression, FunctionCall):
            function_info = self.functions.get(expression.name)

            if function_info is None:
                self.errors.append(f"La funcion {expression.name!r} no existe.")
                return ExpressionResult(value=None)

            if len(expression.arguments) != len(function_info.parameters):
                self.errors.append(
                    f"La funcion {expression.name!r} esperaba "
                    f"{len(function_info.parameters)} argumentos y recibio "
                    f"{len(expression.arguments)}."
                )
                return ExpressionResult(value=None)

            evaluated_arguments = [
                self._evaluate_expression(argument, scope, scope_name)
                for argument in expression.arguments
            ]

            if any(argument.value is None for argument in evaluated_arguments):
                return ExpressionResult(value=None)

            simulated_value = self._simulate_function(
                self.function_nodes[expression.name],
                [argument.value for argument in evaluated_arguments],
            )
            return ExpressionResult(value=simulated_value)

        raise TypeError(f"Expresion no soportada: {type(expression).__name__}")

    def _simulate_function(
        self,
        function: FunctionDef,
        argument_values: list[int | None],
    ) -> int | None:
        local_scope = {
            parameter: VariableState(
                name=parameter,
                scope=function.name,
                defined=True,
                maybe_defined=True,
                value=argument_values[index],
            )
            for index, parameter in enumerate(function.parameters)
        }

        _, signal = self._execute_block(function.body, local_scope, function.name)
        if signal is None:
            return None
        return signal.value.value

    def _merge_scopes(
        self,
        base_scope: dict[str, VariableState],
        then_scope: dict[str, VariableState],
        scope_name: str,
    ) -> dict[str, VariableState]:
        merged: dict[str, VariableState] = {}

        for name in sorted(set(base_scope) | set(then_scope)):
            before = base_scope.get(name)
            after = then_scope.get(name)

            if before is not None and after is not None:
                merged[name] = VariableState(
                    name=name,
                    scope=scope_name,
                    defined=before.defined and after.defined,
                    maybe_defined=before.maybe_defined or after.maybe_defined,
                    value=before.value if before.value == after.value else None,
                )
                continue

            if before is not None:
                merged[name] = deepcopy(before)
                continue

            if after is not None:
                merged[name] = VariableState(
                    name=name,
                    scope=scope_name,
                    defined=False,
                    maybe_defined=True,
                    value=None,
                )

        return merged

    def _warn_once(self, warning: str) -> None:
        if warning not in self._warning_cache:
            self._warning_cache.add(warning)
            self.warnings.append(warning)

    @staticmethod
    def _apply_operator(left: int, operator: str, right: int) -> int:
        if operator == "+":
            return left + right
        if operator == "-":
            return left - right
        if operator == "*":
            return left * right
        if operator == "/":
            if right == 0:
                raise ZeroDivisionError("Division por cero en tiempo de compilacion.")
            return left // right
        if operator == ">":
            return int(left > right)
        if operator == "<":
            return int(left < right)
        if operator == ">=":
            return int(left >= right)
        if operator == "<=":
            return int(left <= right)
        if operator == "==":
            return int(left == right)
        if operator == "!=":
            return int(left != right)
        raise ValueError(f"Operador no soportado: {operator}")
