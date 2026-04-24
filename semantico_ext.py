import lexico
class TablaSimbolos:
    def __init__(self):
        self.variables = {}     # Almacena variables {nombre: tipo}
        self.funciones = {}     # Almacena funciones {nombre: (tipo_ret, [parametros]   )}

    def declarar_variable(self, nombre, tipo):
        if nombre in self.variables:
            raise Exception(f"Error: Variable '{nombre}' ya declarada")
        self.variables[nombre] = tipo

    def obtener_tipo_variable(self, nombre):
        if nombre not in self.variables:
            raise Exception(f"Error: Variable '{nombre}' no definida")

        return self.variables[nombre]
    
    def declarar_funcion(self, nombre, tipo_retorno, parametros):
        if nombre in self.funciones:
            raise Exception(f"Error: Funcion '{nombre}' ya definida")
        self.funciones[nombre] = (tipo_retorno, parametros)

    def obtener_info_funcion(self, nombre):
        if nombre not in self.funciones:
            raise Exception(f"Error: Funcion '{nombre}' no definida")
        return self.funciones[nombre]
    
# ------------------------ Analizador Semantico -----------------------------
class AnalizadorSemantico:
    def __init__(self):
        self.tabla_simbolos = TablaSimbolos()
    
    def analizar(self, nodo):
        if isinstance(nodo, lexico.NodoPrograma):
            for funcion in nodo.funciones:
                self.analizar(funcion)
            self.analizar(main)
        elif isinstance(nodo, lexico.NodoFuncion):
            self.tabla_simbolos.declarar_funcion(nodo.nombre, nodo.tipo, nodo.parametros)
            for instruccion in nodo.cuerpo:
                self.analizar(instruccion)
        elif isinstance(nodo, lexico.NodoAsignacion):
            tipo_expr = self.analizar(nodo.expresion)
            if tipo_expr != nodo.tipo:
                raise Exception(f"Error: mp coinciden los tipos {nodo.tipo} != {tipo_expr}")
            self.tabla_simbolos.declarar_funcion(nodo.nombre, nodo.tipo)
        elif isinstance(nodo, lexico.NodoOperacion):
            tipo_izq = self.analizar(nodo.izquierda)
            tipo_der = self.analizar(nodo.derecha)
            if tipo_izq != tipo_der:
                raise Exception(f"Error: tipos incompatabiles en la expresion {tipo_izq} {nodo.operador} {tipo_der}")
            elif isinstance(nodo, lexico.NodoIdentificador):
                return self.tabla_simbolos.obtener_tipo_variable(nodo.nombre)
            elif isinstance(nodo, lexico.NodoNumero):
                return 'int' if '.' not in nodo.valor[1] else 'float'   
            elif isinstance(nodo, lexico.NodoLlamadaFuncion):
                tipo, parametros = self.tabla_simbolos.obtener_info_funcion(nodo.nombre)         