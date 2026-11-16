import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from compiler_arena.compiler import compile_source, export_report
from compiler_arena.lexer import Lexer, TokenType
from compiler_arena.runtime import calculate
from compiler_arena.bytecode import validate, load, OPCODES, BytecodeError
from compiler_arena.vm import VM
from compiler_arena.arena import Arena, EMPTY_SCAN

SENSORS={'energy':100,'hp':100,'heading':0.0,'hit':False,'position.x':0.0,'position.y':0.0,**EMPTY_SCAN}


def compile_body(body,opt=True): return compile_source('robot Teste { '+body+' }',opt)


def execute(body,opt=True,budget=100,ticks=1000):
    report=compile_body(body,opt)
    if report['diagnostics']: raise AssertionError(report['diagnostics'])
    vm=VM(report['bytecode']); actions=[]
    for _ in range(ticks):
        action=vm.tick(SENSORS,budget)
        if action: actions.append(action)
        if vm.state in ('finalizada','erro'): break
    return vm,actions,report


class LexicalTests(unittest.TestCase):
    def test_positions_comments_unicode(self):
        ts=Lexer('// ok\r\n/* x\n y */ int _x = 12.5; "Olá\\n\\t\\\"\\\\"').tokenize()
        self.assertEqual((ts[0].line,ts[0].column),(3,7))
        self.assertEqual(ts[3].value,12.5)
        self.assertEqual(ts[-2].value,'Olá\n\t"\\')

    def test_errors(self):
        for source in ['"x\\q"','"abc','/*abc','"a\nb"','1e3','12abc','++','--','&','|','@','"x\\\n"']:
            with self.subTest(source=source): self.assertTrue(any(t.type is TokenType.ERRO for t in Lexer(source).tokenize()))

    def test_opening_position(self):
        ts=Lexer('\n  /*never').tokenize()
        self.assertEqual((ts[0].line,ts[0].column),(2,3))

    def test_longest_and_case(self):
        ts=Lexer('+= -= *= /= == != <= >= && || ! Robot robot').tokenize()
        self.assertEqual([t.lexeme for t in ts[:10]],'+= -= *= /= == != <= >= && ||'.split())
        self.assertEqual(ts[-3].type,TokenType.IDENTIFICADOR)
        self.assertEqual(ts[-2].type,TokenType.PALAVRA_RESERVADA)


class SyntaxTests(unittest.TestCase):
    def test_exact_robot(self):
        for text in ['', 'int x;', 'robot A {} robot B {}','robot A {};','robot A {;}']:
            with self.subTest(text=text): self.assertIsNone(compile_source(text)['bytecode'])

    def test_invalid_grammar(self):
        for body in ['int a=1; int b=2; int c=3; bool x=a<b<c;', 'bool a=true==false==true;',
                     'if true {}', 'while (true) move(1);','int x=scan();','int a,b;', 'int a; int b; a=b=1;',
                     'int x=1; x++;', 'if (true) {} else move(1);']:
            with self.subTest(body=body): self.assertTrue(compile_body(body)['diagnostics'])

    def test_recovery(self):
        report=compile_body('int a=; int b=; scan();')
        self.assertEqual(len(report['diagnostics']),2)

    def test_depth_and_error_limit(self):
        for body in ['{'*150+'}'*150,'int x='+'('*150+'1'+')'*150+';','int x='+'-'*150+'1;']:
            report=compile_body(body); self.assertTrue(report['diagnostics']); self.assertIsNone(report['bytecode'])
        self.assertLessEqual(len(compile_body('int a=;'*100)['diagnostics']),50)

    def test_precedence_associativity(self):
        vm,actions,_=execute('int x=20-3-2*4; move(x); bool b=!false && true || false; if (b) { rotate(- -5); }')
        self.assertEqual(actions,[('move',[9]),('rotate',[5])]); self.assertEqual(vm.state,'finalizada')


class SemanticTests(unittest.TestCase):
    def test_errors(self):
        cases=['x=1;','int x; int x;', 'int x=true;','bool x=1;','string s=1;',
               'int x=1.0;', 'float x=true;', 'int x=1; x/=2;',
               'int x=1; x="s";', 'const int X=1; X+=1;',
               'int x=x+1;', 'if (1) {}', 'break;', 'continue;',
               'int energy;', 'int move;', 'position.x=1;', 'energy=1;',
               'float x=enemy.unknown;', 'int x=energy.x;', 'bool b=true; int x=b+1;',
               'string s="a"+1;', 'float x=1.2%1;', 'bool b="a"<"b";',
               'if (false) { missing=1; }','const int X=energy;',
               'int x=1; const int C=x;', 'bool v=false; const bool C=false && v;',
               'scan(1);','fire();','fire(true);','fire(4);','move(-1);','back(101);','rotate(361);','unknown();',
               '{int x=1;} move(x);']
        for body in cases:
            with self.subTest(body=body): self.assertIsNone(compile_body(body)['bytecode'])

    def test_defaults_and_promotion(self):
        vm,actions,_=execute('int x; float f; bool b; string s; f=3; s+="abc"; move(x); move(f); if (!b && s=="abc") { fire(1); }')
        self.assertEqual(actions,[('move',[0]),('move',[3.0]),('fire',[1])])
        self.assertIn(3.0,vm.memory)

    def test_shadow_and_initializer(self):
        _,actions,r=execute('int x=2; {int x=x+1; move(x);} move(x);')
        self.assertEqual(actions,[('move',[3]),('move',[2])])
        syms=r['symbols']; self.assertNotEqual(syms[0]['id'],syms[1]['id']); self.assertNotEqual(syms[0]['scope'],syms[1]['scope'])

    def test_reinitialize_and_nested_control(self):
        body='int i=0; while (i<3) { i+=1; int x=1; x+=1; int j=0; while (true) { j+=1; if (j==1) {continue;} break; } move(x+j); if (i==2) {continue;} rotate(i); }'
        _,actions,_=execute(body)
        self.assertEqual(actions,[('move',[4]),('rotate',[1]),('move',[4]),('move',[4]),('rotate',[3])])

    def test_constants(self):
        _,actions,_=execute('const int A=2; const float B=A+1; move(B); const string S="x"+"y"; if (S=="xy") {fire(A);}')
        self.assertEqual(actions,[('move',[3.0]),('fire',[2])])

    def test_short_circuit(self):
        for opt in (False,True):
            vm,actions,_=execute('bool x=false && (1/0>0); bool y=true || (1%0==0); if (!x && y) {move(1);}',opt)
            self.assertIsNone(vm.error); self.assertEqual(actions,[('move',[1])])
        self.assertTrue(compile_body('bool x=false && missing;')['diagnostics'])
        self.assertTrue(compile_body('bool x=true || 1;')['diagnostics'])

    def test_float_conversion_overflow_diagnostic(self):
        report=compile_body('float x='+('9'*400)+';')
        self.assertIsNone(report['bytecode'])
        self.assertIn('Erro semântico na linha',report['diagnostics'][0])

    def test_large_numeric_promotion_consistent(self):
        for opt in (False,True):
            _, actions, _=execute('const bool C=9007199254740993==9007199254740992.0; bool b=9007199254740993==9007199254740992.0; if (b==C) {move(1);}',opt)
            self.assertEqual(actions,[('move',[1])])

    def test_long_tree_and_nonfinite_export(self):
        self.assertTrue(compile_body('int x='+'+'.join(['1']*1000)+';')['diagnostics'])
        with tempfile.TemporaryDirectory() as tmp:
            export_report(compile_body('float x='+('9'*400)+'.0;'),tmp)
            self.assertTrue((Path(tmp)/'relatorio.json').exists())

    def test_static_and_dynamic_zero(self):
        for body in ['float x=1/0;','int x=1%0;','const float X=1/0;']:
            self.assertTrue(compile_body(body)['diagnostics'])
        for opt in (False,True):
            vm,_,_=execute('int z=0; float x=1/z;',opt)
            self.assertEqual(vm.state,'erro'); self.assertIn('zero',vm.error)

    def test_dynamic_command_clamped(self):
        cases={'int p=4; fire(p);':('fire',[3]),'int p=-2; fire(p);':('fire',[1]),
               'int d=101; move(d);':('move',[100]),'float a=-361.0; rotate(a);':('rotate',[-360.0])}
        for body,expected in cases.items():
            vm,actions,_=execute(body); self.assertIsNone(vm.error)
            self.assertEqual(actions,[expected]); self.assertIsNotNone(vm.clamped_from)
        vm,_,_=execute('float x=enemy.distance; move(x);'); self.assertEqual(vm.clamped_from,[-1.0])

    def test_numeric_rules(self):
        self.assertEqual(calculate('%',-5,3),1)
        vm,actions,_=execute('float x=5/2; move(x); if (1==1.0 && "a"!="b") {rotate(+2);}')
        self.assertEqual(actions,[('move',[2.5]),('rotate',[2])]); self.assertIsNone(vm.error)
        huge='9'*400
        self.assertTrue(compile_body(f'float x={huge}.0;')['diagnostics'])
        vm,_,_=execute('int i=0; string s="x"; while (i<20) {s+=s; i+=1;}')
        self.assertEqual(vm.state,'erro')


class BackendTests(unittest.TestCase):
    def test_ir_validation(self):
        from compiler_arena.ir import validate as validate_ir, Quad, Operand
        c=Operand('constant',1,'int'); t=Operand('temporary',1,'int'); label=Operand('label',1,'label')
        cases=[[],[Quad('FAKE')],[Quad('COPY',c,c,t,'int')],
               [Quad('COPY',Operand('constant',True,'int'),None,t,'int')],
               [Quad('JMP',result=label)], [Quad('COPY',c,None,t,'float')],
               [Quad('COPY',c,None,Operand('symbol',0,'int'),'int'),Quad('COPY',Operand('constant',1.0,'float'),None,Operand('symbol',0,'float'),'float')]]
        for ir in cases:
            with self.subTest(ir=ir):
                with self.assertRaises(ValueError): validate_ir(ir)

    def test_ir_bytecode_distinct(self):
        r=compile_body('int x=2; while (x>0) {move(x); x-=1;}')
        self.assertTrue(any(q['op']=='LABEL' for q in r['ir']))
        self.assertTrue(all(type(row['opcode']) is int for row in r['bytecode']['instructions']))
        self.assertTrue(any(a and a['kind']=='symbol' for q in r['ir'] for a in (q['arg1'],q['result'])))

    def test_optimization_equivalence(self):
        cases=['int x=10+20; move(x+0);','int x=2; if (energy>5) {x=3;} else {x=4;} move(x);',
               'int i=0; while (i<4) {move(i); i+=1;}','int x=0; float y=1/x;',
               'bool b=false && (1/0>0); if (b) {move(1);} scan();',
               'float x=position.x; float y=x+0.0; move(y);']
        for body in cases:
            with self.subTest(body=body):
                a,aa,_=execute(body,False); b,bb,_=execute(body,True)
                self.assertEqual(aa,bb); self.assertEqual(a.state,b.state); self.assertEqual(a.error,b.error)
        r=compile_body('int x=10+20; move(x+0);')
        self.assertLess(r['metrics']['after'],r['metrics']['before'])
        self.assertTrue(r['optimizations']); self.assertTrue(r['blocks'])

    def test_algebraic_and_no_cross_block(self):
        r=compile_body('int x=energy; move(x+0);')
        self.assertTrue(any('algébrica' in o['rule'] for o in r['optimizations']))
        _,actions,_=execute('int x=1; int i=0; while (i<3) {x+=1; i+=1;} move(x);')
        self.assertEqual(actions,[('move',[4])])

    def test_invalid_bytecode(self):
        base=compile_body('move(1);')['bytecode']
        variants=[]
        def change(field,value):
            p=copy.deepcopy(base); p[field]=value; variants.append(p)
        change('version',2); change('register_types',['nonsense']); change('instructions',[])
        change('instructions',[{'opcode':999,'args':[]}]); change('instructions',[{'opcode':True,'args':[]}])
        for row in [ {'opcode':OPCODES['JMP'],'args':[999]}, {'opcode':OPCODES['JZ'],'args':[['c','int',1],0]},
                     {'opcode':OPCODES['COPY'],'args':[9,['c','int',2]]},
                     {'opcode':OPCODES['CMD:move'],'args':[['c','int',True]]},
                     {'opcode':OPCODES['CMD:scan'],'args':[1]},
                     {'opcode':OPCODES['COPY'],'args':[0,['r',-1]]},
                     {'opcode':OPCODES['CMD:move'],'args':[['c','float',float('inf')]]}]:
            p=copy.deepcopy(base); p['instructions']=[row]; variants.append(p)
        for data in variants:
            with self.subTest(data=data):
                with self.assertRaises(BytecodeError): validate(data)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.json'; path.write_text('{invalid')
            with self.assertRaises(BytecodeError): load(path)

    def test_vm_isolation_budget_resume(self):
        r=compile_body('int i=0; while (true) {i+=1; move(i);} ',False)
        a,b=VM(r['bytecode']),VM(r['bytecode'])
        for _ in range(20): a.tick(SENSORS,1)
        self.assertNotEqual(a.memory,b.memory); self.assertGreater(a.pc,0); self.assertEqual(b.pc,0)
        loop=VM(compile_body('while (true) {}')['bytecode'])
        loop.tick(SENSORS,7); self.assertEqual(loop.executed,7); self.assertEqual(loop.state,'pausada')

    def test_one_command_per_tick_halt(self):
        vm=VM(compile_body('scan(); fire(1);')['bytecode'])
        self.assertEqual(vm.tick(SENSORS),('scan',[])); self.assertEqual(vm.tick(SENSORS),('fire',[1]))
        vm.tick(SENSORS); self.assertEqual(vm.state,'finalizada'); self.assertIsNone(vm.tick(SENSORS))

    def test_standalone_vm_no_compiler(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=compile_body('move(4);'); export_report(r,tmp)
            script='import sys; from compiler_arena.bytecode import load; from compiler_arena.vm import VM; v=VM(load(sys.argv[1])); print(v.tick({})); assert "compiler_arena.parser" not in sys.modules'
            result=subprocess.run([sys.executable,'-c',script,str(Path(tmp)/'robot.rbc.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr); self.assertIn('move',result.stdout)

    def test_invalid_export_clears_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_report(compile_body('scan();'),tmp); self.assertTrue((Path(tmp)/'robot.rbc.json').exists())
            export_report(compile_body('int x=true;'),tmp); self.assertFalse((Path(tmp)/'robot.rbc.json').exists())


class ArenaTests(unittest.TestCase):
    def arena(self,a,b=None,**kw):
        return Arena([compile_body(a)['bytecode'],compile_body(a if b is None else b)['bytecode']],**kw)

    def test_initial_scan_next_tick_and_stale(self):
        arena=self.arena('scan(); bool v=enemy.visible; move(enemy.distance/10);')
        self.assertFalse(arena.robots[0].scan['enemy.visible'])
        arena.step(); r=arena.robots[0]
        self.assertTrue(r.scan['enemy.visible']); self.assertEqual(r.scan['enemy.distance'],400.0)
        self.assertEqual(r.vm.pc,1)
        arena.step(); self.assertEqual(r.scan['enemy.distance'],400.0); self.assertAlmostEqual(r.x,560.0)

    def test_simultaneous_death(self):
        arena=self.arena('fire(3);'); arena.robots[0].hp=30; arena.robots[1].hp=30
        arena.step(); self.assertEqual(len(arena.projectiles),2); self.assertIsNone(arena.result)
        arena.run(); self.assertEqual([r.state for r in arena.robots],['eliminado','eliminado']); self.assertIsNone(arena.result['winner'])
        self.assertEqual(arena.tick_count,13)  # 388 unidades até o disco a 30 por tick

    def test_projectile_travel_and_dodge(self):
        arena=self.arena('fire(1);','while (true) {}')
        arena.step(); shot=arena.projectiles[0]; self.assertAlmostEqual(shot.x,570.0)
        self.assertTrue(any(e['type']=='fire' for e in arena.effects))
        for _ in range(12): arena.step()
        hit=[e for e in arena.effects if e['type']=='hit']
        self.assertEqual(hit[0]['target'],1); self.assertAlmostEqual(hit[0]['x'],212.0)
        self.assertEqual(arena.robots[1].hp,90); self.assertTrue(arena.robots[1].hit); self.assertEqual(arena.projectiles,[])
        # Quem sai da linha de tiro antes da chegada não é atingido.
        arena=self.arena('fire(3);','rotate(90); move(100); while (true) {}')
        expired=False
        for _ in range(25): arena.step(); expired|=any(e['type']=='expire' for e in arena.effects)
        self.assertEqual(arena.robots[1].hp,100); self.assertTrue(expired); self.assertEqual(arena.projectiles,[])

    def test_energy_regenerates_and_does_not_kill(self):
        arena=self.arena('while (true) {fire(3);}','while (true) {}')
        arena.robots[0].energy=6; arena.step()
        self.assertEqual(arena.robots[0].energy,1); self.assertEqual(arena.robots[0].state,'ativo')
        for _ in range(5): arena.step()
        self.assertEqual(arena.robots[0].energy,6); self.assertEqual(arena.robots[0].state,'ativo')
        arena=self.arena('while (true) {scan();}','while (true) {}',max_ticks=300); arena.run()
        self.assertEqual(arena.robots[0].energy,100); self.assertEqual(arena.robots[0].state,'ativo')

    def test_new_sensors(self):
        arena=self.arena('if (heading == -180.0 && hp == 100 && !hit) { move(hp/10); }','while (true) {}')
        arena.step(); self.assertAlmostEqual(arena.robots[0].x,590.0)

    def test_halted_still_target(self):
        arena=self.arena('', 'while (true) {fire(3);}')
        arena.run(); self.assertEqual(arena.robots[0].vm.state,'finalizada'); self.assertEqual(arena.robots[0].state,'eliminado'); self.assertEqual(arena.result['winner'],1)

    def test_runtime_disqualification(self):
        arena=self.arena('int z=0; int p=1%z; fire(p);','')
        arena.step(); self.assertEqual(arena.robots[0].state,'desclassificado'); self.assertEqual(arena.result['winner'],1)

    def test_limit_tie_and_energy(self):
        arena=self.arena('while (true) {}',max_ticks=3); arena.run()
        self.assertEqual(arena.tick_count,3); self.assertIsNone(arena.result['winner'])
        arena=self.arena('scan();','',max_ticks=1); arena.run(); self.assertIsNone(arena.result['winner'])
        arena=self.arena('while (true) {}',max_ticks=3); arena.robots[0].hp=50; arena.run()
        self.assertEqual(arena.result['winner'],1); self.assertIn('maior vida',arena.result['reason'])

    def test_early_end_when_all_finished(self):
        arena=self.arena('scan();',''); arena.run()
        self.assertEqual(arena.tick_count,2); self.assertIn('programas finalizados',arena.result['reason'])
        arena=self.arena('fire(1);',''); arena.run()
        self.assertGreater(arena.tick_count,1); self.assertEqual(arena.robots[1].hp,90)

    def test_collision_and_wall(self):
        arena=self.arena('move(100);'); arena.robots[0].x=430; arena.robots[1].x=370
        arena.step(); self.assertEqual(arena.robots[0].x,430); self.assertEqual(arena.robots[1].x,370)
        arena=self.arena('move(100);'); arena.robots[0].x=750; arena.robots[0].angle=0
        arena.step(); self.assertEqual(arena.robots[0].x,788)
        arena=self.arena('move(100);'); arena.robots[0].x=788; arena.robots[0].y=500; arena.robots[0].angle=45
        arena.step(); self.assertEqual(arena.robots[0].x,788); self.assertEqual(arena.robots[0].y,500)

    def test_order_independent_and_scan_tie(self):
        programs=[compile_body('scan(); fire(1);')['bytecode'] for _ in range(3)]
        a=Arena(programs,max_ticks=10); b=Arena(programs,max_ticks=10)
        b.robots.reverse(); a.run(); b.run()
        da={r.id:(r.x,r.y,r.hp,r.energy,r.scan) for r in a.robots}; db={r.id:(r.x,r.y,r.hp,r.energy,r.scan) for r in b.robots}
        self.assertEqual(da,db)
        c=Arena(programs); c.robots[0].x=400; c.robots[0].y=300
        c.robots[1].x=450; c.robots[1].y=300; c.robots[2].x=350; c.robots[2].y=300
        c.step(); self.assertEqual(c.robots[0].scan['enemy.direction'],-180.0)

    def test_invalid_entry_and_insufficient_energy(self):
        with self.assertRaises((ValueError,TypeError)): Arena([None,None])
        arena=self.arena('fire(3);',''); arena.robots[0].energy=5; arena.step()
        self.assertEqual(arena.robots[0].energy,6); self.assertEqual(arena.projectiles,[])
        self.assertFalse(arena.logs[0]['executed'])

    def test_planet_examples_compile_and_finish(self):
        programs={n:compile_source(Path(f'exemplos/{n}.robo').read_text())['bytecode'] for n in ('marte','saturno','netuno')}
        self.assertTrue(all(programs.values()))
        for a,b in (('marte','saturno'),('saturno','netuno'),('netuno','marte')):
            arena=Arena([programs[a],programs[b]]); arena.run()
            self.assertIsNotNone(arena.result['winner']); self.assertLess(arena.tick_count,1000)

    def test_cli_integration(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd=[sys.executable,'main.py','compile','exemplos/alpha.robo','--out',tmp]
            p=subprocess.run(cmd,capture_output=True,text=True); self.assertEqual(p.returncode,0,p.stderr)
            bc=str(Path(tmp)/'robot.rbc.json')
            p=subprocess.run([sys.executable,'main.py','battle',bc,bc,'--ticks','10','--out',str(Path(tmp)/'battle.json')],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr); self.assertTrue((Path(tmp)/'battle.json').exists())


if __name__=='__main__': unittest.main()
