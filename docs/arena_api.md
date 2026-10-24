# API e arena

| Comando | Argumento | Intervalo | Custo de energia |
|---|---|---|---|
| move | int/float | 0..100 | 1 |
| back | int/float | 0..100 | 1 |
| rotate | int/float | -360..360 | 1 |
| scan | nenhum | — | 1 |
| fire | int | 1..3 | 2×potência |

Não retornam valores, logo não são expressões. Constantes fora do intervalo são
erro semântico de compilação. Valores dinâmicos fora do intervalo são limitados
(clamp) pela VM ao extremo mais próximo, e o log registra `clamped_from` com o
valor original; o robô não é desclassificado. Tipos continuam obrigatórios.
Custos são inteiros mesmo para movimento/ângulo float.

Sensores (somente leitura):

| Sensor | Tipo | Significado |
|---|---|---|
| hp | int | vida, 0..100; chegar a 0 elimina |
| energy | int | recurso para ações, 0..100; regenera |
| heading | float | orientação própria em graus, [-180,180) |
| hit | bool | foi atingido por projétil no tick anterior |
| position.x/y | float | posição do centro |
| enemy.visible/distance/direction | bool/float/float | resultado do último scan |

hp/energy/heading/hit/position leem o snapshot inicial do tick. enemy lê o
último scan, nunca executa uma busca. Antes do primeiro scan ou sem alvo:
false, -1.0, 0.0.

## Vida e energia

Vida e energia são separadas. Projéteis tiram vida; comandos gastam energia.
Ao fim de cada tick, todo robô ativo recupera 1 de energia (máximo 100). Comando
sem energia suficiente é consumido sem efeito nem custo parcial. Energia zero não
elimina: o robô só perde quando a vida chega a zero. Assim, ficar parado não é
mais vantagem, e um laço de `scan()` se sustenta sozinho.

## Geometria

Arena 800×600, x para direita e y para cima. A renderização inverte y apenas
para desenhar. Raio físico 12, vida e energia iniciais 100, posições em círculo
de raio 200 ao redor (400,300), direções iniciais para o centro. Entre 2 e 16
robôs, condições simétricas. Ângulos positivos anti-horários, 0° direita.

## Ordem de um tick

1. Captura as posições/direções/vida/energia de todos os ativos.
2. Executa cada VM com esse estado e coleta até um comando.
3. Cobra custo de comandos executáveis; planeja movimentos/rotações, calcula
   scans e cria projéteis no estado inicial.
4. Movimento contra a parede para no limite (o robô encosta nela). Colisões
   entre robôs consideram a distância mínima entre as trajetórias simultâneas;
   ambos param na posição inicial; repete até ponto fixo.
5. Todos os projéteis (antigos e recém-disparados) avançam 30 unidades junto
   com o movimento dos robôs. Cada um atinge o primeiro disco que tocar no
   intervalo do tick (ID em empate) e some. O próprio atirador nunca é atingido.
6. Aplica posições/ângulos, custos, regeneração e dano acumulado juntos; publica
   scans e `hit`. Vida zero elimina. VMs com erro são desclassificadas e
   excluídas dos alvos.
7. Incrementa tick e verifica vitória/limite/término.

Scan é omnidirecional até 1000 (a arena inteira, então não há como se esconder).
Escolhe distância mínima e ID estável no empate. A direção é relativa à
orientação no momento do scan e normalizada para [-180,180). O resultado emitido
em um tick só pode ser lido pela VM no seguinte. Permanece armazenado até outro
scan e pode ficar desatualizado.

Tiro cria um projétil na posição e na direção do snapshot inicial; rotação no
mesmo tick não o desvia. Velocidade 30 por tick, alcance máximo 1000, dano
10×potência. Sai da arena, expira. Como o projétil leva vários ticks para chegar
(cerca de 13 a 400 de distância), um alvo que se move pode desviar. Ataques de
robôs que morrerão naquele tick continuam válidos, e projéteis já disparados
continuam voando depois da morte do atirador. Não há dano de colisão. Custos e
danos são simultâneos, sem vantagem por ordem de iteração; há teste com a
lista de robôs invertida.

## Fim da batalha

Restando um ativo, ele vence; restando zero, empate. Se todos os ativos
estiverem com o programa finalizado e não houver projéteis no ar, a batalha
termina antes do limite. No limite (padrão 1000, máximo 100000 ticks) ou nesse
término antecipado vence a maior vida; igualdade é empate.
Não há aleatoriedade, seed é metadado aceito para reprodução futura.
Esses números e mecânicas são decisões do projeto, não imposições do PDF.

## Eventos para animação

O snapshot inclui `projectiles` (id, dono, posição, potência) e `effects`, com
as ações reais do último tick: scan, rotate, fire (origem, ângulo, potência e
id do projétil), hit (atirador, alvo, dano, ponto de impacto e `time`, a fração do tick em que ocorreu), expire e
elimination. São metadados de apresentação; não alteram a ordem das fases ou
as regras de combate. O navegador apenas interpola as posições recebidas.
