"""Integração HTTP da interface com o compilador e a arena reais."""
import json
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from compiler_arena.web_server import ArenaServer, wire_encode, wire_decode
from compiler_arena.compiler import compile_source


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ArenaServer(('127.0.0.1',0))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def call(self,path,data,session='web-test-session-1234',origin=None):
        headers={'Content-Type':'application/json','X-Arena-Session':session}
        if origin: headers['Origin']=origin
        req=Request(self.url+'/api/'+path,json.dumps(wire_encode(data)).encode(),headers=headers)
        with urlopen(req,timeout=10) as res: return wire_decode(json.load(res))

    def test_page_and_examples(self):
        with urlopen(self.url) as res:
            html=res.read().decode();self.assertIn('canvas',html);self.assertIn('app.js',html);self.assertIn('arena_renderer.js',html)
        with urlopen(self.url+'/api/examples') as res: self.assertTrue(any(e['name']=='alpha.robo' for e in json.load(res)))
        with self.assertRaises(HTTPError): urlopen(self.url+'/../main.py')

    def test_compilation_and_invalid_block(self):
        result=self.call('compile',{'source':'robot A {move(1);}','optimization':False})
        self.assertTrue(result['bytecode']);self.assertEqual(result['stages']['otimização'],'desativada')
        result=self.call('compile',{'source':'robot A {fire(true);}'})
        self.assertIsNone(result['bytecode']);self.assertTrue(result['diagnostics'])
        with self.assertRaises(HTTPError): self.call('battle/create',{'programs':[None,None]})

    def test_ticks_reset_and_export(self):
        p=compile_source('robot A {scan(); while (true) {}}')['bytecode']
        s=self.call('battle/create',{'programs':[p,p],'max_ticks':2})['snapshot'];self.assertEqual(s['tick'],0)
        s=self.call('battle/step',{})['snapshot'];self.assertEqual(s['tick'],1);self.assertTrue(s['robots'][0]['scan']['enemy.visible'])
        s=self.call('battle/step',{})['snapshot'];self.assertIsNotNone(s['result'])
        self.assertTrue(self.call('battle/export',{})['logs'])
        self.assertEqual(self.call('battle/reset',{})['snapshot']['tick'],0)
        self.call('battle/close',{})
        with self.assertRaises(HTTPError): self.call('battle/state',{})

    def test_session_isolation_and_origin(self):
        p=compile_source('robot A {}')['bytecode']
        self.call('battle/create',{'programs':[p,p]},'session-aaaaaaaaaaaa')
        with self.assertRaises(HTTPError): self.call('battle/state',{},'session-bbbbbbbbbbbb')
        with self.assertRaises(HTTPError) as error: self.call('compile',{'source':'robot A {}'},origin='https://example.com')
        self.assertEqual(error.exception.code,403)

    def test_animation_events_from_real_actions(self):
        fire=compile_source('robot Shooter {fire(3);}')['bytecode']
        idle=compile_source('robot Idle {}')['bytecode']
        self.call('battle/create',{'programs':[fire,idle]},'animation-event-session')
        snapshot=self.call('battle/step',{},'animation-event-session')['snapshot']
        shot=next(e for e in snapshot['effects'] if e['type']=='fire')
        self.assertEqual(shot['power'],3);self.assertEqual(len(snapshot['projectiles']),1)
        self.assertAlmostEqual(snapshot['projectiles'][0]['x'],570.0)
        while not any(e['type']=='hit' for e in snapshot['effects']):
            snapshot=self.call('battle/step',{},'animation-event-session')['snapshot']
        hit=next(e for e in snapshot['effects'] if e['type']=='hit')
        self.assertEqual(hit['target'],1);self.assertEqual(hit['damage'],30);self.assertAlmostEqual(hit['x'],212.0)
        self.assertEqual(snapshot['robots'][1]['hp'],70);self.assertTrue(snapshot['robots'][1]['hit'])
        self.assertEqual(self.call('battle/reset',{},'animation-event-session')['snapshot']['effects'],[])
        rotating=compile_source('robot Rotation {rotate(360);}')['bytecode']
        self.call('battle/create',{'programs':[rotating,idle]},'animation-rotation-session')
        effects=self.call('battle/step',{},'animation-rotation-session')['snapshot']['effects']
        self.assertTrue(any(e['type']=='rotate' and e['degrees']==360 for e in effects))

    def test_integer_roundtrip_and_uploaded_json(self):
        number=9007199254740993
        result=self.call('compile',{'source':f'robot Big {{int n={number};}}'})
        literals=[arg for row in result['bytecode']['instructions'] for arg in row['args'] if isinstance(arg,list) and arg[0]=='c']
        self.assertTrue(any(arg[2]==number for arg in literals))
        program=self.call('validate',{'text':json.dumps(result['bytecode'])})['bytecode']
        self.assertEqual(program,result['bytecode'])
        fractional=self.call('compile',{'source':'robot Float {float n=450.0; move(1.0);}'})
        result=self.call('validate',{'bytecode':fractional['bytecode']})
        self.assertTrue(result['bytecode'])
        self.call('battle/create',{'programs':[program,program]},'session-large-integer')
        with self.assertRaises(HTTPError): self.call('validate',{'text':'{"version":999}'})


if __name__=='__main__': unittest.main()
