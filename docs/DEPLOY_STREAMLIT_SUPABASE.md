# Deploy do IRREAL App Cloud

## Arquitetura

- Interface: Streamlit.
- Hospedagem: Streamlit Community Cloud.
- Banco persistente: Supabase/PostgreSQL.
- Storage de arquivos: Supabase Storage, bucket `deliverables`.
- Envio de e-mail: Resend.
- Segredos: Streamlit Secrets.

## Passo 1 — Supabase

1. Crie um projeto no Supabase.
2. Abra SQL Editor.
3. Execute `sql/schema.sql`.
4. Em Storage, crie um bucket chamado `deliverables`.
5. Copie Project URL e service_role key.

## Passo 2 — Resend

1. Crie conta no Resend.
2. Gere uma API Key.
3. Configure domínio de envio, se for usar e-mail institucional.

## Passo 3 — GitHub

```bash
git init
git add .
git commit -m "IRREAL Cloud Mobile App"
git branch -M main
git remote add origin https://github.com/klebersilva-spec/irreal_cloud_mobile_app.git
git push -u origin main
```

## Passo 4 — Streamlit Community Cloud

1. Crie app a partir do repositório GitHub.
2. Arquivo principal: `app.py`.
3. Em Advanced settings > Secrets, cole as variáveis do arquivo `.streamlit/secrets.example.toml`.

## Passo 5 — Primeiro acesso

No primeiro boot, o app cria automaticamente o usuário de controle geral usando:

- `BOOTSTRAP_ADMIN_FULL_NAME`
- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD`

Depois de entrar, cadastre professores, cursos, turmas e alunos.
