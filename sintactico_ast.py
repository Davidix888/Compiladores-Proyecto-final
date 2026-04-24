import lexico

# Analizador sintactico 
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
    
    def obtener_token_actual(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    
    def coincidir(self, tipo_esperado):
        token_actual = self.obtener_token_actual()
        if token_actual and token_actual[0] == tipo_esperado:
            self.pos +=1
            return token_actual
        else:
            raise SyntaxError(f"Error sintactico: Se esperaba {tipo_esperado}, pero se encontro: {token_actual}")

    def parsear(self):
        # Punto de entrada: Se espera una funcion
        return self.funcion()

    def funcion(self):
        # Gramatica para una funcion: int IDENTIFIER (int IDENTIFIER) {CUERPO}
        tipo_retorno = self.coincidir('KEYWORD')            # Tipo de retorno (ej. int)
        nombre_funcion = self.coincidir('IDENTIFIER')       # Nombre de la funcion
        self.coincidir('DELIMITER')                         # Se espera un (

        if nombre_funcion == 'main':
            parametros = []
        else:
            parametros = self.parametros()                      # Regla para los parametros
        self.coincidir('DELIMITER')                         # Se espera un )
        self.coincidir('DELIMITER')                         # Se espera un {
        cuerpo = self.cuerpo()                              # Regla para el cuerpo de la funcion
        self.coincidir('DELIMITER')                         # Se espera un }

        return lexico.NodoFuncion(tipo_retorno, nombre_funcion, parametros, cuerpo)

    def parametros(self):
        lista_parametros = []

        # Reglas para parametros: int IDENTIFIER (, int IDENTIFIER)*
        tipo = self.coincidir('KEYWORD')                    # Tipo de parametro
        nombre = self.coincidir('IDENTIFIER')               # Nombre del parametro

        lista_parametros.append(lexico.NodoParametro(tipo, nombre))

        while self.obtener_token_actual() and self.obtener_token_actual()[1] == ',':
            self.coincidir('DELIMITER')                     # Se espera una ,
            tipo = self.coincidir('KEYWORD')                # Tipo de paramentro
            nombre = self.coincidir('IDENTIFIER')           # Nombre de parametro

            lista_parametros.append(lexico.NodoParametro(tipo, nombre))
        
        return lista_parametros

    def cuerpo(self):
        instrucciones = []

        while self.obtener_token_actual() and self.obtener_token_actual()[1] != '}':
            token = self.obtener_token_actual()

            if token[1] == 'return':
                instrucciones.append(self.retorno())

            elif token[0] == 'KEYWORD':
                instrucciones.append(self.asignacion())

            elif token[0] == 'IDENTIFIER':
                instrucciones.append(self.llamadaComoInstruccion())

            else:
                raise SyntaxError(f"Instruccion no valida: {token}")

        return instrucciones

    def asignacion(self):
        # Gramatica para la estrucutra de una asignacion
        tipo = self.coincidir('KEYWORD')                    # Se espera un tipo
        nombre = self.coincidir('IDENTIFIER')
        self.coincidir('OPERATOR')                          # Se espera un =
        expresion = self.expresion()
        self.coincidir('DELIMITER')                         # Se espera un ;

        return lexico.NodoAsignacion(tipo, nombre, expresion)        
    
    def retorno(self):
        self.coincidir('KEYWORD')                           # Se espera un return
        expresion = self.expresion()
        self.coincidir('DELIMITER')
        return lexico.NodoRetorno(expresion)
    
    def expresion(self):
        izquierda = self.termino()
        while self.obtener_token_actual() and self.obtener_token_actual()[0] == 'OPERATOR':
            operador = self.coincidir('OPERATOR')
            derecha = self.termino()
            izquierda = lexico.NodoOperacion(izquierda, operador, derecha)
        return izquierda
    
    def termino(self):
        token = self.obtener_token_actual()
        if token[0] == 'NUMBER':
            return lexico.NodoNumero(self.coincidir('NUMBER'))
        elif token[0] =='IDENTIFIER':
            identificador = self.coincidir('IDENTIFIER')
            if self.obtener_token_actual() and self.obtener_token_actual()[1] == '(':
                
                self.coincidir('DELIMITER')
                argumentos = self.llamadaFuncion()
                self.coincidir('DELIMITER')
                return lexico.NodoLlamadaFuncion(identificador[1], argumentos)
            else:
                return lexico.NodoIdentificador(identificador)
        else:
            raise SyntaxError(f'Expresion no valida: {token}')
    
    def llamadaFuncion(self):
        argumentos = []
        # Reglas para argumentos: IDENTIFIER | NUMBER (, IDENTIFIER | NUMBER)*
        sigue = True
        token = self.obtener_token_actual()
        while sigue: 
            sigue = False
            if token[0] == 'NUMBER':
                argumento = lexico.NodoNumero(self.coincidir('NUMBER'))
            elif token[0] == 'IDENTIFIER':
                argumento = lexico.NodoIdentificador(self.coincidir('IDENTIFIER'))
            else:
                raise SyntaxError(f'Error de sinaxxis, se esperaba un identificador o numero pero se encontro token actual')
            argumentos.append(argumento)
            if self.obtener_token_actual() and self.obtener_token_actual()[1] == ',':
                self.coincidir('DELIMITER')     # Se espera una coma
                token = self.obtener_token_actual()
                sigue = True
        return argumentos
    
    def llamadaComoInstruccion(self):
        identificador = self.coincidir('IDENTIFIER')
        self.coincidir('DELIMITER')  # (
        argumentos = self.llamadaFuncion()
        self.coincidir('DELIMITER')  # )
        self.coincidir('DELIMITER')  # ;

        return lexico.NodoLlamadaFuncion(identificador[1], argumentos)

