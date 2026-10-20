"""Verificação determinística de progresso/recuperação em fontes malformadas."""
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from compiler_arena.compiler import compile_source


def main():
    rng=random.Random(2026)
    atoms=['robot','int','float','bool','true','const','{','}','(',')',';','scan','if','while','else','x','1','0','+','/','=','&&','"s"']
    for _ in range(1200):
        report=compile_source(' '.join(rng.choices(atoms,k=rng.randrange(1,70))))
        assert report['diagnostics'] or report['bytecode']
    print('1200 entradas malformadas processadas sem exceção não tratada; semente 2026.')


if __name__=='__main__': main()
