from __future__ import annotations

from dataclasses import dataclass

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


Operand = int | str


def operand_text(value: Operand) -> str:
    return str(value)


def is_temp(value: Operand) -> bool:
    return isinstance(value, str) and value.startswith("t")


def is_variable(value: Operand) -> bool:
    return isinstance(value, str)


def apply_operator(left: int, operator: str, right: int) -> int:
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
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


@dataclass(slots=True)
class IRAssign:
    target: str
    value: Operand

    def format(self) -> str:
        return f"{self.target} = {operand_text(self.value)}"

    def uses(self) -> list[str]:
        return [self.value] if is_variable(self.value) else []


@dataclass(slots=True)
class IRBinary:
    target: str
    left: Operand
    operator: str
    right: Operand

    def format(self) -> str:
        return (
            f"{self.target} = {operand_text(self.left)} "
            f"{self.operator} {operand_text(self.right)}"
        )

    def uses(self) -> list[str]:
        used: list[str] = []
        if is_variable(self.left):
            used.append(self.left)
        if is_variable(self.right):
            used.append(self.right)
        return used


@dataclass(slots=True)
class IRIfFalse:
    condition: Operand
    label: str

    def format(self) -> str:
        return f"if_false {operand_text(self.condition)} goto {self.label}"

    def uses(self) -> list[str]:
        return [self.condition] if is_variable(self.condition) else []


@dataclass(slots=True)
class IRGoto:
    label: str

    def format(self) -> str:
        return f"goto {self.label}"

    def uses(self) -> list[str]:
        return []


@dataclass(slots=True)
class IRLabel:
    name: str

    def format(self) -> str:
        return f"{self.name}:"

    def uses(self) -> list[str]:
        return []


@dataclass(slots=True)
class IRWrite:
    value: Operand

    def format(self) -> str:
        return f"escribir {operand_text(self.value)}"

    def uses(self) -> list[str]:
        return [self.value] if is_variable(self.value) else []


@dataclass(slots=True)
class IRReturn:
    value: Operand

    def format(self) -> str:
        return f"return {operand_text(self.value)}"

    def uses(self) -> list[str]:
        return [self.value] if is_variable(self.value) else []


@dataclass(slots=True)
class IRCall:
    target: str | None
    name: str
    arguments: list[Operand]

    def format(self) -> str:
        args = ", ".join(operand_text(argument) for argument in self.arguments)
        if self.target is None:
            return f"call {self.name}({args})"
        return f"{self.target} = call {self.name}({args})"

    def uses(self) -> list[str]:
        return [argument for argument in self.arguments if is_variable(argument)]


Instruction = IRAssign | IRBinary | IRIfFalse | IRGoto | IRLabel | IRWrite | IRReturn | IRCall


@dataclass(slots=True)
class IRFunction:
    name: str
    parameters: list[str]
    instructions: list[Instruction]


@dataclass(slots=True)
class IRProgram:
    functions: list[IRFunction]
    main: list[Instruction]


class ThreeAddressGenerator:
    def __init__(self) -> None:
        self.temp_counter = 0
        self.label_counter = 0

    def generate(self, program: Program) -> IRProgram:
        functions = [
            IRFunction(
                name=function.name,
                parameters=list(function.parameters),
                instructions=self._generate_block(function.body),
            )
            for function in program.functions
        ]
        main = self._generate_block(program.statements)
        return IRProgram(functions=functions, main=main)

    def _generate_block(self, statements: list) -> list[Instruction]:
        instructions: list[Instruction] = []

        for statement in statements:
            instructions.extend(self._generate_statement(statement))

        return instructions

    def _generate_statement(self, statement) -> list[Instruction]:
        instructions: list[Instruction] = []

        if isinstance(statement, Assignment):
            value, expression_code = self._generate_expression(statement.expression)
            instructions.extend(expression_code)
            instructions.append(IRAssign(statement.name, value))
            return instructions

        if isinstance(statement, Write):
            value, expression_code = self._generate_expression(statement.expression)
            instructions.extend(expression_code)
            instructions.append(IRWrite(value))
            return instructions

        if isinstance(statement, IfStatement):
            condition, condition_code = self._generate_expression(statement.condition)
            end_label = self._new_label()
            instructions.extend(condition_code)
            instructions.append(IRIfFalse(condition, end_label))
            instructions.extend(self._generate_block(statement.body))
            instructions.append(IRLabel(end_label))
            return instructions

        if isinstance(statement, Return):
            value, expression_code = self._generate_expression(statement.expression)
            instructions.extend(expression_code)
            instructions.append(IRReturn(value))
            return instructions

        raise TypeError(f"Sentencia no soportada: {type(statement).__name__}")

    def _generate_expression(self, expression) -> tuple[Operand, list[Instruction]]:
        if isinstance(expression, NumberLiteral):
            return expression.value, []

        if isinstance(expression, Variable):
            return expression.name, []

        if isinstance(expression, BinaryOperation):
            left, left_code = self._generate_expression(expression.left)
            right, right_code = self._generate_expression(expression.right)
            temp = self._new_temp()
            return (
                temp,
                left_code + right_code + [IRBinary(temp, left, expression.operator, right)],
            )

        if isinstance(expression, FunctionCall):
            instructions: list[Instruction] = []
            arguments: list[Operand] = []

            for argument in expression.arguments:
                value, argument_code = self._generate_expression(argument)
                instructions.extend(argument_code)
                arguments.append(value)

            temp = self._new_temp()
            instructions.append(IRCall(temp, expression.name, arguments))
            return temp, instructions

        raise TypeError(f"Expresion no soportada: {type(expression).__name__}")

    def _new_temp(self) -> str:
        self.temp_counter += 1
        return f"t{self.temp_counter}"

    def _new_label(self) -> str:
        self.label_counter += 1
        return f"L{self.label_counter}"


def format_instructions(instructions: list[Instruction]) -> str:
    return "\n".join(instruction.format() for instruction in instructions)


def format_ir_program(program: IRProgram) -> str:
    sections: list[str] = []

    for function in program.functions:
        header = f"funcion {function.name}({', '.join(function.parameters)})"
        body = format_instructions(function.instructions)
        sections.append(f"{header}\n{body}")

    sections.append("main\n" + format_instructions(program.main))
    return "\n\n".join(section for section in sections if section.strip())


def resolve_operand(value: Operand, constants: dict[str, int]) -> Operand:
    if is_variable(value) and value in constants:
        return constants[value]
    return value


def constant_propagation(instructions: list[Instruction]) -> list[Instruction]:
    constants: dict[str, int] = {}
    optimized: list[Instruction] = []

    for instruction in instructions:
        if isinstance(instruction, IRAssign):
            value = resolve_operand(instruction.value, constants)
            if isinstance(value, int):
                constants[instruction.target] = value
            else:
                constants.pop(instruction.target, None)
            optimized.append(IRAssign(instruction.target, value))
            continue

        if isinstance(instruction, IRBinary):
            left = resolve_operand(instruction.left, constants)
            right = resolve_operand(instruction.right, constants)

            if isinstance(left, int) and isinstance(right, int):
                result = apply_operator(left, instruction.operator, right)
                constants[instruction.target] = result
                optimized.append(IRAssign(instruction.target, result))
            else:
                constants.pop(instruction.target, None)
                optimized.append(
                    IRBinary(instruction.target, left, instruction.operator, right)
                )
            continue

        if isinstance(instruction, IRIfFalse):
            condition = resolve_operand(instruction.condition, constants)
            if isinstance(condition, int):
                if condition == 0:
                    optimized.append(IRGoto(instruction.label))
                continue
            optimized.append(IRIfFalse(condition, instruction.label))
            continue

        if isinstance(instruction, IRWrite):
            optimized.append(IRWrite(resolve_operand(instruction.value, constants)))
            continue

        if isinstance(instruction, IRReturn):
            optimized.append(IRReturn(resolve_operand(instruction.value, constants)))
            continue

        if isinstance(instruction, IRCall):
            arguments = [resolve_operand(argument, constants) for argument in instruction.arguments]
            if instruction.target is not None:
                constants.pop(instruction.target, None)
            optimized.append(IRCall(instruction.target, instruction.name, arguments))
            continue

        optimized.append(instruction)

    return optimized


def remove_unreachable_code(instructions: list[Instruction]) -> list[Instruction]:
    reachable = True
    optimized: list[Instruction] = []

    for instruction in instructions:
        if isinstance(instruction, IRLabel):
            reachable = True
            optimized.append(instruction)
            continue

        if not reachable:
            continue

        optimized.append(instruction)

        if isinstance(instruction, IRGoto):
            reachable = False

    return optimized


def eliminate_dead_temporaries(instructions: list[Instruction]) -> list[Instruction]:
    live: set[str] = set()
    kept: list[Instruction] = []

    for instruction in reversed(instructions):
        if isinstance(instruction, IRAssign):
            if is_temp(instruction.target) and instruction.target not in live:
                continue
            live.discard(instruction.target)
            live.update(instruction.uses())
            kept.append(instruction)
            continue

        if isinstance(instruction, IRBinary):
            if is_temp(instruction.target) and instruction.target not in live:
                continue
            live.discard(instruction.target)
            live.update(instruction.uses())
            kept.append(instruction)
            continue

        if isinstance(instruction, IRCall):
            if instruction.target is not None:
                live.discard(instruction.target)
            live.update(instruction.uses())
            kept.append(instruction)
            continue

        live.update(instruction.uses())
        kept.append(instruction)

    kept.reverse()
    return kept


def remove_unused_labels(instructions: list[Instruction]) -> list[Instruction]:
    referenced = {
        instruction.label
        for instruction in instructions
        if isinstance(instruction, (IRGoto, IRIfFalse))
    }

    return [
        instruction
        for instruction in instructions
        if not isinstance(instruction, IRLabel) or instruction.name in referenced
    ]


def optimize_instructions(instructions: list[Instruction]) -> tuple[list[Instruction], list[str]]:
    optimized = constant_propagation(instructions)
    optimized = remove_unreachable_code(optimized)
    optimized = eliminate_dead_temporaries(optimized)
    optimized = remove_unused_labels(optimized)

    passes = [
        "Plegado y propagacion de constantes",
        "Eliminacion de codigo muerto y simplificacion de saltos",
    ]
    return optimized, passes


class RegisterPool:
    def __init__(self) -> None:
        self.available = ["$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7"]

    def acquire(self) -> str:
        if not self.available:
            raise RuntimeError("No hay registros temporales disponibles.")
        return self.available.pop(0)

    def release(self, register: str) -> None:
        if register.startswith("$t") and register not in self.available:
            self.available.insert(0, register)


class MIPSGenerator:
    ARG_REGISTERS = ["$a0", "$a1", "$a2", "$a3"]

    def __init__(self) -> None:
        self.registers = RegisterPool()
        self.lines: list[str] = []
        self.data_labels: list[str] = []
        self.label_counter = 0

    def generate(self, program: Program) -> str:
        self.lines = []
        self.data_labels = self._collect_data_labels(program)
        self.label_counter = 0

        data_section = [
            ".data",
            'msg: .asciiz "\\n"',
            "    # Convencion: las variables del programa se almacenan en memoria",
        ]
        for label in self.data_labels:
            data_section.append(f"    {label}: .word 0")

        text_section = [
            ".text",
            ".globl main",
            "    # Convencion: se usan registros temporales $t0-$t7 para evaluar expresiones",
        ]

        for function in program.functions:
            text_section.extend(self._emit_function(function))
            text_section.append("")

        text_section.extend(self._emit_main(program.statements))

        return "\n".join(data_section + [""] + text_section).strip()

    def _collect_data_labels(self, program: Program) -> list[str]:
        labels: list[str] = []

        def add_label(label: str) -> None:
            if label not in labels:
                labels.append(label)

        def collect_from_statements(statements: list, prefix: str | None = None) -> None:
            for statement in statements:
                if isinstance(statement, Assignment):
                    label = statement.name if prefix is None else f"{prefix}_{statement.name}"
                    add_label(label)
                if isinstance(statement, IfStatement):
                    collect_from_statements(statement.body, prefix)

        collect_from_statements(program.statements)

        for function in program.functions:
            locals_in_function = [
                statement.name
                for statement in function.body
                if isinstance(statement, Assignment) and statement.name not in function.parameters
            ]
            for name in locals_in_function:
                add_label(f"{function.name}_{name}")
            for statement in function.body:
                if isinstance(statement, IfStatement):
                    collect_from_statements(statement.body, function.name)

        return labels

    def _emit_function(self, function: FunctionDef) -> list[str]:
        emitted = [f"{function.name}:", "    # Inicio de funcion"]
        bindings = {
            parameter: self.ARG_REGISTERS[index]
            for index, parameter in enumerate(function.parameters)
            if index < len(self.ARG_REGISTERS)
        }

        local_names = self._collect_assigned_names(function.body)
        for name in local_names:
            if name not in bindings:
                bindings[name] = f"{function.name}_{name}"

        for statement in function.body:
            emitted.extend(self._emit_statement(statement, bindings))

        if not any(isinstance(statement, Return) for statement in function.body):
            emitted.append("    jr $ra")

        return emitted

    def _emit_main(self, statements: list) -> list[str]:
        emitted = ["main:", "    # Programa principal"]
        bindings = {name: name for name in self._collect_assigned_names(statements)}

        for statement in statements:
            emitted.extend(self._emit_statement(statement, bindings))

        emitted.extend(
            [
                "    # Fin del programa",
                "    li $v0, 10",
                "    syscall",
            ]
        )
        return emitted

    def _collect_assigned_names(self, statements: list) -> list[str]:
        names: list[str] = []

        for statement in statements:
            if isinstance(statement, Assignment) and statement.name not in names:
                names.append(statement.name)
            if isinstance(statement, IfStatement):
                for name in self._collect_assigned_names(statement.body):
                    if name not in names:
                        names.append(name)

        return names

    def _emit_statement(self, statement, bindings: dict[str, str]) -> list[str]:
        emitted: list[str] = []

        if isinstance(statement, Assignment):
            emitted.append(f"    # {statement.name} = {self._describe_expression(statement.expression)}")
            register = self._emit_expression(statement.expression, bindings, emitted)
            target = bindings.get(statement.name, statement.name)
            if target.startswith("$"):
                emitted.append(f"    move {target}, {register}")
            else:
                emitted.append(f"    sw {register}, {target}")
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
                    "    la $a0, msg",
                    "    syscall",
                ]
            )
            self.registers.release(register)
            return emitted

        if isinstance(statement, IfStatement):
            label = self._new_label()
            emitted.append(
                f"    # si ({self._describe_expression(statement.condition)}) entonces"
            )
            register = self._emit_expression(statement.condition, bindings, emitted)
            emitted.append("    # si la condicion es falsa, saltar al final del bloque")
            emitted.append(f"    beq {register}, $zero, {label}")
            self.registers.release(register)
            for child in statement.body:
                emitted.extend(self._emit_statement(child, bindings))
            emitted.append(f"{label}:")
            return emitted

        if isinstance(statement, Return):
            emitted.append(f"    # retornar {self._describe_expression(statement.expression)}")
            register = self._emit_expression(statement.expression, bindings, emitted)
            emitted.extend(
                [
                    f"    move $v0, {register}",
                    "    jr $ra",
                ]
            )
            self.registers.release(register)
            return emitted

        raise TypeError(f"Sentencia no soportada: {type(statement).__name__}")

    def _new_label(self) -> str:
        self.label_counter += 1
        return f"mips_L{self.label_counter}"

    def _describe_expression(self, expression) -> str:
        if isinstance(expression, NumberLiteral):
            return str(expression.value)
        if isinstance(expression, Variable):
            return expression.name
        if isinstance(expression, FunctionCall):
            arguments = ", ".join(
                self._describe_expression(argument) for argument in expression.arguments
            )
            return f"{expression.name}({arguments})"
        if isinstance(expression, BinaryOperation):
            left = self._describe_expression(expression.left)
            right = self._describe_expression(expression.right)
            return f"{left} {expression.operator} {right}"
        return type(expression).__name__

    def _emit_expression(
        self,
        expression,
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
                raise ValueError(f"Operador no soportado: {expression.operator}")

            self.registers.release(left)
            self.registers.release(right)
            return result

        raise TypeError(f"Expresion no soportada: {type(expression).__name__}")
