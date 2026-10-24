"""VM de registradores: depende apenas do bytecode e das regras de valores."""
from copy import deepcopy
from .bytecode import validate, NAMES
from .runtime import DEFAULT, checked, calculate, clamp_command, type_of


class VM:
    def __init__(self, bytecode):
        self.program = deepcopy(validate(bytecode))
        self.memory = [DEFAULT[t] for t in bytecode['register_types']]
        self.pc = 0
        self.state = 'pronta'
        self.error = None
        self.executed = 0
        self.clamped_from = None  # argumentos originais do último comando limitado

    def read(self, operand):
        return operand[2] if operand[0]=='c' else self.memory[operand[1]]

    def tick(self, sensors, budget=100):
        if type(budget) is not int or not 1 <= budget <= 100000: raise ValueError('orçamento deve estar entre 1 e 100000')
        if self.state in ('finalizada','erro'): return None
        self.state = 'pausada'
        for _ in range(budget):
            row = self.program['instructions'][self.pc]
            try:
                self.executed += 1
                name = NAMES[row['opcode']]; args = row['args']; self.pc += 1
                if name=='HALT': self.state='finalizada'; return None
                if name=='JMP': self.pc=args[0]
                elif name in ('JZ','JNZ'):
                    cond = self.read(args[0])
                    if (not cond) if name=='JZ' else cond: self.pc=args[1]
                elif name.startswith('CMD:'):
                    original = [self.read(a) for a in args]
                    values, clamped = clamp_command(name[4:],original)
                    self.clamped_from = original if clamped else None
                    # Fim físico do arquivo também finaliza; não acessa PC fora da memória.
                    if self.pc >= len(self.program['instructions']): self.state='finalizada'
                    return (name[4:],values)
                else:
                    dest, a = args[0], self.read(args[1])
                    if name=='COPY': value=a
                    elif name=='I2F': value=float(a)
                    elif name=='SENSOR': value=sensors[a]
                    elif name.startswith('UN:'): value=calculate(name[3:],a)
                    else: value=calculate(name[4:],a,self.read(args[2]))
                    value=checked(value)
                    if type_of(value) != self.program['register_types'][dest]:
                        raise ValueError('tipo dinâmico incompatível com registrador')
                    self.memory[dest] = value
                if self.pc >= len(self.program['instructions']): self.state='finalizada'; return None
            except (ValueError, OverflowError, ZeroDivisionError, KeyError, TypeError) as e:
                line,col = row.get('source',[1,1])
                self.error = f'Erro de execução na linha {line}, coluna {col}: {e}.'
                self.state='erro'; return None
        return None
