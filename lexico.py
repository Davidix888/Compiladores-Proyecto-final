import re

# === Análisis Léxico ===
# Definir los patrones para los diferentes tipos de tokens
token_patron = {
    "KEYWORD": r'\b(if|else|while|return|int|float|void)\b',
    "IDENTIFIER": r'\b[a-zA-Z_][a-zA-Z0-9_]*\b',
    "NUMBER": r'\b\d+(\.\d+)?\b',
    "OPERATOR": r'[+\-*/=<>]',
    "DELIMITER": r'[();{},]',
    "WHITESPACE": r'\s+',
}

def identificar_tokens(texto):
    # Unimos todos los patrones en un único patrón usando grupos nombrados
    patron_general = '|'.join(
        f'(?P<{token}>{patron})'
        for token, patron in token_patron.items()
    )

    patron_regex = re.compile(patron_general)

    tokens_encontrados = []

    for match in patron_regex.finditer(texto):
        for token, valor in match.groupdict().items():
            if valor is not None and token != "WHITESPACE":  # Ignoramos espacios en blanco
                tokens_encontrados.append((token, valor))

    return tokens_encontrados


# ==========================
# DEFINICIÓN DEL AST
# ==========================

class NodoAST():
  # Clase para todos los nodos del AST
  pass

  def traducirPy(self):
    # Traduccion de C++ a Python
    raise NotImplementedError("Metodo traducirPy() no implementado en este Nodo.")
  
  def traducirRuby(self):
    # Traduccion de C++ a Ruby
    raise NotImplementedError("Metodo traducirRuby() no implementado en este Nodo.")
  
  def generarCodigo():
    # Traduccion de C++ a ASSEMBLER
    raise NotImplementedError("Metodo generarCodigo() no implementado en este Nodo.")

class NodoPrograma(NodoAST):
    # Nodo que representa a un programa completo
    def __init__(self, funciones, main):
      self.variables = []
      self.funciones = funciones
      self.main = main

    # Generar codigo de todas las funciones
    def generarCodigo(self):
      codigo = ["section .text", "global _start"]
      data = ["section .bss"]

      for funcion in self.funciones:
        codigo.append(funcion.generarCodigo())
        self.variables.append((funcion.cuerpo[0].tipo[1].funcion.cuerpo[0].nombre[1])) 

        if len(funcion.parametros) > 0:
          for parametro in funcion.parametros:
            self.variables.append((parametro.tipo[1], parametro[0]))

      # Generar el punto de entrada del proyecto
      codigo.append("_start:")
      codigo.append(self.main.generarCodigo())
      # Finalizacion del programa
      codigo.append("   mov eax, 1      ; syscall exit")
      codigo.append("   xor ebx, ebx    ; Codigo de salida 0")
      codigo.append("   int 0x80")

      # Seccion de reserva de memoria para las variables
      for variable in self.variables:
        if variable[0] == 'int':
            data.append(f'  {variable[1]}:  resd 1')
      codigo = '\n'.join(codigo)
      return '\n'.join(data) + '\n' + codigo

class NodoLlamadaFuncion(NodoAST):
    # Nodo que representa una llamada a funcion
    def __init__(self, nombref, argumentos):
        self.nombre_funcion = nombref
        self.argumentos = argumentos

    def traducirPy(self):
        args = ", ".join(arg.traducirPy() for arg in self.argumentos)

        # Si es print lo traducimos directo
        if self.nombre_funcion == "print":
            return f"print({args})"
        else:
            return f"{self.nombre_funcion}({args})"

    def traducirRuby(self):
        args = ", ".join(arg.traducirRuby() for arg in self.argumentos)

        if self.nombre_funcion == "print":
            return f"puts {args}"
        else:
            return f"{self.nombre_funcion}({args})"
    
    def generarCodigo (self):
      # Apilamos argumentos en orden inverso
      codigo = []
      for arg in reversed (self. argumentos):
        codigo.append(arg.generar_codigo())
        codigo.append(" push eax ; Pasar argumento a la pila")
      codigo. append (f"    call {self. nombre} ; Llamar a la función {self. nombre}")
      codigo. append (f"    add esp, {len(self. argumentos) * 4} ; Limpiar pila de argumentos")
      return "\n". join (codigo)



class NodoFuncion(NodoAST):
  # Nodo que representa la funcion
  def __init__(self, tipo, nombre, parametros, cuerpo):
    self.tipo = tipo
    self.nombre = nombre
    self.parametros = parametros
    self.cuerpo = cuerpo

  def generarCodigo(self):
    codigo = f'{self.nombre[1]}:\n'
    if len(self.parametros) > 0:
      # Aqui guardamos en pila el registro que usaremos
      for parametro in self.parametros:
        codigo += '\n   pop   eax'
        codigo += f'\n   mov [{parametro.nombre}],   eax'
    codigo += '\n'.join(c.generarCodigo() for c in self.cuerpo)
    codigo += '\n    ret'
    codigo += '\n'      
    return codigo

  def traducirPy(self):
    params = ", ".join(p.traducirPy() for p in self.parametros)
    cuerpo = "\n    ".join(c.traducirPy() for c in self.cuerpo)
    
    return f"def {self.nombre[1]}({params}):\n    {cuerpo}"
  
  def traducirRuby(self):
    params = ", ".join(p.traducirRuby() for p in self.parametros)
    cuerpo = "\n    ".join(c.traducirRuby() for c in self.cuerpo)
    
    return f"def {self.nombre[1]}({params})\n    {cuerpo}\nend"
  
class NodoParametro(NodoAST):
  # Nodo que representa a un parametro de funcion
  def __init__(self, tipo, nombre):
    self.tipo = tipo
    self.nombre = nombre

  def traducirPy(self):
    return self.nombre[1]
  
  def traducirRuby(self):
    return self.nombre[1]

class NodoAsignacion(NodoAST):
  # Nodo que representa una asignacion de variable
  def __init__(self, tipo, nombre, expresion):
    self.tipo = tipo
    self.nombre = nombre
    self.expresion = expresion
  
  def generarCodigo(self):
    codigo = self.expresion.generarCodigo()
    codigo +=f'\n   mov [{self.expresion.traducirPy()}], eax'
    return codigo
  
  def traducirPy(self):
    return f"{self.nombre[1]} = {self.expresion.traducirPy()}"

  def traducirRuby(self):
    return f"{self.nombre[1]} = {self.expresion.traducirRuby()}"

class NodoOperacion(NodoAST):
  # Nodo que representa una operacion aritmetica
  def __init__(self, izquierda, operador, derecha):
    self.izquierda = izquierda
    self.operador = operador
    self.derecha = derecha
  
  def generarCodigo(self):
    codigo = []
    codigo.append(self.izquierda.generarCodigo())
    codigo.append('   push    eax')
    codigo.append(self.derecha.generarCodigo())
    codigo.append('   mov   ebx, eax')
    if self.operador[1] == '+':
      codigo.append('   add   eax, ebx')
    return '\n'.join(codigo)

  def traducirPy(self):
    return f"{self.izquierda.traducirPy()} {self.operador[1]} {self.derecha.traducirPy()}"  
  
  def traducirRuby(self):
    return f"{self.izquierda.traducirRuby()} {self.operador[1]} {self.derecha.traducirRuby()}" 

  def optimizar(self):
    if isinstance(self.izquierda, NodoOperacion):
      self.izquierda.optimizar()
    
    else:
        izquierda = self.izquierda
    
    if isinstance(self.derecha, NodoOperacion):
      self.derecha.optimizar()
    else:
      derecha = self.derecha
    
    # Si ambos nodos son numeros realizamos la operacion de manera directa
    if isinstance(izquierda, NodoNumero) and isinstance(derecha, NodoNumero):
      izq = int(izquierda.valor[1])
      der = int(derecha.valor[1])

      if self.operador[1] == '+':
        valor = izq + der
      elif self.operador[1] == '-':
        valor = izq - der
      elif self.operador[1] == '*':
        valor = izq * der
      elif self.operador[1] == '/':
        valor = izq / der  # Verificar divisiones por 0
      return NodoNumero(('NUMBER', str(valor)))

    # Simplificacion algebraica
    if self.operador == '*' and isinstance(derecha, NodoNumero) and derecha.valor == 1:
      return izquierda
    if self.operador == '*' and isinstance(izquierda, NodoNumero) and izquierda.valor == 1:
      return derecha
    if self.operador == '+' and isinstance(derecha, NodoNumero) and derecha.valor == 0:
      return izquierda
    if self.operador == '+' and isinstance(izquierda, NodoNumero) and izquierda.valor == 0:
      return derecha
    
    # Si no se puede optimizar mas, se devuelve la expresion
    return NodoOperacion(izquierda, self.operador, derecha)


class NodoRetorno(NodoAST):
  # Nodo que representa un retorno de funcion
  def __init__(self, expresion):
    self.expresion = expresion
  
  def generarCodigo(self):
    return self.expresion.generarCodigo()

  def traducirPy(self):
    return f"return {self.expresion.traducirPy()}"
  
  def traducirRuby(self):
    return f"return {self.expresion.traducirRuby()}"

class NodoIdentificador(NodoAST):
  # Nodo que representa un identificador
  def __init__(self, nombre):
    self.nombre = nombre
  
  def generarCodigo(self):
    return f'\n   mov, eax, [{self.nombre[1]}]'

  def traducirPy(self):
    return self.nombre[1]
  
  def traducirRuby(self):
    return self.nombre[1]

class NodoNumero(NodoAST):
  # Nodo que representa un numero
  def __init__(self, valor):
      self.valor = valor
    
  def generarCodigo(self):
    return f'\n   mov, eax, [{self.valor[1]}]'
  
  def traducirPy(self):
    return str(self.valor[1])
  
  def traducirRuby(self):
    return str(self.valor[1])

