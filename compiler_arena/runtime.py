"""Regras de valores compartilhadas pela avaliação constante e pela VM."""
import math
import operator

TYPES = ('int', 'float', 'bool', 'string')
DEFAULT = {'int': 0, 'float': 0.0, 'bool': False, 'string': ''}
SENSORS = {'energy': 'int', 'position.x': 'float', 'position.y': 'float',
           'enemy.visible': 'bool', 'enemy.distance': 'float', 'enemy.direction': 'float'}
COMMANDS = {'move': ('number', 0, 100), 'back': ('number', 0, 100),
            'rotate': ('number', -360, 360), 'scan': None, 'fire': ('int', 1, 3)}
RESERVED = set(COMMANDS) | {'energy', 'position', 'enemy'}
MAX_INT_BITS = 4096
MAX_STRING = 16384


def type_of(value):
    return {int: 'int', float: 'float', bool: 'bool', str: 'string'}.get(type(value))


def checked(value):
    typ = type_of(value)
    if typ is None: raise ValueError('tipo de valor inválido')
    if typ == 'float' and not math.isfinite(value): raise ValueError('float não finito')
    if typ == 'int' and value.bit_length() > MAX_INT_BITS: raise ValueError('inteiro excede 4096 bits')
    if typ == 'string' and len(value) > MAX_STRING: raise ValueError('string excede 16384 caracteres')
    return value


def compatible(dest, src):
    return dest == src or (dest == 'float' and src == 'int')


def result_type(op, left, right=None):
    numeric = ('int', 'float')
    if right is None:
        if op == '!' and left == 'bool': return 'bool'
        if op in ('+', '-') and left in numeric: return left
    elif op in ('&&', '||'):
        if left == right == 'bool': return 'bool'
    elif op in ('==', '!='):
        if left == right or left in numeric and right in numeric: return 'bool'
    elif op in ('<', '<=', '>', '>='):
        if left in numeric and right in numeric: return 'bool'
    elif op == '+' and left == right == 'string': return 'string'
    elif op == '%':
        if left == right == 'int': return 'int'
    elif op in ('+', '-', '*', '/') and left in numeric and right in numeric:
        return 'float' if op == '/' or 'float' in (left, right) else 'int'
    raise ValueError(f'operador {op} incompatível com {left}' + (f' e {right}' if right else ''))


BINARY = {'+': operator.add, '-': operator.sub, '*': operator.mul,
          '/': operator.truediv, '%': operator.mod, '<': operator.lt,
          '<=': operator.le, '>': operator.gt, '>=': operator.ge,
          '==': operator.eq, '!=': operator.ne, '&&': operator.and_, '||': operator.or_}


def calculate(op, a, b=None):
    result_type(op, type_of(a), type_of(b) if b is not None else None)
    if b is None:
        return checked({'!': operator.not_, '+': operator.pos, '-': operator.neg}[op](a))
    if type_of(a) in ('int','float') and type_of(b) in ('int','float') and type_of(a) != type_of(b):
        a, b = checked(float(a)), checked(float(b))
    if op in ('/', '%') and b == 0: raise ValueError('divisão ou resto por zero')
    return checked(BINARY[op](a, b))


def validate_command(name, args):
    if name not in COMMANDS: raise ValueError(f'comando desconhecido: {name}')
    rule = COMMANDS[name]
    if len(args) != (0 if rule is None else 1): raise ValueError(f'{name}: quantidade de argumentos inválida')
    if rule is None: return
    val = checked(args[0]); typ, low, high = rule
    actual = type_of(val)
    if (typ == 'number' and actual not in ('int', 'float')) or (typ != 'number' and actual != typ):
        raise ValueError(f'{name} espera {typ} entre {low} e {high}; recebido {actual}')
    if not low <= val <= high: raise ValueError(f'{name} espera valor entre {low} e {high}; recebido {val}')
