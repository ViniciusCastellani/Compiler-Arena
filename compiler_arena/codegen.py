"""Atribui registradores e resolve rótulos; bytecode distinto da IR."""
from .bytecode import OPCODES, validate


def generate(ir, robot, validate_ir=True):
    registers = {}; types = []; labels = {}; pc = 0
    for q in ir:
        if q.op == 'LABEL': labels[q.result] = pc
        else: pc += 1
        for a in (q.arg1, q.arg2, q.result):
            if a and a.kind in ('symbol','temporary') and a not in registers:
                registers[a] = len(types); types.append(a.type)
    def read(a):
        if a is None: return None
        if a.kind == 'constant': return ['c',a.type,a.value]
        return ['r', registers[a]]
    code = []
    for q in ir:
        if q.op == 'LABEL': continue
        op = q.op
        args = []
        if op in ('COPY','I2F') or op.startswith('UN:') or op == 'SENSOR': args = [registers[q.result],read(q.arg1)]
        elif op.startswith('BIN:'): args = [registers[q.result],read(q.arg1),read(q.arg2)]
        elif op == 'JMP': args = [labels[q.result]]
        elif op in ('JZ','JNZ'): args = [read(q.arg1), labels[q.result]]
        elif op.startswith('CMD:'): args = [read(q.arg1)] if q.arg1 else []
        code.append({'opcode': OPCODES[op], 'args': args, 'source': [q.line,q.column]})
    out = {'version': 1, 'robot': robot, 'register_types': types, 'instructions': code}
    validate(out)
    return out
