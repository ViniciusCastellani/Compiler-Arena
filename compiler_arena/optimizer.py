"""Otimizações conservadoras por bloco básico, sem cruzar arestas do CFG."""
from copy import deepcopy
from dataclasses import replace
from .ir import constant, validate
from .runtime import calculate


def basic_blocks(ir):
    leaders = {0}
    for i, q in enumerate(ir):
        if q.op == 'LABEL': leaders.add(i)
        if q.op in ('JMP','JZ','JNZ','HALT') or q.op.startswith('CMD:'):
            if i+1 < len(ir): leaders.add(i+1)
    starts = sorted(leaders)
    blocks = [{'id': j, 'start': a, 'end': starts[j+1] if j+1 < len(starts) else len(ir), 'successors': []} for j, a in enumerate(starts)]
    labels = {ir[b['start']].result: b['id'] for b in blocks if ir[b['start']].op == 'LABEL'}
    for b in blocks:
        q = ir[b['end']-1]
        if q.op in ('JMP','JZ','JNZ'): b['successors'].append(labels[q.result])
        if q.op not in ('JMP','HALT') and b['id']+1 < len(blocks): b['successors'].append(b['id']+1)
    return blocks


def optimize(original):
    ir = deepcopy(original); log = []; blocks = basic_blocks(ir)
    for block in blocks:
        env = {}; discarded = False
        for i in range(block['start'], block['end']):
            q = ir[i]
            before = q.to_dict()
            if discarded: continue  # Não calcular nem mesmo constantes em trecho descartado.
            for field in ('arg1','arg2'):
                a = getattr(q, field)
                if a and a.kind in ('symbol','temporary') and a in env:
                    setattr(q, field, env[a])
            rule = None
            if q.op in ('JZ','JNZ') and q.arg1.kind == 'constant':
                taken = (not q.arg1.value) if q.op == 'JZ' else bool(q.arg1.value)
                discarded = taken
            try:
                if q.op.startswith('BIN:') and q.arg1.kind == q.arg2.kind == 'constant':
                    v = calculate(q.op[4:], q.arg1.value, q.arg2.value)
                    q = replace(q, op='COPY', arg1=constant(v,q.result.type), arg2=None); rule = 'constant folding'
                elif q.op.startswith('UN:') and q.arg1.kind == 'constant':
                    v = calculate(q.op[3:], q.arg1.value)
                    q = replace(q, op='COPY', arg1=constant(v,q.result.type)); rule = 'constant folding'
                elif q.op == 'I2F' and q.arg1.kind == 'constant':
                    q = replace(q, op='COPY', arg1=constant(float(q.arg1.value),'float')); rule = 'constant folding'
                elif q.op in ('BIN:+','BIN:-','BIN:*') and q.result.type == 'int' and q.arg2.kind == 'constant':
                    identity = 1 if q.op == 'BIN:*' else 0
                    if q.arg2.value == identity:
                        q = replace(q, op='COPY', arg2=None); rule = 'simplificação algébrica int'
            except (ValueError, OverflowError, ZeroDivisionError):
                pass  # Preserva erro dinâmico e não avalia blocos possivelmente inalcançáveis.
            if q.result and q.result.kind in ('symbol','temporary'):
                env.pop(q.result, None)
                if q.op == 'COPY' and q.arg1.kind == 'constant': env[q.result] = q.arg1
            ir[i] = q
            if q.to_dict() != before:
                log.append({'rule': rule or 'propagação local', 'index': i, 'before': before, 'after': q.to_dict(), 'line': q.line, 'column': q.column})
    # Só COPY para temporário sem usos: a origem já foi avaliada, não pode lançar erro.
    used = {a for q in ir for a in (q.arg1,q.arg2) if a}
    result = []
    for i, q in enumerate(ir):
        if q.op == 'COPY' and q.result.kind == 'temporary' and q.result not in used:
            log.append({'rule': 'remoção de cópia temporária sem uso', 'index': i, 'line': q.line, 'column': q.column, 'before': q.to_dict(), 'after': None})
        else: result.append(q)
    validate(result)
    return result, log, blocks
