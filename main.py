"""Entrada CLI e web do Compiler Arena."""
import argparse
import json
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description='Compiler Arena — RoboLang')
    sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('compile',help='compilar e exportar etapas')
    c.add_argument('source'); c.add_argument('--no-opt',action='store_true'); c.add_argument('--out',default='artefatos/compilacao')
    r=sub.add_parser('run',help='executar bytecode com sensores controlados')
    r.add_argument('bytecode'); r.add_argument('--ticks',type=int,default=100); r.add_argument('--budget',type=int,default=100)
    b=sub.add_parser('battle',help='batalha de bytecodes')
    b.add_argument('bytecodes',nargs='+'); b.add_argument('--ticks',type=int,default=1000); b.add_argument('--budget',type=int,default=100); b.add_argument('--seed',type=int,default=0); b.add_argument('--out',default='artefatos/batalha.json'); b.add_argument('--visual',action='store_true')
    web=sub.add_parser('web',aliases=['gui'],help='abrir interface HTML no navegador')
    web.add_argument('--port',type=int,default=8000)
    web.add_argument('--no-browser',action='store_true')
    args=p.parse_args()
    try:
        if args.command in ('web','gui'):
            from compiler_arena.interface import launch
            launch(args.port,not args.no_browser); return 0
        if args.command=='compile':
            from compiler_arena.compiler import compile_source,export_report
            report=compile_source(Path(args.source).read_text(encoding='utf-8'),not args.no_opt)
            export_report(report,args.out)
            print(json.dumps({'stages':report['stages'],'diagnostics':report['diagnostics'],'metrics':report.get('metrics'),'out':args.out},ensure_ascii=False,indent=2))
            return 1 if report['diagnostics'] else 0
        from compiler_arena.bytecode import load
        if args.command=='run':
            from compiler_arena.vm import VM
            from compiler_arena.arena import EMPTY_SCAN
            vm=VM(load(args.bytecode)); actions=[]
            for tick in range(args.ticks):
                cmd=vm.tick({'energy':100,'position.x':0.0,'position.y':0.0,**EMPTY_SCAN},args.budget)
                if cmd: actions.append({'tick':tick+1,'command':cmd})
                if vm.state in ('erro','finalizada'): break
            print(json.dumps({'state':vm.state,'error':vm.error,'memory':vm.memory,'actions':actions},ensure_ascii=False,indent=2))
            return 1 if vm.error else 0
        from compiler_arena.arena import Arena
        programs=[load(path) for path in args.bytecodes]
        arena=Arena(programs,args.ticks,args.budget,args.seed)
        if args.visual:
            from compiler_arena.visual import run_visual
            arena=run_visual(arena)
        else: arena.run()
        out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps({'snapshot':arena.snapshot(),'logs':arena.logs,'seed':args.seed,'budget':args.budget},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(arena.snapshot(),ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError,ImportError) as e:
        print(str(e),file=sys.stderr); return 2


if __name__=='__main__': raise SystemExit(main())
