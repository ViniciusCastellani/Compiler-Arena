"""Servidor local da interface HTML. Toda simulação permanece em Python."""
import argparse
import json
import math
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .arena import Arena
from .bytecode import validate, MAX_FILE
from .compiler import compile_source

STATIC = Path(__file__).with_name('web')


def wire_encode(value):
    # JSON.parse arredonda inteiros maiores que 53 bits: preserve-os no transporte.
    if type(value) is int and abs(value)>9007199254740991: return {'$integer':str(value)}
    if type(value) is float: return {'$float':repr(value)}
    if isinstance(value,dict): return {k:wire_encode(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [wire_encode(v) for v in value]
    return value


def wire_decode(value):
    if isinstance(value,dict):
        if set(value)=={'$float'}:
            raw=value['$float']
            if not isinstance(raw,str) or len(raw)>100: raise ValueError('Float de transporte inválido.')
            number=float(raw)
            if not math.isfinite(number): raise ValueError('Float não finito.')
            return number
        if set(value)=={'$integer'}:
            digits=value['$integer']
            if not isinstance(digits,str) or len(digits)>1235 or not digits.lstrip('-').isascii() or not digits.lstrip('-').isdigit():
                raise ValueError('Inteiro de transporte inválido.')
            return int(digits)
        return {k:wire_decode(v) for k,v in value.items()}
    if isinstance(value,list): return [wire_decode(v) for v in value]
    return value


class ArenaServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        super().__init__(address, Handler)
        self.sessions = {}
        self.guard = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def reply(self, status, payload, mime='application/json; charset=utf-8'):
        data = json.dumps(wire_encode(payload), ensure_ascii=False, allow_nan=False).encode() if isinstance(payload, (dict,list)) else payload
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError): pass

    def local_request(self):
        port = self.server.server_port
        allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
        host = self.headers.get('Host','')
        origin = self.headers.get('Origin')
        if host not in allowed or (origin and origin != 'http://'+host):
            self.reply(403, {'error':'Origem local inválida.'}); return False
        return True

    def do_GET(self):
        if not self.local_request(): return
        path = urlsplit(self.path).path
        if path == '/api/examples':
            examples = STATIC.parent.parent/'exemplos'
            return self.reply(200, [{'name':p.name,'source':p.read_text(encoding='utf-8')} for p in sorted(examples.glob('*.robo'))])
        files = {'/':'index.html','/index.html':'index.html','/app.js':'app.js','/arena_renderer.js':'arena_renderer.js','/style.css':'style.css'}
        if path not in files: return self.reply(404, {'error':'Recurso inexistente.'})
        name = files[path]
        mime = {'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[name.rsplit('.',1)[1]]
        self.reply(200,(STATIC/name).read_bytes(),mime)

    def do_POST(self):
        if not self.local_request(): return
        try:
            size = int(self.headers.get('Content-Length','0'))
            if not 0 < size <= 16*MAX_FILE: raise ValueError('Tamanho de requisição inválido.')
            if self.headers.get_content_type() != 'application/json': raise ValueError('Envie dados JSON.')
            data = wire_decode(json.loads(self.rfile.read(size)))
            if not isinstance(data,dict): raise ValueError('Objeto JSON obrigatório.')
            path = urlsplit(self.path).path
            if path == '/api/compile':
                source = data.get('source'); opt = data.get('optimization',True)
                if not isinstance(source,str) or type(opt) is not bool: raise ValueError('Fonte ou opção de otimização inválida.')
                return self.reply(200,compile_source(source,opt))
            if path == '/api/validate':
                if 'text' in data:
                    raw=data['text']
                    if not isinstance(raw,str) or len(raw.encode('utf-8'))>MAX_FILE: raise ValueError('Bytecode excede 8 MB.')
                    program=json.loads(raw)
                else: program=data.get('bytecode')
                return self.reply(200,{'bytecode':validate(program)})
            session = self.headers.get('X-Arena-Session','')
            if not 16 <= len(session) <= 128 or not all(c.isalnum() or c=='-' for c in session): raise ValueError('Sessão inválida.')
            with self.server.guard:
                if path == '/api/battle/create':
                    programs = data.get('programs')
                    if not isinstance(programs,list) or not 2<=len(programs)<=16: raise ValueError('Selecione de 2 a 16 robôs.')
                    if session not in self.server.sessions and len(self.server.sessions)>=32: raise ValueError('Limite de sessões atingido. Reinicie o servidor.')
                    arena = Arena(programs,data.get('max_ticks',1000),data.get('budget',100),data.get('seed',0))
                    self.server.sessions[session] = arena
                elif path == '/api/battle/close':
                    self.server.sessions.pop(session,None); return self.reply(200,{'closed':True})
                elif path in ('/api/battle/step','/api/battle/reset','/api/battle/state','/api/battle/export'):
                    arena = self.server.sessions.get(session)
                    if arena is None: raise ValueError('Crie uma batalha primeiro.')
                    if path.endswith('/reset'):
                        arena = Arena([r.vm.program for r in arena.robots],arena.max_ticks,arena.budget,arena.seed)
                        self.server.sessions[session] = arena
                    elif path.endswith('/step'): arena.step()
                else: return self.reply(404,{'error':'Operação inexistente.'})
                payload = {'snapshot':arena.snapshot()}
                if path.endswith('/export'): payload.update(logs=arena.logs,seed=arena.seed,budget=arena.budget)
                self.reply(200,payload)
        except (ValueError,TypeError,KeyError,RecursionError,UnicodeError) as error:
            self.reply(400,{'error':str(error) or 'Dados inválidos.'})


def launch(port=8000, open_browser=True):
    with ArenaServer(('127.0.0.1',port)) as server:
        url=f'http://127.0.0.1:{server.server_port}'
        print(f'Compiler Arena: {url}\nEncerre o servidor com Ctrl+C.',flush=True)
        if open_browser: webbrowser.open(url)
        try: server.serve_forever()
        except KeyboardInterrupt: print('\nServidor encerrado.')
