"""Validação separada; anota a AST com tipos e identidades únicas."""
from dataclasses import dataclass, asdict
from .runtime import (SENSORS, COMMANDS, RESERVED, DEFAULT, type_of, checked,
                      compatible, result_type, calculate, validate_command)

UNKNOWN = object()


@dataclass
class Symbol:
    id: int
    name: str
    type: str
    scope: int
    mutable: bool
    line: int
    column: int
    constant: object = None

    def to_dict(self): return asdict(self)


class Semantic:
    def __init__(self):
        self.scopes = []
        self.symbols = []
        self.errors = []
        self.scope_id = 0
        self.loops = 0

    def fail(self, node, message):
        raise ValueError(f'Erro semântico na linha {node.line}, coluna {node.column}: {message}.')

    def resolve(self, node):
        for _, scope in reversed(self.scopes):
            if node.valor in scope: return scope[node.valor]
        self.fail(node, f'símbolo {node.valor} não declarado ou fora de escopo')

    def analyze(self, root):
        if root.valor in RESERVED or len(root.valor)>128:
            self.errors.append(f'Erro semântico na linha {root.line}, coluna {root.column}: nome do robô reservado ou maior que 128 caracteres.')
            return self.symbols, self.errors
        self.statement(root.filhos[0])
        return self.symbols, self.errors

    def block(self, node):
        self.scope_id += 1
        self.scopes.append((self.scope_id, {}))
        for child in node.filhos:
            if len(self.errors) >= 50: break
            try: self.statement(child)
            except (ValueError, OverflowError) as error: self.errors.append(str(error))
        self.scopes.pop()

    def expression(self, n, evaluate=True):
        constant = UNKNOWN
        if n.tipo == 'LITERAL':
            typ = type_of(n.valor)
            try: constant = checked(n.valor)
            except ValueError as e: self.fail(n, str(e))
        elif n.tipo == 'IDENTIFICADOR':
            if n.valor in SENSORS:
                typ = SENSORS[n.valor]; n.meta['sensor'] = n.valor
            else:
                if n.valor in RESERVED or '.' in n.valor: self.fail(n, f'sensor inexistente {n.valor}')
                sym = self.resolve(n); typ = sym.type; n.meta['symbol'] = sym.id
                if not sym.mutable: constant = sym.constant
        elif n.tipo in ('BIN', 'UNARY'):
            lt, a = self.expression(n.filhos[0], evaluate)
            b = UNKNOWN; rt = None
            if n.tipo == 'BIN':
                skip = (n.valor == '&&' and a is False) or (n.valor == '||' and a is True)
                rt, b = self.expression(n.filhos[1], evaluate and not skip)
            else: skip = False
            try:
                typ = result_type(n.valor, lt, rt)
                if evaluate and a is not UNKNOWN:
                    if skip: constant = a
                    elif n.tipo == 'UNARY': constant = calculate(n.valor, a)
                    elif b is not UNKNOWN: constant = calculate(n.valor, a, b)
            except (ValueError, OverflowError, ZeroDivisionError) as e: self.fail(n, str(e))
        else: self.fail(n, 'expressão inválida')
        n.meta['type'] = typ
        if constant is not UNKNOWN: n.meta['constant'] = constant
        return typ, constant

    def assign_type(self, n, dest, src, value=UNKNOWN):
        if not compatible(dest, src): self.fail(n, f'atribuição de {src} para {dest} não permitida')
        if dest == 'float' and src == 'int' and value is not UNKNOWN:
            try: checked(float(value))
            except (ValueError, OverflowError) as error: self.fail(n, f'conversão para float inválida: {error}')

    def statement(self, n):
        if n.tipo == 'BLOCO': return self.block(n)
        if n.tipo == 'DECL':
            typ = n.meta['decl_type']; const = n.meta['const']
            sid, scope = self.scopes[-1]
            if n.valor in RESERVED: self.fail(n, f'nome reservado {n.valor}')
            if n.valor in scope: self.fail(n, f'declaração duplicada de {n.valor}')
            et, val = self.expression(n.filhos[0]) if n.filhos else (typ, DEFAULT[typ])
            self.assign_type(n, typ, et, val)
            def constant_only(expr):
                if expr.tipo == 'IDENTIFICADOR':
                    if 'sensor' in expr.meta: return False
                    return not self.symbols[expr.meta['symbol']].mutable
                return all(constant_only(c) for c in expr.filhos)
            if const and (val is UNKNOWN or not constant_only(n.filhos[0])):
                self.fail(n, 'constante depende de variável ou sensor')
            if const and typ == 'float': val = float(val)
            sym = Symbol(len(self.symbols), n.valor, typ, sid, not const, n.line, n.column, val if const else None)
            self.symbols.append(sym); scope[n.valor] = sym
            n.meta.update(symbol=sym.id, type=typ)
        elif n.tipo == 'ATRIBUICAO':
            target, expr = n.filhos
            if target.valor in SENSORS or target.valor.split('.')[0] in RESERVED:
                self.fail(target, 'sensor somente leitura ou nome reservado')
            sym = self.resolve(target)
            if not sym.mutable: self.fail(n, f'constante {sym.name} não recebe atribuição')
            et, val = self.expression(expr)
            if n.valor != '=':
                try: et = result_type(n.valor[0], sym.type, et)
                except ValueError as e: self.fail(n, str(e))
            self.assign_type(n, sym.type, et, val if n.valor == '=' else UNKNOWN)
            target.meta.update(symbol=sym.id, type=sym.type)
            n.meta.update(type=sym.type, operation_type=et)
        elif n.tipo in ('IF', 'WHILE'):
            typ, _ = self.expression(n.filhos[0])
            if typ != 'bool': self.fail(n, 'condição exige bool')
            if n.tipo == 'WHILE': self.loops += 1
            for child in n.filhos[1:]: self.statement(child)
            if n.tipo == 'WHILE': self.loops -= 1
        elif n.tipo in ('BREAK', 'CONTINUE'):
            if not self.loops: self.fail(n, f'{n.tipo.lower()} somente dentro de while')
        elif n.tipo == 'CALL':
            vals = [self.expression(arg) for arg in n.filhos]
            if n.valor not in COMMANDS: self.fail(n, f'comando desconhecido {n.valor}')
            rule = COMMANDS[n.valor]
            if len(vals) != (0 if rule is None else 1): self.fail(n, f'{n.valor}: quantidade de argumentos inválida')
            if rule:
                typ, value = vals[0]
                if rule[0] == 'int' and typ != 'int' or rule[0] == 'number' and typ not in ('int','float'):
                    self.fail(n, f'{n.valor} espera {rule[0]} entre {rule[1]} e {rule[2]}; recebido {typ}')
                if value is not UNKNOWN:
                    try: validate_command(n.valor, [value])
                    except ValueError as e: self.fail(n, str(e))
