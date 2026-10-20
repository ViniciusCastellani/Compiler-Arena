# Apresentação editável

- `apresentacao_compiler_arena.pptx`: 18 slides 16:9; textos, formas e diagramas
  editáveis; notas do apresentador em todos os slides. Campos institucionais
  devem ser preenchidos pela equipe.
- `apresentacao_compiler_arena.pdf`: versão de consulta, com páginas raster.
- `gerar_apresentacao.py`: geração reproduzível com python-pptx e Pillow.
- `capturas/`: capturas reais da aplicação executada em Chromium headless.
- `previas/slide_01.png` a `slide_18.png`: renderizações para revisão.
- `previas/contato.png`: visão geral dos slides.
- `revisao.txt`: checagem geométrica de cortes e sobreposições de texto.
- `dados_slides.json`: fonte/hash, métricas, resultado da suíte e batalha usados.

Na raiz do projeto:

```bash
python -m pip install -r requirements.txt -r apresentacao/requirements.txt
python -m pip install -r ferramentas/requirements-testes.txt
python -m playwright install chromium
python -m unittest discover -s tests -v > artefatos/testes.txt 2>&1
python ferramentas/verificar_web.py
python apresentacao/gerar_apresentacao.py
```

Os trechos de tokens, AST, símbolos, IR e bytecode são extraídos do compilador
real para Alpha. O exemplo isolado de otimização fornece uma métrica adicional.
Resultados de teste são lidos do arquivo real, e a batalha Alpha/Beta é executada
pelo gerador. Não há valores fictícios de cobertura ou desempenho.

## Revisão e limite de renderização

Não havia LibreOffice/PowerPoint disponível como conversor neste ambiente.
O script relê os objetos do PPTX salvo e renderiza as formas, textos e imagens
usados neste tema via Pillow. O PDF é gerado dessas páginas, com o conteúdo
visual correspondente; é raster e não possui texto selecionável. Não se afirma
que tenha sido exportado por um motor Office. As prévias foram inspecionadas,
e as caixas foram medidas para verificar cortes e sobreposições. Como o motor
PowerPoint pode diferir em métricas de fonte, abra o PPTX no computador da defesa
e confirme a fonte DejaVu Sans/DejaVu Sans Mono ou substitua por fontes locais.
O PPTX permanece editável, inclusive os diagramas. As capturas são imagens,
como esperado. O roteiro completo está em `docs/defesa_demonstracao.md`.
