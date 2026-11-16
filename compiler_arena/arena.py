"""Núcleo determinístico, sem qualquer import de GUI ou compilador."""
import math
from dataclasses import dataclass, field
from .vm import VM

EMPTY_SCAN = {'enemy.visible':False,'enemy.distance':-1.0,'enemy.direction':0.0}


def normalize(degrees): return (degrees+180)%360-180


@dataclass
class Robot:
    id: int
    name: str
    vm: VM
    x: float
    y: float
    angle: float
    hp: int = 100
    energy: int = 100
    state: str = 'ativo'
    hit: bool = False
    scan: dict = field(default_factory=lambda: dict(EMPTY_SCAN))


@dataclass
class Projectile:
    id: int
    owner: int
    x: float
    y: float
    dx: float
    dy: float
    power: int
    travelled: float = 0.0


def closest_distance(a,b,c,d):
    """Mínima distância entre dois pontos em movimento durante o mesmo tick."""
    rx,ry=a[0]-b[0],a[1]-b[1]
    vx,vy=(c[0]-a[0])-(d[0]-b[0]),(c[1]-a[1])-(d[1]-b[1])
    den=vx*vx+vy*vy
    t=max(0,min(1,-(rx*vx+ry*vy)/den)) if den else 0
    return math.hypot(rx+t*vx,ry+t*vy)


def contact_time(p0,p1,a0,a1,radius):
    """Primeiro instante t∈[0,1] em que o ponto p0→p1 entra no disco a0→a1."""
    rx,ry=p0[0]-a0[0],p0[1]-a0[1]
    vx,vy=(p1[0]-p0[0])-(a1[0]-a0[0]),(p1[1]-p0[1])-(a1[1]-a0[1])
    c=rx*rx+ry*ry-radius*radius
    if c<=0: return 0.0
    a=vx*vx+vy*vy; b=2*(rx*vx+ry*vy)
    disc=b*b-4*a*c
    if not a or disc<0: return None
    t=(-b-math.sqrt(disc))/(2*a)
    return t if 0<=t<=1 else None


class Arena:
    width=800; height=600; radius=12; scan_range=1000; shot_range=1000
    projectile_speed=30; regen=1; max_energy=100

    def __init__(self, programs, max_ticks=1000, budget=100, seed=0):
        if not 2<=len(programs)<=16: raise ValueError('A arena exige de 2 a 16 robôs válidos')
        if type(max_ticks) is not int or not 1<=max_ticks<=100000: raise ValueError('limite de ticks entre 1 e 100000')
        if type(budget) is not int or not 1<=budget<=100000: raise ValueError('orçamento entre 1 e 100000')
        self.max_ticks=max_ticks; self.budget=budget; self.seed=seed
        self.tick_count=0; self.result=None; self.logs=[]; self.robots=[]; self.effects=[]
        self.projectiles=[]; self.next_projectile=0
        for i, p in enumerate(programs):
            theta=2*math.pi*i/len(programs)
            self.robots.append(Robot(i,p['robot'],VM(p),400+200*math.cos(theta),300+200*math.sin(theta),normalize(math.degrees(theta)+180)))

    def snapshot(self):
        return {'tick':self.tick_count,'max_ticks':self.max_ticks,'result':self.result,
                'robots':[{'id':r.id,'name':r.name,'x':r.x,'y':r.y,'angle':r.angle,'hp':r.hp,'energy':r.energy,'hit':r.hit,'state':r.state,'vm':r.vm.state,'pc':r.vm.pc,'error':r.vm.error, 'scan':dict(r.scan)} for r in self.robots],
                'projectiles':[{'id':p.id,'owner':p.owner,'x':p.x,'y':p.y,'power':p.power} for p in self.projectiles],
                'recent':self.logs[-12:], 'effects':self.effects}

    def wall_limit(self, x, y, dx, dy):
        """Maior fração do deslocamento (dx,dy) que mantém o disco dentro da arena."""
        t=1.0
        for pos,delta,high in ((x,dx,self.width),(y,dy,self.height)):
            if delta>0: t=min(t,(high-self.radius-pos)/delta)
            elif delta<0: t=min(t,(self.radius-pos)/delta)
        return max(0.0,t)

    def step(self):
        if self.result: return self.snapshot()
        self.effects=[]
        active=[r for r in self.robots if r.state=='ativo']
        snap={r.id:(r.x,r.y,r.angle,r.energy) for r in active}
        commands={}; disqualified=set()
        for r in active:
            sensors={'energy':r.energy,'hp':r.hp,'heading':float(r.angle),'hit':r.hit,
                     'position.x':float(r.x),'position.y':float(r.y),**r.scan}
            cmd=r.vm.tick(sensors,self.budget)
            if r.vm.state=='erro':
                disqualified.add(r.id)
                self.logs.append({'tick':self.tick_count+1,'robot':r.id,'error':r.vm.error})
            elif cmd: commands[r.id]=cmd
        costs={r.id:0 for r in active}; damage={r.id:0 for r in active}
        plans={r.id:(r.x,r.y) for r in active}; angles={r.id:r.angle for r in active}; scans={}
        fired=[]
        for r in active:
            if r.id not in commands: continue
            name,args=commands[r.id]; val=args[0] if args else 0
            cost=2*val if name=='fire' else 1
            enough=r.energy>=cost
            entry={'tick':self.tick_count+1,'robot':r.id,'command':name,'args':args,'executed':enough}
            if r.vm.clamped_from is not None: entry['clamped_from']=r.vm.clamped_from
            self.logs.append(entry)
            if not enough: continue
            costs[r.id]=cost
            if name in ('move','back'):
                amount=val if name=='move' else -val
                rad=math.radians(r.angle); dx,dy=amount*math.cos(rad),amount*math.sin(rad)
                t=self.wall_limit(r.x,r.y,dx,dy)
                plans[r.id]=(r.x+t*dx,r.y+t*dy)
            elif name=='rotate':
                angles[r.id]=normalize(r.angle+val)
                self.effects.append({'type':'rotate','robot':r.id,'degrees':val})
            elif name=='scan':
                self.effects.append({'type':'scan','robot':r.id,'x':r.x,'y':r.y,'range':self.scan_range})
                candidates=[(math.hypot(s.x-r.x,s.y-r.y),s.id,s) for s in active if s.id!=r.id and s.id not in disqualified]
                candidates=[c for c in candidates if c[0]<=self.scan_range]
                scans[r.id]=dict(EMPTY_SCAN)
                if candidates:
                    distance,_,enemy=min(candidates,key=lambda c:(c[0],c[1]))
                    direction=normalize(math.degrees(math.atan2(enemy.y-r.y,enemy.x-r.x))-r.angle)
                    scans[r.id]={'enemy.visible':True,'enemy.distance':float(distance),'enemy.direction':float(direction)}
            elif name=='fire':
                # O projétil parte do snapshot inicial; a rotação do mesmo tick não o desvia.
                rad=math.radians(r.angle)
                p=Projectile(self.next_projectile,r.id,r.x,r.y,math.cos(rad),math.sin(rad),val)
                self.next_projectile+=1; fired.append(p)
                self.effects.append({'type':'fire','robot':r.id,'projectile':p.id,'power':val,'x':r.x,'y':r.y,'angle':r.angle})
        # Cancelamento simultâneo, repetido porque uma parada pode bloquear outro caminho.
        changed=True
        while changed:
            changed=False; blocked=set()
            for i,r in enumerate(active):
                for s in active[i+1:]:
                    if closest_distance(snap[r.id][:2],snap[s.id][:2],plans[r.id],plans[s.id])<2*self.radius:
                        blocked.update((r.id,s.id))
            for ident in blocked:
                start=snap[ident][:2]
                if plans[ident]!=start: plans[ident]=start; changed=True
        # Projéteis avançam junto com os robôs; cada um atinge o primeiro disco tocado.
        targets=[r for r in active if r.id not in disqualified]
        flying=[]; hit_now=set()
        for p in self.projectiles+fired:
            start=(p.x,p.y); end=(p.x+p.dx*self.projectile_speed,p.y+p.dy*self.projectile_speed)
            contacts=[]
            for s in targets:
                if s.id==p.owner: continue
                t=contact_time(start,end,snap[s.id][:2],plans[s.id],self.radius)
                if t is not None: contacts.append((t,s.id))
            if contacts:
                t,target=min(contacts)
                x,y=start[0]+t*(end[0]-start[0]),start[1]+t*(end[1]-start[1])
                damage[target]+=10*p.power; hit_now.add(target)
                self.effects.append({'type':'hit','robot':p.owner,'projectile':p.id,'target':target,'damage':10*p.power,'x':x,'y':y,'time':t})
                self.logs.append({'tick':self.tick_count+1,'robot':p.owner,'hit':target,'damage':10*p.power})
                continue
            p.x,p.y=end; p.travelled+=self.projectile_speed
            if 0<=p.x<=self.width and 0<=p.y<=self.height and p.travelled<self.shot_range: flying.append(p)
            else: self.effects.append({'type':'expire','robot':p.owner,'projectile':p.id,'x':p.x,'y':p.y})
        self.projectiles=flying
        for r in active:
            r.x,r.y=plans[r.id]; r.angle=angles[r.id]
            r.energy=min(self.max_energy,r.energy-costs[r.id]+self.regen)
            r.hp=max(0,r.hp-damage[r.id]); r.hit=r.id in hit_now
            if r.id in scans: r.scan=scans[r.id]
            if r.id in disqualified: r.state='desclassificado'
            elif r.hp<=0:
                r.state='eliminado'
                self.effects.append({'type':'elimination','robot':r.id,'x':r.x,'y':r.y})
        self.tick_count+=1
        eligible=[r for r in self.robots if r.state=='ativo']
        idle=all(r.vm.state=='finalizada' for r in eligible) and not self.projectiles
        if len(eligible)<=1:
            self.result={'winner':eligible[0].id if eligible else None,'reason':'único elegível' if eligible else 'eliminação simultânea / nenhum elegível'}
        elif self.tick_count>=self.max_ticks or idle:
            cause='programas finalizados' if idle else 'limite de ticks'
            best=max(r.hp for r in eligible); winners=[r for r in eligible if r.hp==best]
            self.result={'winner':winners[0].id if len(winners)==1 else None,'reason':f'{cause}; maior vida' if len(winners)==1 else f'{cause}; empate em vida'}
        return self.snapshot()

    def run(self):
        while not self.result: self.step()
        return self.snapshot()
