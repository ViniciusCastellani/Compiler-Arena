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
const astLabels={PROGRAMA:'Robô',BLOCO:'Bloco de comandos',DECL:'Declaração',ATRIBUICAO:'Atribuição',CALL:'Comando',IF:'Se / senão',WHILE:'Enquanto',FOR:'Repetição for',BREAK:'Sair do laço',CONTINUE:'Próxima repetição',LITERAL:'Valor literal',IDENTIFICADOR:'Variável ou sensor',BIN:'Operação binária',BINARY:'Operação binária',UNARY:'Operação unária'};
function sourceLink(line,column){
 const b=node('button',`Linha ${line} · coluna ${column}`,'source-link');
 b.title='Selecionar esta linha no editor';b.onclick=e=>{e.stopPropagation();gotoDiagnostic(`linha ${line}`);};return b;
}
function technical(value,label='Ver dados técnicos'){const d=node('details',undefined,'technical');d.append(node('summary',label),node('pre',typeof value==='string'?value:serialize(value)));return d;}
function intro(area,title,description){const box=node('div',undefined,'inspection-intro');box.append(node('h3',title),node('p',description));area.append(box);}
function astNode(n,depth=0){
 const branch=node('div',undefined,'ast-branch'),head=node('div',undefined,'ast-heading');
 head.append(node('span',astLabels[n.tipo]||n.tipo,'ast-kind'));
 if(n.valor!==null)head.append(node('code',serialize(n.valor),'ast-value'));
 if(n.meta?.type)head.append(node('span',n.meta.type,'type-tag'));
 const children=n.filhos||[];
 if(children.length){const tree=node('details',undefined,'ast-node');tree.open=depth<3;const summary=node('summary');summary.append(head,node('span',`${children.length} ${children.length===1?'filho':'filhos'}`,'muted'));tree.append(summary);children.forEach(c=>tree.append(astNode(c,depth+1)));branch.append(tree);}
 else branch.append(head);
 const info=node('div',undefined,'ast-info');info.append(sourceLink(n.line,n.column));
 if(n.meta?.const)info.append(node('span','Constante','type-tag'));
 branch.append(info);return branch;
}
function astView(area,data){
 intro(area,'AST · Árvore sintática abstrata','Cada ramo representa uma construção do programa. Abra os ramos para explorar comandos, condições e valores; clique na origem para localizar o código.');
 if(!data){area.append(node('p','AST indisponível nesta compilação.','empty'));return;}
 const controls=node('div',undefined,'inspection-controls'),tree=node('div',undefined,'ast-tree');tree.append(astNode(data));
 for(const [label,open] of [['Expandir tudo',true],['Recolher tudo',false]]){const b=node('button',label);b.onclick=()=>tree.querySelectorAll('details').forEach(d=>d.open=open);controls.append(b);}
 area.append(controls,tree,technical(data,'Ver AST em JSON (com metadados)'));
}
function irOperand(o){
 if(!o)return '—';if(o.kind==='constant')return serialize(o.value);
 if(o.kind==='symbol'){const symbol=report.symbols.find(s=>s.id===o.value);return symbol?`${symbol.name} [s${o.value}]`:`s${o.value}`;}
 return (o.kind==='temporary'?'t':'L')+o.value;
}
function instructionText(op,a,b,r){
 if(op==='COPY')return `${r} ← ${a}`;
 if(op==='I2F')return `${r} ← converter ${a} para float`;
 if(op==='SENSOR')return `${r} ← ler sensor ${a}`;
 if(op==='LABEL')return `Destino de salto ${r}`;
 if(op==='JMP')return `Ir para ${r}`;
 if(op==='JZ'||op==='JNZ')return `Se ${a} for ${op==='JZ'?'falso':'verdadeiro'}, ir para ${r}`;
 if(op==='HALT')return 'Encerrar programa';
 if(op.startsWith('BIN:'))return `${r} ← ${a} ${op.slice(4)} ${b}`;
 if(op.startsWith('UN:'))return `${r} ← ${op.slice(3)} ${a}`;
 if(op.startsWith('CMD:')){const name=op.slice(4),label={move:'Avançar',back:'Recuar',rotate:'Girar',scan:'Buscar inimigo',fire:'Disparar'}[name]||name;return `${label} · ${name}(${a==='—'?'':a})`;}
 return `${op} ${a} ${b} → ${r}`;
}
function instructionTable(rows,bytecode=false){
 const t=node('table',undefined,'instruction-table'),head=node('thead'),hr=node('tr');
 ['#',bytecode?'Instrução / opcode':'Operação','O que acontece','Origem'].forEach(x=>hr.append(node('th',x)));head.append(hr);t.append(head);
 const body=node('tbody');rows.forEach((row,i)=>{const tr=node('tr');tr.append(node('td',String(i).padStart(4,'0'),'instruction-index'));
 const op=node('td');op.append(node('code',row.op));if(bytecode)op.append(node('small',`opcode ${row.opcode}`));
 const meaning=node('td',row.text,'instruction-meaning'),origin=node('td');origin.append(sourceLink(row.line,row.column));tr.append(op,meaning,origin);if(row.op==='LABEL')tr.classList.add('label-row');body.append(tr);});t.append(body);return t;
}
function irView(area,optimized){
 const rows=report[optimized?'optimized_ir':'ir']||[];
 intro(area,optimized?'IR otimizada · Após as transformações':'IR original · Passo a passo', 'IR é a representação intermediária do programa. t indica um resultado temporário, s identifica uma variável e L marca um destino de salto. A seta ← significa receber um valor.');
 if(!rows.length){area.append(node('p','IR indisponível nesta compilação.','empty'));return;}
 const count=node('div',undefined,'inspection-stats');
 if(optimized){const before=report.ir.length,removed=before-rows.length;count.textContent=`${before} → ${rows.length} instruções · ${removed>0?removed+' removidas':removed<0?-removed+' adicionadas':'sem alteração na contagem'}. A contagem não mede tempo de execução.`;}
 else count.textContent=`${rows.length} instruções antes das otimizações.`;
 area.append(count,instructionTable(rows.map(q=>({op:q.op,text:instructionText(q.op,irOperand(q.arg1),irOperand(q.arg2),irOperand(q.result)),line:q.line,column:q.column}))),technical(report[optimized?'optimized_ir_text':'ir_text']||'' ,'Ver IR em formato técnico'));
}
const bytecodeNames=['HALT','COPY','I2F','SENSOR','JMP','JZ','JNZ',...['!','+','-'].map(x=>'UN:'+x),...['+','-','*','/','%','<','<=','>','>=','==','!='].map(x=>'BIN:'+x),...['move','back','rotate','scan','fire'].map(x=>'CMD:'+x)];
function bytecodeView(area,data){
 intro(area,'Bytecode · Instruções da máquina virtual','A máquina virtual executa estas instruções na ordem dos índices, começando em 0000. r identifica um registrador de memória; saltos alteram a próxima instrução executada.');
 if(!data){area.append(node('p','Bytecode indisponível. Compile um programa sem erros.','empty'));return;}
 area.append(node('p',`${data.robot} · ${data.instructions.length} instruções · ${data.register_types.length} registradores`,'inspection-stats'));
 const operand=x=>!x?'—':x[0]==='r'?`r${x[1]}`:serialize(x[2]);
 const rows=data.instructions.map(q=>{const op=bytecodeNames[q.opcode]||`Opcode ${q.opcode}`,a=q.args;let text;
 if(op==='JMP')text=instructionText(op,'—','—',`instrução ${a[0]}`);
 else if(op==='JZ'||op==='JNZ')text=instructionText(op,operand(a[0]),'—',`instrução ${a[1]}`);
 else if(op.startsWith('CMD:')||op==='HALT')text=instructionText(op,operand(a[0]),'—','—');
 else text=instructionText(op,operand(a[1]),operand(a[2]),`r${a[0]}`);
 return {op,opcode:q.opcode,text,line:q.source[0],column:q.source[1]};});
 area.append(instructionTable(rows,true),technical(data.register_types.map((type,i)=>`r${i}: ${type}`).join('\n'),'Ver tipos dos registradores'),technical(data,'Ver bytecode em JSON'));
}
function gotoDiagnostic(message){const match=message.match(/linha\s+(\d+)/i);if(!match)return;const lines=$('source').value.split('\n'),line=Number(match[1])-1;const start=lines.slice(0,line).reduce((a,b)=>a+b.length+1,0);$('source').focus();$('source').setSelectionRange(start,start+(lines[line]?.length||0));$('source').scrollTop=Math.max(0,(line-4)*23);lineNumbers();}
function renderInspection(){
 const area=$('inspection');area.replaceChildren();
 if(!report){area.append(node('p','Compile o código para inspecionar esta etapa.','empty'));return;}
 const data=report[activeTab];
 if(activeTab==='tokens')area.append(table(['Tipo','Lexema','Valor','Linha','Coluna'],data.map(t=>[t.type,t.lexeme,t.value,t.line,t.column])));
 else if(activeTab==='symbols')area.append(table(['ID','Nome','Tipo','Escopo','Mutável','Origem','Constante'],data.map(s=>[s.id,s.name,s.type,s.scope,s.mutable,`${s.line}:${s.column}`,s.constant])));
 else if(activeTab==='ast')astView(area,data);
 else if(activeTab==='ir_text'||activeTab==='optimized_ir_text')irView(area,activeTab==='optimized_ir_text');
 else if(activeTab==='diagnostics'){
  if(!data.length)area.append(node('p','Nenhum diagnóstico. Compilação válida.','empty'));
  data.forEach(message=>{const b=node('button',message,'diagnostic');b.onclick=()=>gotoDiagnostic(message);area.append(b);});
 }else if(activeTab==='bytecode')bytecodeView(area,data);
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
