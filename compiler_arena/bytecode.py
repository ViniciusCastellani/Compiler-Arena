"""Formato JSON explícito e validação de código objeto externo. Sem compilador."""
import json
from pathlib import Path
from .runtime import TYPES, SENSORS, COMMANDS, checked, type_of, result_type

NAMES = ['HALT','COPY','I2F','SENSOR','JMP','JZ','JNZ'] + ['UN:'+x for x in ('!','+','-')] + ['BIN:'+x for x in ('+','-','*','/','%','<','<=','>','>=','==','!=')] + ['CMD:'+x for x in COMMANDS]
OPCODES = {name: i for i,name in enumerate(NAMES)}
MAX_CODE = 50000
MAX_REGISTERS = 10000
MAX_FILE = 8_000_000


class BytecodeError(ValueError): pass


def validate(data):
    def bad(msg): raise BytecodeError('Erro de carregamento de bytecode: '+msg)
    if not isinstance(data,dict) or type(data.get('version')) is not int or data['version'] != 1: bad('versão inválida')
    if not isinstance(data.get('robot'),str) or not 1 <= len(data['robot']) <= 128: bad('identificação inválida')
    ts = data.get('register_types'); code = data.get('instructions')
    if not isinstance(ts,list) or len(ts)>MAX_REGISTERS or any(t not in TYPES for t in ts): bad('tipos/limite de registradores')
    if not isinstance(code,list) or not 1 <= len(code) <= MAX_CODE: bad('quantidade de instruções inválida')
    def reg(x):
        if type(x) is not int or not 0 <= x < len(ts): bad('referência de memória inválida')
        return ts[x]
    def operand(x):
        if not isinstance(x,list) or not x: bad('operando malformado')
        if x[0]=='r' and len(x)==2: return reg(x[1])
        if x[0]=='c' and len(x)==3 and x[1] in TYPES:
            try: checked(x[2])
            except ValueError as e: bad(str(e))
            if type_of(x[2]) != x[1]: bad('constante de tipo incompatível')
            return x[1]
        bad('categoria ou quantidade de campos do operando')
    def jump(x):
        if type(x) is not int or not 0 <= x < len(code): bad('destino de salto inválido')
    for row in code:
        if not isinstance(row,dict): bad('instrução malformada')
        op = row.get('opcode'); a = row.get('args'); pos = row.get('source',[1,1])
        if type(op) is not int or not 0 <= op < len(NAMES): bad('opcode desconhecido')
        if not isinstance(a,list): bad('argumentos inválidos')
        if not isinstance(pos,list) or len(pos)!=2 or any(type(p) is not int or p<1 for p in pos): bad('origem inválida')
        name = NAMES[op]
        count = 0 if name in ('HALT','CMD:scan') else 1 if name=='JMP' or name.startswith('CMD:') else 3 if name.startswith('BIN:') else 2
        if len(a)!=count: bad(f'{name}: quantidade de operandos')
        if name == 'JMP': jump(a[0])
        elif name in ('JZ','JNZ'):
            if operand(a[0])!='bool': bad('desvio exige bool')
            jump(a[1])
        elif name.startswith('CMD:') and a:
            typ = operand(a[0]); rule = COMMANDS[name[4:]]
            if rule[0]=='int' and typ!='int' or rule[0]=='number' and typ not in ('int','float'): bad('tipo de argumento de comando')
        elif name not in ('HALT','CMD:scan'):
            dest, src = reg(a[0]), operand(a[1])
            if name == 'SENSOR':
                if a[1][0]!='c' or a[1][2] not in SENSORS or dest!=SENSORS[a[1][2]]: bad('sensor inválido')
            elif name=='COPY':
                if dest!=src: bad('COPY exige tipos iguais; use I2F')
            elif name=='I2F':
                if src!='int' or dest!='float': bad('conversão inválida')
            else:
                try: expected = result_type(name.split(':')[1],src,operand(a[2]) if name.startswith('BIN:') else None)
                except ValueError as e: bad(str(e))
                if expected!=dest: bad('tipo do resultado inválido')
    return data


def load(path):
    path = Path(path)
    if path.stat().st_size > MAX_FILE: raise BytecodeError('Erro de carregamento de bytecode: arquivo excede 8 MB')
    try:
        return validate(json.loads(path.read_text(encoding='utf-8')))
    except (json.JSONDecodeError, RecursionError, UnicodeError) as e:
        raise BytecodeError('Erro de carregamento de bytecode: JSON inválido') from e


def save(data,path):
    validate(data)
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
