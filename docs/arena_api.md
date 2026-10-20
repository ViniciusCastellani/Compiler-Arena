# API e arena

| Comando | Argumento | Intervalo | Custo |
|---|---|---|---|
| move | int/float | 0..100 | 1 |
| back | int/float | 0..100 | 1 |
| rotate | int/float | -360..360 | 1 |
| scan | nenhum | — | 1 |
| fire | int | 1..3 | 2×potência |

Não retornam valores, logo não são expressões. Validação de constantes é
estática e de valores dinâmicos ocorre na VM. Não há truncamento/clamp de
argumentos. Custos são inteiros mesmo para movimento/ângulo float.

Sensores: energy:int, position.x/y:float, enemy.visible:bool,
enemy.distance/direction:float. São somente leitura. energy/position leem o
snapshot inicial do tick. enemy lê o último scan, nunca executa uma busca.
Antes do primeiro scan ou sem alvo: false, -1.0, 0.0.

Arena 800×600, x para direita e y para cima. A renderização inverte y apenas
para desenhar. Raio físico 12, energia inicial 100, posições em círculo de
raio 200 ao redor (400,300), direções iniciais para o centro. Entre 2 e 16
robôs, condições simétricas. Ângulos positivos anti-horários, 0° direita.

A cada tick:
1. Captura as posições/direções/energia de todos os ativos.
2. Executa cada VM com esse estado e coleta até um comando.
3. Cobra custo de comandos executáveis; planeja movimentos/rotações e calcula
   scans/tiros no estado inicial. Falha por energia insuficiente consome o
   comando e não tem efeito nem custo parcial. Não recarrega energia.
4. Cancela movimentos fora das paredes. Colisões consideram a distância
   mínima entre as trajetórias simultâneas. Ambos param na posição inicial;
   repete até ponto fixo para considerar um robô que acabou de parar.
5. Aplica posições/ângulos, custos e dano acumulado juntos; publica scans.
   Energia zero elimina. VMs com erro são desclassificadas e excluídas dos alvos.
6. Incrementa tick e verifica vitória/limite.

Scan é omnidirecional até 500. Escolhe distância mínima e ID estável no
empate. A direção é relativa à orientação no momento do scan e normalizada
para [-180,180). O resultado emitido em um tick só pode ser lido pela VM
no seguinte. Permanece armazenado até outro scan e pode ficar desatualizado.

Tiro é hitscan (instantâneo) em raio de 500: intercepta discos de raio 12
no snapshot inicial, escolhe a primeira interseção positiva (ID em empate),
causa 10×potência de dano. Movimento/rotação no mesmo tick não desvia esse tiro.
Ataques de robôs que morrerão naquele tick continuam válidos. Não há projéteis
persistentes ou dano de colisão. Custos e danos são simultâneos, sem vantagem
por ordem de iteração; há teste com a lista de robôs invertida.

Restando um ativo, ele vence; restando zero, empate. Todos os ativos são
elegíveis, inclusive programas finalizados. No limite (padrão 1000, máximo
100000 ticks) vence a maior energia; igualdade é empate. Uma batalha em que
todos os programas terminam ainda avança até o limite, pois término não é morte.
Não há aleatoriedade, seed é metadado aceito para reprodução futura.
Esses números e mecânicas são decisões do projeto, não imposições do PDF.

## Eventos para animação
O snapshot inclui `effects`, com as ações reais do último tick: scan, rotate,
fire (origem, fim, potência, alvo e dano) e elimination. São metadados de
apresentação; não alteram a ordem das fases ou as regras de combate. O tiro
continua instantâneo na simulação; o projétil desenhado é um efeito visual.
