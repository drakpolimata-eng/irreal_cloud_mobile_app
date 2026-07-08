# Atualização da imagem inicial do IRREAL App

## Arquivo principal

Use este arquivo como nova imagem da frente/splash do app:

`irreal_splash_professora.png`

## Onde colocar no GitHub

No repositório:

`drakpolimata-eng/irreal_cloud_mobile_app`

envie o arquivo para a pasta:

`assets/`

Caminho final recomendado:

`assets/irreal_splash_professora.png`

## Ajuste no código

Procure no projeto pelo arquivo que mostra a imagem inicial. Normalmente estará em:

`irreal_auth.py`

ou no início do:

`app.py`

Procure por uma linha parecida com:

```python
st.image("assets/ALGUMA_IMAGEM.png", use_container_width=True)
```

ou:

```python
st.image("assets/ALGUMA_IMAGEM.png")
```

Substitua o nome da imagem por:

```python
st.image("assets/irreal_splash_professora.png", use_container_width=True)
```

Se o Streamlit mostrar aviso sobre `use_container_width`, use:

```python
st.image("assets/irreal_splash_professora.png", width="stretch")
```

## Depois de alterar

1. Faça commit no GitHub.
2. Aguarde o Streamlit atualizar automaticamente.
3. Se não atualizar, faça:
   - Streamlit
   - Manage app
   - Reboot app

## Observação

Como a permissão de escrita do GitHub via ChatGPT ainda retornou `403 Resource not accessible by integration`, esta alteração precisa ser enviada manualmente ou via Codex com permissão de escrita.
