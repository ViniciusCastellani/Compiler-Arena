'use strict';
/* Apresentação entre snapshots. Acertos, dano e eliminações vêm do Python. */
class ArenaRenderer {
 constructor(canvas, colors) {
  this.canvas=canvas; this.ctx=canvas.getContext('2d'); this.colors=colors;
  this.frame=0; this.transition=null; this.current=null; this.finish=null;
  this.reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
  this.draw(null, null, 1);
 }
 cancel() {
  cancelAnimationFrame(this.frame); this.frame=0;
  if(this.finish){const done=this.finish;this.finish=null;done();}
  this.transition=null;
 }
 reset(snapshot) {
  this.cancel();this.current=snapshot;this.draw(snapshot,snapshot,1);
 }
 present(previous, next, duration) {
  this.cancel(); this.current=next;
  if(!previous || next.tick<=previous.tick){this.draw(next,next,1);return Promise.resolve();}
  const reduced=this.reducedMotion.matches;
  const length=duration;
  const start=performance.now();
  this.transition={previous,next,start,duration:length};
  return new Promise(resolve=>{
   this.finish=resolve;
   const frame=now=>{
    const progress=Math.min(1,Math.max(0,(now-start)/length));
    this.draw(previous,next,progress,reduced);
    if(progress<1){this.frame=requestAnimationFrame(frame);}
    else{this.frame=0;this.transition=null;this.finish=null;resolve();}
   };
   this.frame=requestAnimationFrame(frame);
  });
 }
 draw(previous,next,progress,reduced=false) {
  const ctx=this.ctx;
  ctx.clearRect(0,0,800,600);ctx.fillStyle='#101e24';ctx.fillRect(0,0,800,600);
  ctx.lineWidth=1;ctx.strokeStyle='#23353d';
  for(let x=0;x<=800;x+=50){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,600);ctx.stroke();}
  for(let y=0;y<=600;y+=50){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(800,y);ctx.stroke();}
  ctx.strokeStyle='#4a626b';ctx.strokeRect(1,1,798,598);
  if(!next){ctx.fillStyle='#7f999e';ctx.textAlign='center';ctx.font='18px system-ui';ctx.fillText('Sua próxima batalha acontece aqui.',400,285);ctx.font='13px system-ui';ctx.fillText('Adicione dois robôs e prepare a arena.',400,313);return;}
  const smooth=progress*progress*(3-2*progress);
  const amount=reduced?1:smooth;
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
   const eliminated=r.state!=='ativo';
   ctx.globalAlpha=eliminated?1-.72*amount:1;
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
  if(progress<1)effects.forEach(effect=>this.drawEffect(effect,progress,reduced));
 }
 drawEffect(effect,t,reduced) {
  const ctx=this.ctx, color=this.colors[effect.robot%this.colors.length];
  ctx.save();ctx.lineCap='round';
  if(effect.type==='scan'){
   ctx.globalAlpha=(1-t)*.36;ctx.strokeStyle=color;ctx.lineWidth=2;
   const radius=reduced?55:25+t*Math.min(effect.range,320);ctx.beginPath();ctx.arc(effect.x,600-effect.y,radius,0,Math.PI*2);ctx.stroke();
  }else if(effect.type==='fire'){
   const x=effect.x,y=600-effect.y,dx=effect.end_x-x,dy=(600-effect.end_y)-y;
   const length=Math.hypot(dx,dy),ux=length?dx/length:1,uy=length?dy/length:0;
   const tip=reduced?1:Math.min(1,t/.48),tail=reduced?0:Math.max(0,tip-.18);
   if(t<.64){
    ctx.globalAlpha=Math.min(1,(.64-t)*5);ctx.strokeStyle=color;ctx.shadowColor=color;ctx.shadowBlur=reduced?0:15;
    ctx.lineWidth=2+effect.power;ctx.beginPath();ctx.moveTo(x+dx*tail,y+dy*tail);ctx.lineTo(x+dx*tip,y+dy*tip);ctx.stroke();
    ctx.fillStyle='#fff8cf';ctx.beginPath();ctx.arc(x+dx*tip,y+dy*tip,2+effect.power,0,Math.PI*2);ctx.fill();
   }
   if(t<.32){
    ctx.globalAlpha=1-t/.32;ctx.fillStyle='#ffe6a3';ctx.shadowBlur=reduced?0:18;
    ctx.beginPath();ctx.arc(x+ux*24,y+uy*24,3+(1-t/.32)*(3+effect.power*2),0,Math.PI*2);ctx.fill();
   }
   if(effect.target!==null&&t>=.42){
    const hit=(t-.42)/.58;ctx.globalAlpha=1-hit;ctx.shadowBlur=0;
    ctx.strokeStyle='#ffd18b';ctx.lineWidth=2;ctx.beginPath();ctx.arc(effect.end_x,600-effect.end_y,5+hit*(reduced?10:30),0,Math.PI*2);ctx.stroke();
    if(!reduced)for(let i=0;i<8;i++){const a=i*Math.PI/4,r=9+hit*32;ctx.beginPath();ctx.moveTo(effect.end_x+Math.cos(a)*r,600-effect.end_y+Math.sin(a)*r);ctx.lineTo(effect.end_x+Math.cos(a)*(r+6),600-effect.end_y+Math.sin(a)*(r+6));ctx.stroke();}
    ctx.fillStyle='#ffce9a';ctx.font='bold 15px system-ui';ctx.textAlign='center';ctx.fillText('−'+effect.damage,effect.end_x,600-effect.end_y-24-hit*20);
   }
  }else if(effect.type==='elimination'){
   const p=Math.max(0,(t-.4)/.6);
   if(t>=.4){ctx.globalAlpha=1-p;ctx.strokeStyle='#ffb47e';ctx.lineWidth=3;ctx.beginPath();ctx.arc(effect.x,600-effect.y,14+p*(reduced?12:50),0,Math.PI*2);ctx.stroke();}
  }
  ctx.restore();
 }
}
