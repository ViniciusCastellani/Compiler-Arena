'use strict';
const $=id=>document.getElementById(id);
const session=crypto.randomUUID();
const stages=['léxica','sintática','semântica','IR','otimização','bytecode'];
const tabNames=[['tokens','Tokens'],['ast','AST'],['symbols','Símbolos'],['diagnostics','Diagnósticos'],['ir_text','IR original'],['optimized_ir_text','IR otimizada'],['optimizations','Otimizações'],['bytecode','Bytecode']];
const colors=['#48cfad','#69a8fa','#e6b456','#ed8b9b','#c39bf3','#6dd3e0'];
let report=null, revision=0, activeTab='tokens', dirty=false, fileName='alpha.robo', examples=[], pool=[];
let battle=null, playing=false, battleBusy=false;
const renderer=new ArenaRenderer($('arena'),colors);
function node(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function notify(message,error=false){$('notice').hidden=false;$('notice').textContent=message;$('notice').classList.toggle('error',error);}
function clearNotice(){$('notice').hidden=true;}
async function api(path,data={}){
 const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Arena-Session':session},body:JSON.stringify(data)});
 const result=await response.json();if(!response.ok)throw Error(result.error||'Falha de comunicação com o servidor.');return result;
}
function isFloatTag(v){return v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===1&&typeof v.$float==='string';}
function plainFloats(v){if(isFloatTag(v))return Number(v.$float);if(Array.isArray(v))return v.map(plainFloats);if(v&&typeof v==='object')return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,plainFloats(x)]));return v;}
function isIntegerTag(v){return v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===1&&typeof v.$integer==='string';}
// Exportação preserva números RoboLang exatos, mesmo fora do intervalo seguro do JS.
function serialize(v,depth=0){
 if(isIntegerTag(v))return v.$integer;
 if(isFloatTag(v))return v.$float;
 if(v===null||typeof v!=='object')return JSON.stringify(v);
 const arr=Array.isArray(v), entries=arr?v:Object.entries(v), pad='  '.repeat(depth), next=pad+'  ';
 if(!entries.length)return arr?'[]':'{}';
 return (arr?'[':'{')+'\n'+entries.map(x=>next+(arr?'':JSON.stringify(x[0])+': ')+serialize(arr?x:x[1],depth+1)).join(',\n')+'\n'+pad+(arr?']':'}');
}
function displayValue(v){return typeof v==='string'?v:serialize(v);}
function download(name,value,type='application/json'){
 const blob=new Blob([typeof value==='string'?value:serialize(value)],{type});const url=URL.createObjectURL(blob);const a=node('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function lineNumbers(){$('line-numbers').textContent=Array.from({length:$('source').value.split('\n').length},(_,i)=>i+1).join('\n');$('line-numbers').scrollTop=$('source').scrollTop;}
function stageView(){
 $('stages').replaceChildren();for(const name of stages){const state=report?.stages[name]||'não executada';const label=node('span',(state==='concluída'?'✓ ':state==='erro'?'× ':'· ')+name,'stage'+(state==='concluída'?' done':state==='erro'?' error':''));label.title=name+': '+state;$('stages').append(label);}
}
function invalidated(){
 revision++;report=null;$('export-report').disabled=true;$('export-bytecode').disabled=true;$('add').disabled=true;
 $('compile-state').textContent='Compilação necessária';$('metrics').textContent='Texto ou otimizações alterados. Compile esta versão.';
 $('revision').textContent='Versão '+revision+' · resultados invalidados';stageView();renderInspection();
}
function edited(){dirty=true;invalidated();lineNumbers();$('filename').textContent=fileName+' *';document.title='* '+fileName+' · Compiler Arena';}
function discard(){return !dirty||confirm('Há alterações não salvas. Deseja descartá-las?');}
function setSource(text,name){$('source').value=text;fileName=name;dirty=false;invalidated();lineNumbers();$('filename').textContent=name;document.title=name+' · Compiler Arena';}
function table(headers,rows){const t=node('table'),head=node('thead'),tr=node('tr');headers.forEach(h=>tr.append(node('th',h)));head.append(tr);t.append(head);const body=node('tbody');rows.forEach(row=>{const r=node('tr');row.forEach(value=>{const cell=node('td',displayValue(value));cell.title=displayValue(value);r.append(cell);});body.append(r);});t.append(body);return t;}
function astNode(n,opened=false){const tree=node('details');tree.open=opened;tree.append(node('summary',`${n.tipo} ${n.valor===null?'':displayValue(n.valor)}  @${n.line}:${n.column}`));for(const c of n.filhos)tree.append(astNode(c));if(n.meta&&Object.keys(n.meta).length)tree.append(node('pre',serialize(n.meta)));return tree;}
function gotoDiagnostic(message){const match=message.match(/linha\s+(\d+)/i);if(!match)return;const lines=$('source').value.split('\n'),line=Number(match[1])-1;const start=lines.slice(0,line).reduce((a,b)=>a+b.length+1,0);$('source').focus();$('source').setSelectionRange(start,start+(lines[line]?.length||0));$('source').scrollTop=Math.max(0,(line-4)*23);lineNumbers();}
function renderInspection(){
 const area=$('inspection');area.replaceChildren();
 if(!report){area.append(node('p','Compile o código para inspecionar esta etapa.','empty'));return;}
 const data=report[activeTab];
 if(activeTab==='tokens')area.append(table(['Tipo','Lexema','Valor','Linha','Coluna'],data.map(t=>[t.type,t.lexeme,t.value,t.line,t.column])));
 else if(activeTab==='symbols')area.append(table(['ID','Nome','Tipo','Escopo','Mutável','Origem','Constante'],data.map(s=>[s.id,s.name,s.type,s.scope,s.mutable,`${s.line}:${s.column}`,s.constant])));
 else if(activeTab==='ast'){if(data)area.append(astNode(data,true));else area.append(node('p','AST indisponível nesta compilação.','empty'));}
 else if(activeTab==='diagnostics'){
  if(!data.length)area.append(node('p','Nenhum diagnóstico. Compilação válida.','empty'));
  data.forEach(message=>{const b=node('button',message,'diagnostic');b.onclick=()=>gotoDiagnostic(message);area.append(b);});
 }else if(activeTab==='bytecode'&&data)area.append(table(['Índice','Opcode','Operandos','Origem'],data.instructions.map((r,i)=>[i,r.opcode,r.args,r.source])));
 else area.append(node('pre',typeof data==='string'?data:serialize(data??null)));
}
function selectTab(key){activeTab=key;document.querySelectorAll('[role=tab]').forEach(b=>{const selected=b.dataset.key===key;b.setAttribute('aria-selected',String(selected));b.tabIndex=selected?0:-1;});$('inspection').setAttribute('aria-labelledby','tab-'+key);renderInspection();}
for(const [key,label]of tabNames){const b=node('button',label);b.id='tab-'+key;b.dataset.key=key;b.role='tab';b.setAttribute('aria-controls','inspection');b.onclick=()=>selectTab(key);b.onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const i=tabNames.findIndex(t=>t[0]===key),j=(i+(e.key==='ArrowRight'?1:-1)+tabNames.length)%tabNames.length;selectTab(tabNames[j][0]);$('tab-'+tabNames[j][0]).focus();}};document.querySelector('.tabs').append(b);}
async function compile(){
 clearNotice();const current=revision, source=$('source').value, optimization=$('optimization').checked;
 $('compile').disabled=true;$('compile').textContent='Compilando…';$('compile-state').textContent='Compilando';
 try{const response=await api('compile',{source,optimization});if(current!==revision)return;report=response;stageView();
 $('compile-state').textContent=report.bytecode?'Compilação válida':'Compilação com erro';$('export-report').disabled=false;$('export-bytecode').disabled=!report.bytecode;$('add').disabled=!report.bytecode;
 $('revision').textContent=`Versão ${current} · SHA-256 ${report.sha256.slice(0,16)}`;
 const m=report.metrics;$('metrics').textContent=m?`${m.before} → ${m.after} instruções IR · redução ${Number(isFloatTag(m.reduction_percent)?m.reduction_percent.$float:m.reduction_percent).toFixed(2)}% · não representa ganho de tempo medido.`:'A cadeia foi interrompida. Consulte os diagnósticos.';
 if(report.diagnostics.length)selectTab('diagnostics');else renderInspection();
 }catch(e){if(current===revision){$('compile-state').textContent='Falha de conexão';notify(e.message,true);}}
 finally{$('compile').disabled=false;$('compile').textContent='Compilar robô →';}
}
function poolView(){
 $('robot-pool').replaceChildren();if(!pool.length)$('robot-pool').append(node('p','Compile um robô e adicione à lista.','empty'));
 pool.forEach((p,i)=>{const row=node('div',undefined,'pool-row'),check=node('input');check.type='checkbox';check.checked=p.selected;check.id='robot-'+i;check.onchange=()=>p.selected=check.checked;const label=node('label',p.bytecode.robot);label.htmlFor=check.id;label.append(node('small',p.label));const del=node('button','×');del.title='Remover '+p.bytecode.robot;del.setAttribute('aria-label',del.title);del.onclick=()=>{pool.splice(i,1);poolView();};row.append(check,label,del);$('robot-pool').append(row);});
}
function pause(){playing=false;controls();}
function controls(){
 const ready=!!battle,ended=!!battle?.result;
 $('start').disabled=!ready||ended||playing||battleBusy;$('pause').disabled=!playing;
 $('step').disabled=!ready||ended||playing||battleBusy;$('reset').disabled=!ready||battleBusy;
 $('create-battle').disabled=battleBusy;$('export-battle').disabled=!ready||battleBusy;
 if(ready)$('battle-state').textContent=ended?'Batalha encerrada':playing?'Em execução':'Pausada';
}
async function battleRequest(action,data={}){
 if(battleBusy)throw Error('Aguarde a conclusão do tick atual.');battleBusy=true;controls();
 try{
  const response=await api('battle/'+action,data), previous=battle;
  battle=plainFloats(response.snapshot);renderBattle();
  // Em reprodução, a animação ocupa o período inteiro do tick e emenda no próximo.
  const speed=Number($('speed').value);
  if(action==='step')await renderer.present(previous,battle,playing?1000/speed:Math.max(80,900/speed),playing);
  else renderer.reset(battle);
  return response;
 }
 finally{battleBusy=false;controls();}
}
async function loop(){
 // Sem espera extra: o próximo tick é pedido assim que a animação do anterior termina.
 try{while(playing){await battleRequest('step');if(battle.result){pause();return;}}}
 catch(e){pause();notify(e.message,true);}
}
function renderBattle(){
 if(!battle)return;
 $('tick').textContent=`TICK ${String(battle.tick).padStart(4,'0')} / ${battle.max_ticks}`;
 $('robot-states').replaceChildren();battle.robots.forEach(r=>{const card=node('div',undefined,'state-card');card.style.setProperty('--robot-color',colors[r.id%colors.length]);card.append(node('strong',`${r.id} · ${r.name}`));const life=node('progress','','hp');life.max=100;life.value=r.hp;life.setAttribute('aria-label','Vida de '+r.name);const meter=node('progress');meter.max=100;meter.value=r.energy;meter.setAttribute('aria-label','Energia de '+r.name);card.append(life,node('span',`${r.hp} / 100 vida${r.hit?' · atingido':''}`),meter,node('span',r.energy+' / 100 energia'),node('small',`${r.state} · VM ${r.vm} · PC ${r.pc}`));if(r.error)card.append(node('small',r.error));$('robot-states').append(card);});
 $('logs').replaceChildren();if(!battle.recent.length)$('logs').append(node('p','Nenhuma ação emitida.'));
 for(const event of [...battle.recent].reverse()){const r=battle.robots.find(x=>x.id===event.robot);const target=battle.robots.find(x=>x.id===event.hit);const message=event.error||(target?`acertou ${target.name} · −${event.damage} vida`:`${event.command}(${event.args.join(', ')})${event.clamped_from?' · limitado de '+event.clamped_from.join(', '):''}${event.executed?'':' · energia insuficiente'}`);$('logs').append(node('div',`Tick ${event.tick} · ${r.name}: ${message}`,'log'));}
 $('result').hidden=!battle.result;if(battle.result){const winner=battle.robots.find(r=>r.id===battle.result.winner);$('result').textContent=(winner?'Vencedor: '+winner.name:'Empate')+' · '+battle.result.reason;}
}
function bind(id,fn){$(id).onclick=async()=>{try{await fn();}catch(e){notify(e.message,true);}};}
bind('new',()=>{if(discard())setSource('robot Novo {\n    scan();\n}\n','novo.robo');});
bind('open',()=>{if(discard())$('source-file').click();});
$('source-file').onchange=async e=>{const f=e.target.files[0];try{if(f){if(f.size>1000000)throw Error('Arquivo-fonte muito grande.');setSource(await f.text(),f.name);}}catch(err){notify(err.message,true);}finally{e.target.value='';}};
bind('save',()=>{download(fileName,$('source').value,'text/plain;charset=utf-8');dirty=false;$('filename').textContent=fileName;document.title=fileName+' · Compiler Arena';});
$('examples').onchange=()=>{const found=examples.find(e=>e.name===$('examples').value);if(found&&discard())setSource(found.source,found.name);$('examples').value='';};
$('source').oninput=edited;$('source').onscroll=()=>{$('line-numbers').scrollTop=$('source').scrollTop;};
$('source').onkeydown=e=>{if(e.key==='Tab'){e.preventDefault();$('source').setRangeText('    ',$('source').selectionStart,$('source').selectionEnd,'end');edited();}};
$('optimization').onchange=invalidated;bind('compile',compile);
bind('export-report',()=>{if(!report)throw Error('Compile a versão atual.');download('relatorio_compiler_arena.json',report);});
bind('export-bytecode',()=>{if(!report?.bytecode)throw Error('Compile um programa válido.');download(report.bytecode.robot+'.rbc.json',report.bytecode);});
bind('add',()=>{if(!report?.bytecode)throw Error('Compile a versão atual sem erros.');pool.push({bytecode:report.bytecode,label:'SHA '+report.sha256.slice(0,12),selected:true});poolView();notify(report.bytecode.robot+' adicionado à lista de batalha.');});
bind('load-bytecode',()=>$('bytecode-file').click());
$('bytecode-file').onchange=async e=>{for(const file of e.target.files){try{if(file.size>8000000)throw Error('Bytecode excede 8 MB.');const data=await api('validate',{text:await file.text()});pool.push({bytecode:data.bytecode,label:file.name,selected:true});poolView();}catch(err){notify(file.name+': '+err.message,true);}}e.target.value='';};
bind('create-battle',async()=>{pause();clearNotice();const programs=pool.filter(p=>p.selected).map(p=>p.bytecode);await battleRequest('create',{programs,max_ticks:Number($('max-ticks').value),budget:Number($('budget').value)});notify('Batalha preparada. Inicie ou avance um tick.');});
bind('start',()=>{if(!battle||battle.result)return;playing=true;controls();void loop();});bind('pause',pause);
bind('step',()=>battleRequest('step'));bind('reset',async()=>{pause();await battleRequest('reset');});
bind('export-battle',async()=>{const response=await api('battle/export');download('batalha.json',response);});
$('speed').oninput=()=>{$('speed-value').textContent=$('speed').value+(Number($('speed').value)===1?' tick/s':' ticks/s');};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
window.addEventListener('pagehide',()=>{fetch('/api/battle/close',{method:'POST',headers:{'Content-Type':'application/json','X-Arena-Session':session},body:'{}',keepalive:true}).catch(()=>{});});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();$('save').click();}});
async function init(){stageView();selectTab('tokens');try{const response=await fetch('/api/examples');if(!response.ok)throw Error('Não foi possível carregar os exemplos.');examples=await response.json();for(const e of examples){const option=node('option',e.name);option.value=e.name;$('examples').append(option);}const alpha=examples.find(e=>e.name==='alpha.robo');if(alpha)setSource(alpha.source,alpha.name);$('connection').textContent='● Python conectado';}catch(e){$('connection').textContent='Servidor indisponível';notify(e.message,true);}}
void init();
