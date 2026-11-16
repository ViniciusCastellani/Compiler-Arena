"""Orquestração e relatórios; nenhum artefato executável em caso de erro."""
import hashlib
import json
from pathlib import Path
from dataclasses import asdict
from .lexer import Lexer, TokenType
from .parser import Parser
from .semantic import Semantic
from .ir import Builder, render
from .optimizer import optimize
from .codegen import generate

STAGES = ['léxica','sintática','semântica','IR','otimização','bytecode']


def compile_source(source, optimization=True):
    report = {'source': source, 'sha256': hashlib.sha256(source.encode()).hexdigest(),
              'stages': {s:'não executada' for s in STAGES}, 'diagnostics': [],
              'tokens': [], 'ast': None, 'symbols': [], 'ir': [], 'optimized_ir': [],
              'optimizations': [], 'blocks': [], 'bytecode': None}
    if len(source)>250000:
        report['diagnostics']=['Erro léxico na linha 1, coluna 1: fonte excede 250000 caracteres.']
        report['stages']['léxica']='erro'; return report
    tokens = Lexer(source).tokenize()
    report['tokens']=[{'type':t.type.name,'lexeme':t.lexeme,'value':t.value,'line':t.line,'column':t.column} for t in tokens]
    errors = [f'Erro léxico na linha {t.line}, coluna {t.column}: {t.value or "token inválido"} ({t.lexeme!r}).' for t in tokens if t.type is TokenType.ERRO]
    if errors:
        report['diagnostics']=errors[:50]; report['stages']['léxica']='erro'; return report
    report['stages']['léxica']='concluída'
    root, errors = Parser(tokens).parse()
    if errors:
        report['diagnostics']=[f'{e.message} Linha {e.line}, coluna {e.column}.' for e in errors]
        report['stages']['sintática']='erro'; return report
    # Limite explícito da árvore, inclusive para cadeias associativas à esquerda.
    pending=[(root,0)]
    while pending:
        node,depth=pending.pop()
        if depth>100:
            report['stages']['sintática']='erro'
            report['diagnostics']=[f'Erro sintático na linha {node.line}, coluna {node.column}: AST excede 100 níveis.']
            return report
        pending.extend((c,depth+1) for c in node.filhos)
    report['ast']=root.to_dict(); report['stages']['sintática']='concluída'
    sem = Semantic()
    try: symbols, errors = sem.analyze(root)
    except RecursionError:
        symbols,errors=sem.symbols,['Erro semântico na linha 1, coluna 1: árvore excede profundidade suportada.']
    report['symbols']=[s.to_dict() for s in symbols]
    if errors:
        report['diagnostics']=errors; report['stages']['semântica']='erro'; return report
    report['stages']['semântica']='concluída'; report['ast']=root.to_dict()
    try: ir=Builder().build(root)
    except ValueError as error:
        report['stages']['IR']='erro'
        report['diagnostics']=[f'Erro de geração de IR na linha 1, coluna 1: {error}.']
        return report
    report['ir']=[q.to_dict() for q in ir]; report['ir_text']=render(ir)
    report['stages']['IR']='concluída'
    optimized, log, blocks = optimize(ir) if optimization else (ir, [], [])
    report['optimized_ir']=[q.to_dict() for q in optimized]; report['optimized_ir_text']=render(optimized)
    report['optimizations']=log; report['blocks']=blocks
    report['stages']['otimização']='concluída' if optimization else 'desativada'
    report['metrics']={'before':len(ir),'after':len(optimized),'reduction_percent':100*(len(ir)-len(optimized))/len(ir) if ir else 0}
    report['bytecode']=generate(optimized,root.valor)
    report['stages']['bytecode']='concluída'
    return report


def export_report(report,directory):
    path=Path(directory); path.mkdir(parents=True,exist_ok=True)
    def write(name,data): (path/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    write('relatorio.json',report)
    for key in ('tokens','ast','symbols','ir','optimized_ir','optimizations','blocks'):
        write(key+'.json',report[key])
    for key in ('ir_text','optimized_ir_text'):
        (path/(key+'.txt')).write_text(report.get(key,''),encoding='utf-8')
    (path/'fonte.robo').write_text(report['source'],encoding='utf-8')
    if report['bytecode']: write('robot.rbc.json',report['bytecode'])
    elif (path/'robot.rbc.json').exists(): (path/'robot.rbc.json').unlink()
