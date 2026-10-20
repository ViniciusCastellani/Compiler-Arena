"""IR de três endereços, com operandos categorizados e origem."""
from dataclasses import dataclass, asdict
from .runtime import DEFAULT


@dataclass(frozen=True)
class Operand:
    kind: str  # constant, symbol, temporary, label
    value: object
    type: str

    def to_dict(self): return asdict(self)


@dataclass
class Quad:
    op: str
    arg1: Operand | None = None
    arg2: Operand | None = None
    result: Operand | None = None
    type: str = 'void'
    line: int = 1
    column: int = 1

    def to_dict(self): return asdict(self)


def constant(value, typ): return Operand('constant', value, typ)


def render(ir):
    def fmt(x):
        if x is None: return '-'
        if x.kind == 'constant': return repr(x.value)
        return {'symbol': 's', 'temporary': 't', 'label': 'L'}[x.kind] + str(x.value)
    return '\n'.join(f'{i:04} {q.op:9} {fmt(q.arg1):18} {fmt(q.arg2):18} -> {fmt(q.result):10} :{q.type} @{q.line}:{q.column}' for i, q in enumerate(ir))


class Builder:
    def __init__(self):
        self.ir = []; self.temps = 0; self.labels = 0; self.loops = []

    def temp(self, typ):
        self.temps += 1
        return Operand('temporary', self.temps, typ)

    def label(self):
        self.labels += 1
        return Operand('label', self.labels, 'label')

    def emit(self, op, a=None, b=None, r=None, n=None):
        self.ir.append(Quad(op, a, b, r, r.type if r and r.kind != 'label' else 'void', n.line if n else 1, n.column if n else 1))

    def convert(self, value, typ, n):
        if value.type == 'int' and typ == 'float':
            out = self.temp('float'); self.emit('I2F', value, r=out, n=n); return out
        return value

    def binary(self, op, a, b, typ, n):
        if a.type in ('int','float') and b.type in ('int','float') and a.type != b.type:
            a = self.convert(a, 'float', n); b = self.convert(b, 'float', n)
        out = self.temp(typ); self.emit('BIN:' + op, a, b, out, n); return out

    def expression(self, n):
        typ = n.meta['type']
        if n.tipo == 'LITERAL': return constant(n.valor, typ)
        if n.tipo == 'IDENTIFICADOR':
            if 'sensor' in n.meta:
                out = self.temp(typ)
                self.emit('SENSOR', constant(n.valor, 'string'), r=out, n=n); return out
            return Operand('symbol', n.meta['symbol'], typ)
        if n.tipo == 'UNARY':
            a = self.expression(n.filhos[0]); out = self.temp(typ)
            self.emit('UN:' + n.valor, a, r=out, n=n); return out
        if n.valor in ('&&', '||'):
            out = self.temp('bool'); end = self.label()
            a = self.expression(n.filhos[0]); self.emit('COPY', a, r=out, n=n)
            self.emit('JZ' if n.valor == '&&' else 'JNZ', out, r=end, n=n)
            b = self.expression(n.filhos[1]); self.emit('COPY', b, r=out, n=n)
            self.emit('LABEL', r=end, n=n); return out
        a = self.expression(n.filhos[0]); b = self.expression(n.filhos[1])
        return self.binary(n.valor, a, b, typ, n)

    def statement(self, n):
        if n.tipo == 'BLOCO':
            for child in n.filhos: self.statement(child)
        elif n.tipo == 'DECL':
            dest = Operand('symbol', n.meta['symbol'], n.meta['type'])
            val = self.expression(n.filhos[0]) if n.filhos else constant(DEFAULT[dest.type], dest.type)
            self.emit('COPY', self.convert(val, dest.type, n), r=dest, n=n)
        elif n.tipo == 'ATRIBUICAO':
            target, expr = n.filhos
            dest = Operand('symbol', target.meta['symbol'], target.meta['type'])
            val = self.expression(expr)
            if n.valor != '=': val = self.binary(n.valor[0], dest, val, n.meta['operation_type'], n)
            self.emit('COPY', self.convert(val, dest.type, n), r=dest, n=n)
        elif n.tipo == 'CALL':
            a = self.expression(n.filhos[0]) if n.filhos else None
            self.emit('CMD:' + n.valor, a, n=n)
        elif n.tipo == 'IF':
            other, end = self.label(), self.label()
            self.emit('JZ', self.expression(n.filhos[0]), r=other, n=n)
            self.statement(n.filhos[1]); self.emit('JMP', r=end, n=n)
            self.emit('LABEL', r=other, n=n)
            if len(n.filhos) == 3: self.statement(n.filhos[2])
            self.emit('LABEL', r=end, n=n)
        elif n.tipo == 'WHILE':
            start, end = self.label(), self.label()
            self.emit('LABEL', r=start, n=n)
            self.emit('JZ', self.expression(n.filhos[0]), r=end, n=n)
            self.loops.append((start, end)); self.statement(n.filhos[1]); self.loops.pop()
            self.emit('JMP', r=start, n=n); self.emit('LABEL', r=end, n=n)
        elif n.tipo in ('BREAK','CONTINUE'):
            self.emit('JMP', r=self.loops[-1][0 if n.tipo == 'CONTINUE' else 1], n=n)

    def build(self, root):
        self.statement(root.filhos[0]); self.emit('HALT', n=root)
        validate(self.ir)
        return self.ir


def validate(ir):
    """Valida categorias, aridade, tipos, identidades e destinos das quádruplas."""
    from .runtime import TYPES, checked, type_of
    from .bytecode import OPCODES
    if not isinstance(ir,list) or not ir: raise ValueError('IR vazia ou inválida')
    labels=[]; identities={}
    for q in ir:
        if not isinstance(q,Quad): raise ValueError('quádrupla inválida')
        for operand in (q.arg1,q.arg2,q.result):
            if operand is None: continue
            if not isinstance(operand,Operand) or operand.kind not in ('constant','symbol','temporary','label'):
                raise ValueError('categoria de operando IR inválida')
            if operand.kind == 'label':
                if operand.type != 'label': raise ValueError('tipo de rótulo inválido')
            elif operand.type not in TYPES: raise ValueError('tipo de operando IR inválido')
            if operand.kind == 'constant':
                checked(operand.value)
                if type_of(operand.value)!=operand.type: raise ValueError('tipo da constante IR incompatível')
            else:
                if type(operand.value) is not int or operand.value<0: raise ValueError('identidade IR inválida')
                key=(operand.kind,operand.value)
                if key in identities and identities[key]!=operand.type: raise ValueError('identidade IR com tipos conflitantes')
                identities[key]=operand.type
        expected=q.result.type if q.result and q.result.kind!='label' else 'void'
        if q.type!=expected: raise ValueError('metadado de tipo IR incompatível')
        if q.op == 'LABEL':
            if not q.result or q.result.kind!='label' or q.arg1 or q.arg2: raise ValueError('definição de rótulo inválida')
            labels.append(q.result)
        elif q.op not in OPCODES: raise ValueError('operação IR desconhecida')
        elif q.op in ('JMP','JZ','JNZ'):
            if not q.result or q.result.kind!='label' or q.arg2: raise ValueError('destino de salto IR inválido')
            if (q.op=='JMP' and q.arg1) or (q.op!='JMP' and not q.arg1): raise ValueError('aridade de salto IR inválida')
        elif q.op.startswith('CMD:') or q.op=='HALT':
            if q.result or q.arg2: raise ValueError('aridade de comando IR inválida')
            has_arg=q.op not in ('HALT','CMD:scan')
            if bool(q.arg1)!=has_arg: raise ValueError('argumento de comando IR inválido')
        else:
            if not q.result or q.result.kind not in ('symbol','temporary') or not q.arg1: raise ValueError('destino/argumento IR inválido')
            if bool(q.arg2)!=q.op.startswith('BIN:'): raise ValueError('aridade de operação IR inválida')
    if len(set(labels))!=len(labels): raise ValueError('rótulo IR duplicado')
    for q in ir:
        if q.op in ('JMP','JZ','JNZ') and q.result not in labels: raise ValueError('salto IR sem rótulo')
    from .codegen import generate
    try: generate(ir,'validacao',validate_ir=False)
    except (KeyError,TypeError,AttributeError) as error: raise ValueError('operandos IR incompatíveis') from error
