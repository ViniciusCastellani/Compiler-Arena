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
    energy: int = 100
    state: str = 'ativo'
    scan: dict = field(default_factory=lambda: dict(EMPTY_SCAN))


def closest_distance(a,b,c,d):
    """Mínima distância entre dois pontos em movimento durante o mesmo tick."""
    rx,ry=a[0]-b[0],a[1]-b[1]
    vx,vy=(c[0]-a[0])-(d[0]-b[0]),(c[1]-a[1])-(d[1]-b[1])
    den=vx*vx+vy*vy
    t=max(0,min(1,-(rx*vx+ry*vy)/den)) if den else 0
    return math.hypot(rx+t*vx,ry+t*vy)


class Arena:
    width=800; height=600; radius=12; scan_range=500; shot_range=500

    def __init__(self, programs, max_ticks=1000, budget=100, seed=0):
        if not 2<=len(programs)<=16: raise ValueError('A arena exige de 2 a 16 robôs válidos')
        if type(max_ticks) is not int or not 1<=max_ticks<=100000: raise ValueError('limite de ticks entre 1 e 100000')
        if type(budget) is not int or not 1<=budget<=100000: raise ValueError('orçamento entre 1 e 100000')
        self.max_ticks=max_ticks; self.budget=budget; self.seed=seed
        self.tick_count=0; self.result=None; self.logs=[]; self.robots=[]; self.effects=[]
        for i, p in enumerate(programs):
            theta=2*math.pi*i/len(programs)
            self.robots.append(Robot(i,p['robot'],VM(p),400+200*math.cos(theta),300+200*math.sin(theta),normalize(math.degrees(theta)+180)))

    def snapshot(self):
        return {'tick':self.tick_count,'max_ticks':self.max_ticks,'result':self.result,
                'robots':[{'id':r.id,'name':r.name,'x':r.x,'y':r.y,'angle':r.angle,'energy':r.energy,'state':r.state,'vm':r.vm.state,'pc':r.vm.pc,'error':r.vm.error, 'scan':dict(r.scan)} for r in self.robots],
                'recent':self.logs[-12:], 'effects':self.effects}

    def step(self):
        if self.result: return self.snapshot()
        self.effects=[]
        active=[r for r in self.robots if r.state=='ativo']
        snap={r.id:(r.x,r.y,r.angle,r.energy) for r in active}
        commands={}; disqualified=set()
        for r in active:
            sensors={'energy':r.energy,'position.x':float(r.x),'position.y':float(r.y),**r.scan}
            cmd=r.vm.tick(sensors,self.budget)
            if r.vm.state=='erro':
                disqualified.add(r.id)
                self.logs.append({'tick':self.tick_count+1,'robot':r.id,'error':r.vm.error})
            elif cmd: commands[r.id]=cmd
        costs={r.id:0 for r in active}; damage={r.id:0 for r in active}
        plans={r.id:(r.x,r.y) for r in active}; angles={r.id:r.angle for r in active}; scans={}
        for r in active:
            if r.id not in commands: continue
            name,args=commands[r.id]; val=args[0] if args else 0
            cost=2*val if name=='fire' else 1
            enough=r.energy>=cost
            self.logs.append({'tick':self.tick_count+1,'robot':r.id,'command':name,'args':args,'executed':enough})
            if not enough: continue
            costs[r.id]=cost
            if name in ('move','back'):
                amount=val if name=='move' else -val
                rad=math.radians(r.angle); x=r.x+amount*math.cos(rad); y=r.y+amount*math.sin(rad)
                if self.radius<=x<=self.width-self.radius and self.radius<=y<=self.height-self.radius:
                    plans[r.id]=(x,y)
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
                dx,dy=math.cos(math.radians(r.angle)),math.sin(math.radians(r.angle)); hits=[]
                for s in active:
                    if s.id==r.id or s.id in disqualified: continue
                    vx,vy=s.x-r.x,s.y-r.y; projection=vx*dx+vy*dy
                    perpendicular2=max(0,vx*vx+vy*vy-projection*projection)
                    if projection>0 and perpendicular2<=self.radius**2:
                        entry=projection-math.sqrt(self.radius**2-perpendicular2)
                        if 0<=entry<=self.shot_range: hits.append((entry,s.id))
                distance,target=min(hits) if hits else (self.shot_range,None)
                if target is not None: damage[target]+=10*val
                # Dados visuais da ação real; o navegador não recalcula acertos.
                self.effects.append({'type':'fire','robot':r.id,'power':val,
                    'x':r.x,'y':r.y,'end_x':r.x+distance*dx,'end_y':r.y+distance*dy,
                    'target':target,'damage':10*val if target is not None else 0})
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
        for r in active:
            r.x,r.y=plans[r.id]; r.angle=angles[r.id]
            r.energy=max(0,r.energy-costs[r.id]-damage[r.id])
            if r.id in scans: r.scan=scans[r.id]
            if r.id in disqualified: r.state='desclassificado'
            elif r.energy<=0:
                r.state='eliminado'
                self.effects.append({'type':'elimination','robot':r.id,'x':r.x,'y':r.y})
        self.tick_count+=1
        eligible=[r for r in self.robots if r.state=='ativo']
        if len(eligible)<=1:
            self.result={'winner':eligible[0].id if eligible else None,'reason':'único elegível' if eligible else 'eliminação simultânea / nenhum elegível'}
        elif self.tick_count>=self.max_ticks:
            best=max(r.energy for r in eligible); winners=[r for r in eligible if r.energy==best]
            self.result={'winner':winners[0].id if len(winners)==1 else None,'reason':'limite de ticks; maior energia' if len(winners)==1 else 'limite de ticks; empate em energia'}
        return self.snapshot()

    def run(self):
        while not self.result: self.step()
        return self.snapshot()
