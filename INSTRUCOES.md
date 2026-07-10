# IRREAL App V8.2.2 — correção de estabilidade e campos

## Correção principal

O log mostrou que o Streamlit estava rodando com Python 3.14.6 e terminou com `Segmentation fault`.
Esta versão adiciona:

- `runtime.txt` com `python-3.12`;
- `.python-version` com `3.12`;
- `requirements.txt` fixado;
- `app.py` com `width="stretch"` no lugar de `use_container_width=True`;
- correção do ranking de IRREAIS usando relação explícita com `transactions_student_id_fkey`.

## Como aplicar no GitHub

Substitua/adicione estes arquivos na raiz do repositório:

- `app.py`
- `runtime.txt`
- `.python-version`
- `requirements.txt`

Depois faça commit e no Streamlit execute **Reboot app**.

## Resultado esperado nos logs

Depois do reboot, o log deve mostrar Python 3.12 em vez de Python 3.14.6.
