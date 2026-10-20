# Demonstração reproduzível (8–12 minutos)

1. `python main.py web`. Selecione alpha.robo e compile.
2. Mostre Tokens: `int distancia = 10 + 20`. Abra a AST expansível.
3. Mostre Símbolos: distancia possui tipo int, escopo e identidade 0.
4. Troque `fire(3)` por `fire(true)` e compile. A semântica bloqueia bytecode.
   Tente Adicionar à batalha para demonstrar a rejeição.
5. Corrija para 3 e compile. Mostre SHA, estados e diagnósticos vazios.
6. Compare as duas IRs: 10+20 dobra para 30 e +0 é simplificado/propagado.
   Abra Otimizações para as entradas reais do log.
7. Mostre Bytecode: índices, registradores e saltos numéricos.
8. Adicione Alpha. Abra beta.robo, compile, adicione. Marque os dois.
9. Defina limite 300, orçamento 100, prepare a batalha. Inicie, pause e dê Um tick.
10. Mostre energy e VM separadamente. Inicie até o vencedor/empate.
11. Exporte o estado. Mostre que uma VM finalizada ainda é alvo.
12. Explique uma limitação: scans são armazenados e podem ficar desatualizados;
    otimização pode mudar o tick das ações pelo orçamento de instruções.

## Perguntas e respostas para defesa

**Por que não executar a AST?** A disciplina exige transformação real: a AST
anotada gera quádruplas, depois um formato de registradores. A VM importa apenas
o loader e regras de valores; nem conhece a AST.

**O que reaproveitaram?** Cursor/scanners/tokens do lexer e estruturas, helpers,
limites, erros e exportação do parser. As regras evoluíram da mini-linguagem
anterior para RoboLang. Semântica e backend são novos.

**Como escopo não mistura variáveis iguais?** Nomes são resolvidos de dentro
para fora na semântica; cada declaração ganha ID. Dois x possuem dois IDs,
operandos symbol diferentes e registradores diferentes. Não se usa dict por
nome durante a execução.

**Por que x do inicializador pode ser externo?** O novo símbolo ainda não foi
inserido. A resolução usa o escopo atual sem ele e sobe aos externos.

**Como while vira execução?** Rótulo antes da condição, cálculo, salto falso
para fim e salto do corpo ao início. O gerador remove rótulos e resolve PCs.

**Como curto-circuito funciona?** JZ/JNZ pula a IR da direita. A semântica ainda
valida nomes e tipos dessa direita, mas não calcula operações constantes ali
quando a esquerda prova que ela será descartada.

**O que garante a otimização?** Transformações locais conservadoras. Não cruza
ramos/laços sem análise de fluxo, não trata sensores como constantes e preserva
operações que podem falhar. Testes com entradas controladas comparam ações e
erros. Isso não garante a mesma cronologia da batalha com orçamento pequeno.

**Como impedir loop infinito?** Todo opcode gasta orçamento; a VM pausa por
tick. Toda batalha tem limite total. O navegador desenha snapshots; o servidor Python limita cada chamada de passo.

**O que há de justo?** Todos leem o mesmo início de tick; movimentos, custos
e tiros são resolvidos simultaneamente. Inverter a lista de execução não muda
o resultado físico. IDs desempatarão alvos, regra determinística documentada.

**Como detectar um bytecode adulterado?** Validação estrutural/tipos/opcodes e
limites no loader. Argumentos dependentes da execução são verificados pela VM.
Não há pickle, imports ou comandos do sistema na linguagem.

## Pequenas alterações ao vivo
- Troque fire(3) por fire(4): erro estático e bloqueio.
- Faça int p=4; fire(p): compila e falha na VM, preservando erro observável.
- Adicione `{ int distancia=2; move(distancia); }`: mostre IDs distintos.
- Troque budget para 1: observe preservação de PC e ausência de travamento.
- Ajuste dano 10×potência em arena.py: explique por que isso não muda a gramática.
