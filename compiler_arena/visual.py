"""Pygame em processo próprio. A única Arena vive neste processo."""
import math
import time

COLORS=[(72,207,173),(86,156,240),(245,184,74),(238,112,132)]


def draw(pygame, screen, arena):
    screen.fill((15,23,38)); font=pygame.font.SysFont('DejaVu Sans',17)
    def text(msg,x,y,color=(225,233,245)):
        screen.blit(font.render(msg,True,color),(x,y))
    for x in range(0,801,50): pygame.draw.line(screen,(31,44,63),(x,50),(x,650))
    for y in range(50,651,50): pygame.draw.line(screen,(31,44,63),(0,y),(800,y))
    pygame.draw.rect(screen,(101,120,147),(0,50,800,600),2)
    text(f'COMPILER ARENA    Tick {arena.tick_count}/{arena.max_ticks}',16,14)
    for r in arena.robots:
        color=COLORS[r.id%len(COLORS)] if r.state=='ativo' else (95,99,109)
        pos=(round(r.x),round(650-r.y)); rad=math.radians(r.angle)
        pygame.draw.circle(screen,color,pos,12)
        pygame.draw.line(screen,(255,255,255),pos,(pos[0]+23*math.cos(rad),pos[1]-23*math.sin(rad)),3)
        text(f'{r.id} {r.name}',pos[0]-25,pos[1]-37,color)
    for p in arena.projectiles:
        pygame.draw.circle(screen,(255,248,207),(round(p.x),round(650-p.y)),2+p.power)
    def fit(msg,width=535):
        while msg and font.size(msg)[0]>width: msg=msg[:-2]+'…'
        return msg
    for i,r in enumerate(arena.robots):
        text(fit(f'{r.id} {r.name} | vida {r.hp} | energia {r.energy} | {r.state} | VM {r.vm.state}'),820,55+i*25,COLORS[i%4])
    log_y=max(270,90+len(arena.robots)*25)
    for i,event in enumerate(arena.logs[-6:]):
        r=next(r for r in arena.robots if r.id==event['robot'])
        if 'error' in event: message=f'Tick {event["tick"]} | {r.name}: {event["error"]}'
        elif 'hit' in event:
            target=next(t.name for t in arena.robots if t.id==event['hit'])
            message=f'Tick {event["tick"]} | {r.name} acertou {target}: -{event["damage"]} vida'
        else:
            args=', '.join(str(v) for v in event['args'])
            outcome='executado' if event['executed'] else 'energia insuficiente'
            message=f'Tick {event["tick"]} | {r.name}: {event["command"]}({args}) - {outcome}'
        text(fit(message),820,log_y+i*25)
    if arena.result:
        ident=arena.result['winner']
        name=next(r.name for r in arena.robots if r.id==ident) if ident is not None else 'empate'
        text(f'Resultado: {name} | {arena.result["reason"]}',16,672)
    else: text('Espaço: pausar/continuar | N: um tick | R: reiniciar | Esc: sair',16,672)


def run_visual(arena, connection=None, screenshot=None, frame_limit=None):
    import pygame
    from .arena import Arena
    pygame.init(); screen=pygame.display.set_mode((1380,720),pygame.RESIZABLE); canvas=pygame.Surface((1380,720)); pygame.display.set_caption('Compiler Arena — batalha real')
    clock=pygame.time.Clock(); running=True; paused=bool(connection); speed=10; last=time.monotonic(); frames=0
    programs=[r.vm.program for r in arena.robots]
    sent_logs=0
    def publish(reset=False):
        nonlocal sent_logs
        if reset: sent_logs=0
        if connection:
            connection.send({'snapshot':arena.snapshot(),'logs':arena.logs[sent_logs:],'reset':reset})
            sent_logs=len(arena.logs)
    publish()
    try:
        while running:
            requests=[]
            for event in pygame.event.get():
                if event.type==pygame.QUIT: running=False
                elif event.type==pygame.KEYDOWN:
                    key={pygame.K_SPACE:'toggle',pygame.K_n:'step',pygame.K_r:'restart',pygame.K_ESCAPE:'close'}.get(event.key)
                    if key: requests.append({'action':key})
            if connection:
                while connection.poll():
                    try: requests.append(connection.recv())
                    except EOFError: running=False; break
            for req in requests:
                action=req['action']
                if action=='close': running=False
                elif action=='toggle': paused=not paused
                elif action=='pause': paused=True
                elif action=='start': paused=False
                elif action=='speed': speed=max(1,min(60,int(req['value'])))
                elif action=='step': paused=True; arena.step(); publish()
                elif action=='restart':
                    arena=Arena(programs,arena.max_ticks,arena.budget,arena.seed); paused=True; publish(reset=True)
            now=time.monotonic()
            if not paused and now-last>=1/speed and not arena.result:
                arena.step(); last=now; publish()
            draw(pygame,canvas,arena)
            width,height=screen.get_size(); ratio=min(width/1380,height/720)
            size=(max(1,round(1380*ratio)),max(1,round(720*ratio)))
            screen.fill((15,23,38))
            screen.blit(pygame.transform.smoothscale(canvas,size),((width-size[0])//2,(height-size[1])//2))
            pygame.display.flip(); frames+=1
            if screenshot and frames==2: pygame.image.save(screen,screenshot)
            if frame_limit and frames>=frame_limit: running=False
            clock.tick(60)
    except (BrokenPipeError,EOFError): pass
    finally:
        if connection: connection.close()
        pygame.quit()
    return arena


def worker(programs, max_ticks, budget, connection):
    try:
        from .arena import Arena
        run_visual(Arena(programs,max_ticks,budget),connection)
    except Exception as e:
        try: connection.send({'error':str(e)})
        except (BrokenPipeError,EOFError): pass
        connection.close()
