'use strict';
/* Apresentação entre snapshots. Acertos, dano e eliminações vêm do Python. */
class ArenaRenderer {
 constructor(canvas, colors) {
  this.canvas=canvas; this.ctx=canvas.getContext('2d'); this.colors=colors;
  this.frame=0; this.transition=null; this.current=null; this.finish=null;
  // Explosões e textos de dano vivem em tempo real (ms), não presos ao fim do tick.
  this.bursts=[];
  this.reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
  this.render(performance.now());
 }
 settle() {
  if(this.finish){const done=this.finish;this.finish=null;done();}
  this.transition=null;
 }
 cancel() {
  cancelAnimationFrame(this.frame); this.frame=0;
  this.settle(); this.bursts=[];
 }
 reset(snapshot) {
  this.cancel();this.current=snapshot;this.render(performance.now());
 }
 // linear=true na reprodução contínua: velocidade constante, sem frear a cada tick.
 present(previous, next, duration, linear=false) {
  this.settle(); this.current=next;
  if(!previous || next.tick<=previous.tick){this.render(performance.now());return Promise.resolve();}
  const start=performance.now();
  this.transition={previous,next,start,duration,linear};
  for(const e of next.effects||[]){
   if(e.type==='hit')this.bursts.push({...e,at:start+(e.time??.5)*duration,life:650});
   else if(e.type==='elimination')this.bursts.push({...e,at:start+.5*duration,life:900});
  }
  return new Promise(resolve=>{this.finish=resolve;this.loop();});
 }
 loop() {
  if(this.frame)return;
  const frame=now=>{
   this.frame=0;
   const t=this.transition;
   if(t&&now-t.start>=t.duration)this.settle();
   this.bursts=this.bursts.filter(b=>now<b.at+b.life);
   this.render(now);
   if(this.transition||this.bursts.length)this.frame=requestAnimationFrame(frame);
  };
  this.frame=requestAnimationFrame(frame);
 }
 render(now) {
  const t=this.transition;
  if(t){
   const progress=Math.min(1,Math.max(0,(now-t.start)/t.duration));
   this.draw(t.previous,t.next,progress,t.linear,now);
  }else this.draw(this.current,this.current,1,true,now);
 }
 draw(previous,next,progress,linear,now) {
  const ctx=this.ctx, reduced=this.reducedMotion.matches;
  ctx.clearRect(0,0,800,600);ctx.fillStyle='#101e24';ctx.fillRect(0,0,800,600);
  ctx.lineWidth=1;ctx.strokeStyle='#23353d';
  for(let x=0;x<=800;x+=50){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,600);ctx.stroke();}
  for(let y=0;y<=600;y+=50){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(800,y);ctx.stroke();}
  ctx.strokeStyle='#4a626b';ctx.strokeRect(1,1,798,598);
  if(!next){ctx.fillStyle='#7f999e';ctx.textAlign='center';ctx.font='18px system-ui';ctx.fillText('Sua próxima batalha acontece aqui.',400,285);ctx.font='13px system-ui';ctx.fillText('Adicione dois robôs e prepare a arena.',400,313);return;}
  const eased=linear?progress:progress*progress*(3-2*progress);
  const amount=reduced?1:eased;
  const old=new Map(previous.robots.map(r=>[r.id,r]));
  const rotations=new Map((next.effects||[]).filter(e=>e.type==='rotate').map(e=>[e.robot,e.degrees]));
  const effects=previous===next?[]:(next.effects||[]);
  // Movimento: rastro e posição interpolada. Colisões canceladas não deslocam o desenho.
  next.robots.forEach(r=>{
   const before=old.get(r.id)||r, moving=before.x!==r.x||before.y!==r.y;
   const x=before.x+(r.x-before.x)*amount, y=600-(before.y+(r.y-before.y)*amount);
   const delta=rotations.has(r.id)?rotations.get(r.id):((r.angle-before.angle+540)%360)-180;
   const angle=(before.angle+delta*amount)*Math.PI/180;
   const color=this.colors[r.id%this.colors.length];
   ctx.save();
   if(moving&&progress<1&&!reduced){
    ctx.globalAlpha=.35*(1-progress);ctx.strokeStyle=color;ctx.lineWidth=8;ctx.lineCap='round';
    ctx.beginPath();ctx.moveTo(before.x,600-before.y);ctx.lineTo(x,y);ctx.stroke();
   }
   // Só anima o esmaecimento no tick da eliminação; depois permanece apagado.
   const eliminated=r.state!=='ativo', wasEliminated=before.state!=='ativo';
   ctx.globalAlpha=wasEliminated?.28:eliminated?1-.72*amount:1;
   ctx.translate(x,y);ctx.rotate(-angle);
   // Esteiras e corpo deixam o sentido do movimento visível.
   ctx.fillStyle='#081318';ctx.fillRect(-13,-14,26,7);ctx.fillRect(-13,7,26,7);
   ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.strokeRect(-13,-14,26,7);ctx.strokeRect(-13,7,26,7);
   if(moving&&!reduced){ctx.strokeStyle='#b5d3d7';ctx.lineWidth=1;const offset=(progress*24)%6;for(let i=-12;i<13;i+=6){ctx.beginPath();ctx.moveTo(i+offset,-13);ctx.lineTo(i+offset,-8);ctx.moveTo(i+offset,8);ctx.lineTo(i+offset,13);ctx.stroke();}}
   ctx.fillStyle=color;ctx.beginPath();ctx.arc(0,0,11,0,Math.PI*2);ctx.fill();
   ctx.fillStyle='#dffcf1';ctx.fillRect(2,-3,22,6);ctx.fillStyle='#203c3e';ctx.beginPath();ctx.arc(0,0,5,0,Math.PI*2);ctx.fill();ctx.restore();
   ctx.save();ctx.globalAlpha=eliminated?.45:1;ctx.fillStyle=color;ctx.textAlign='center';ctx.font='13px system-ui';
   const label=r.name.length>20?r.name.slice(0,19)+'…':r.name;ctx.fillText(label,Math.min(730,Math.max(70,x)),Math.max(18,y-24));ctx.restore();
  });
  this.drawProjectiles(previous,next,effects,progress,reduced);
  if(progress<1)effects.forEach(effect=>this.drawEffect(effect,progress,reduced));
  this.bursts.forEach(b=>this.drawBurst(b,now,reduced));
 }
 drawProjectiles(previous,next,effects,t,reduced) {
  // Posições vêm do Python; projéteis andam em velocidade constante (interpolação linear).
  const before=new Map((previous.projectiles||[]).map(p=>[p.id,p]));
  const fired=new Map(effects.filter(e=>e.type==='fire').map(e=>[e.projectile,e]));
  const startOf=id=>before.get(id)||fired.get(id);
  const k=reduced?1:t;
  for(const p of next.projectiles||[])this.drawShot(startOf(p.id),p,p.owner,p.power,k,reduced);
  // Encerrados no tick: o acerto chega ao ponto de contato no instante informado pelo servidor.
  for(const e of effects){
   if(e.type!=='hit'&&e.type!=='expire')continue;
   const start=startOf(e.projectile), until=e.type==='hit'?(e.time??1):1;
   if(!start||reduced||t>=until)continue;
   this.drawShot(start,e,e.robot,start.power||1,until?t/until:1,reduced);
  }
 }
 drawShot(start,end,owner,power,k,reduced) {
  if(!start)start=end;
  const ctx=this.ctx,color=this.colors[owner%this.colors.length];
  const at=f=>[start.x+(end.x-start.x)*f,600-(start.y+(end.y-start.y)*f)];
  const [x,y]=at(k);
  ctx.save();ctx.lineCap='round';
  if(!reduced){
   // Rastro de comprimento fixo atrás do projétil, contínuo entre ticks.
   const dx=end.x-start.x,dy=end.y-start.y,len=Math.hypot(dx,dy)||1;
   ctx.globalAlpha=.45;ctx.strokeStyle=color;ctx.lineWidth=1+power;ctx.beginPath();
   ctx.moveTo(x-dx/len*18,y+dy/len*18);ctx.lineTo(x,y);ctx.stroke();
  }
  ctx.globalAlpha=1;ctx.fillStyle='#fff8cf';ctx.shadowColor=color;ctx.shadowBlur=reduced?0:12;
  ctx.beginPath();ctx.arc(x,y,2+power,0,Math.PI*2);ctx.fill();ctx.restore();
 }
 drawEffect(effect,t,reduced) {
  const ctx=this.ctx, color=this.colors[effect.robot%this.colors.length];
  ctx.save();ctx.lineCap='round';
  if(effect.type==='scan'){
   ctx.globalAlpha=(1-t)*.36;ctx.strokeStyle=color;ctx.lineWidth=2;
   const radius=reduced?55:25+t*320;ctx.beginPath();ctx.arc(effect.x,600-effect.y,radius,0,Math.PI*2);ctx.stroke();
  }else if(effect.type==='fire'&&t<.35){
   const a=effect.angle*Math.PI/180,x=effect.x+Math.cos(a)*24,y=600-(effect.y+Math.sin(a)*24);
   ctx.globalAlpha=1-t/.35;ctx.fillStyle='#ffe6a3';ctx.shadowColor=color;ctx.shadowBlur=reduced?0:18;
   ctx.beginPath();ctx.arc(x,y,3+(1-t/.35)*(3+effect.power*2),0,Math.PI*2);ctx.fill();
  }
  ctx.restore();
 }
 drawBurst(b,now,reduced) {
  if(now<b.at)return;
  const ctx=this.ctx, p=reduced?1:(now-b.at)/b.life;
  ctx.save();ctx.lineCap='round';
  if(b.type==='hit'){
   ctx.globalAlpha=1-p*.9;ctx.strokeStyle='#ffd18b';ctx.lineWidth=2;
   ctx.beginPath();ctx.arc(b.x,600-b.y,5+p*(reduced?10:30),0,Math.PI*2);ctx.stroke();
   if(!reduced)for(let i=0;i<8;i++){const a=i*Math.PI/4,r=9+p*32;ctx.beginPath();ctx.moveTo(b.x+Math.cos(a)*r,600-b.y+Math.sin(a)*r);ctx.lineTo(b.x+Math.cos(a)*(r+6),600-b.y+Math.sin(a)*(r+6));ctx.stroke();}
   ctx.fillStyle='#ffce9a';ctx.font='bold 15px system-ui';ctx.textAlign='center';ctx.fillText('−'+b.damage,b.x,600-b.y-24-p*20);
  }else if(b.type==='elimination'){
   ctx.globalAlpha=1-p;ctx.strokeStyle='#ffb47e';ctx.lineWidth=3;
   ctx.beginPath();ctx.arc(b.x,600-b.y,14+p*(reduced?12:50),0,Math.PI*2);ctx.stroke();
  }
  ctx.restore();
 }
}
