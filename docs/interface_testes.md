# Interface HTML e validação

`python main.py web` inicia o servidor local em `http://127.0.0.1:8000` e abre
uma aba do navegador. `--no-browser` apenas inicia o servidor; `--port 8080`
altera a porta. `python main.py gui` é um alias de compatibilidade para a mesma
interface HTML. Não é necessário instalar Tkinter, Pygame, Node ou npm.
A página precisa desse servidor Python; abrir index.html diretamente não
executa o compilador.

A interface em `compiler_arena/web/` usa HTML, CSS e JavaScript locais, sem CDN.
O servidor em `web_server.py` usa apenas biblioteca padrão. A mudança de Tkinter
para HTML foi solicitada pelo usuário depois da primeira entrega. A CLI e o
núcleo de compilação/VM/arena foram preservados.

## Editor e relatórios

Novo/Abrir/Exemplos avisam antes de descartar texto não salvo. Salvar baixa o
arquivo UTF-8 pelo navegador; não sobrescreve automaticamente um arquivo do
disco. O título e o nome do arquivo indicam alterações. Há numeração de linhas,
rolagem e navegação para a linha ao clicar em um diagnóstico. Tab insere quatro
espaços; Ctrl+S baixa o fonte. O navegador avisa ao sair com alterações.

Compilar envia texto e opção de otimização à API Python. A resposta pertence à
revisão exata enviada: editar texto/opção invalida os resultados e uma resposta
antiga é descartada. Abas: tokens, AST expansível, símbolos, diagnósticos, duas
IRs, log de otimizações e bytecode. Estados das etapas distinguem concluída,
erro, não executada e otimização desativada (detalhe no título de cada etapa).
O relatório JSON inclui fonte, SHA-256, todas as representações e estados.
O bytecode possui download próprio. Não há fases simuladas no JavaScript.

## Batalha

Compile Alpha e adicione à lista. Abra Beta, compile e adicione. Marque ambos,
defina limite/orçamento e clique em Preparar batalha. A arena é desenhada no
canvas HTML; Iniciar, Pausar, Um tick e Reiniciar controlam a mesma instância
Python via HTTP. Velocidade altera a frequência de requisições, não a lógica.
Não há ticks sobrepostos: cada requisição e sua animação terminam antes da
próxima. A velocidade inicial é 1 tick/s (antes 10); o controle vai de
0,5 a 10 ticks/s. Ao pausar,
um tick já em trânsito e sua transição visual podem concluir; nenhum outro
é agendado. Um tick manual também reproduz as animações.

Cada aba do navegador tem uma sessão isolada. O servidor guarda PC, memória,
energia e logs. O cliente desenha os snapshots e nunca calcula dano/colisões.
A lista de robôs adicionados representa compilações congeladas com hash.
Carregar bytecode valida JSON no Python, antes de adicioná-lo. Exportar batalha
baixa todos os logs e o snapshot; a página mostra os 12 eventos mais recentes.
Fechar a aba libera a sessão por uma mensagem; Ctrl+C encerra o servidor.
O serviço escuta apenas em 127.0.0.1 e verifica Host/Origin. Limite: 32 sessões
por processo. Downloads grandes preservam inteiros de até 4096 bits por uma
codificação de transporte explícita; floats também preservam o tipo (450.0
não vira int). O JSON exportado contém números normais.

## Testes

`python -m unittest discover -s tests -v` testa o núcleo e a API HTTP local:
compilação, carregamento, estados de batalha, reinício, logs, isolamento de
sessões, rejeição de origem externa e transporte de inteiros grandes.
Resultados reais em `artefatos/testes.txt`.

Para validar o navegador e gerar capturas:

```bash
python -m pip install -r ferramentas/requirements-testes.txt
python -m playwright install chromium
python ferramentas/verificar_web.py
```

O teste usa Chromium headless, sem DISPLAY/Xvfb. Exercita o fluxo real de
compilar, inspecionar, adicionar dois robôs, pausar, avançar, reiniciar, vencer,
baixar bytecode/logs, rejeitar programa inválido, descartar resposta antiga,
preservar inteiros e conferir layout móvel. Capturas reais estão em
`apresentacao/capturas/` e o resultado em `artefatos/teste_web.txt`.

## Animações da arena

`arena_renderer.js` interpola posições e orientações entre snapshots com
requestAnimationFrame e suavização. Movimentos têm rastros e esteiras; rotação
usa o ângulo emitido pelo servidor, incluindo voltas completas. Scan exibe um
pulso, tiro tem clarão e projétil, acerto tem partículas e indicação do dano,
e eliminação tem uma expansão que desaparece. Não há sorteio nos efeitos.

A duração acompanha o controle de velocidade, sem mudar orçamento, energia,
dano ou colisões. O servidor informa em `snapshot.effects` os tiros realmente
executados, ponto de impacto, alvo e dano, além de scans, rotações e eliminações.
O navegador não escolhe alvos. Tiros sem energia não recebem efeito de disparo;
tiros que erram não exibem dano. Ao reiniciar ou preparar outra batalha, a
animação anterior é limpa. Não há loop de renderização permanente em repouso.
A preferência de movimento reduzido evita deslocamentos e partículas, mantendo
a cadência dos ticks e a informação textual de ações/resultado.
