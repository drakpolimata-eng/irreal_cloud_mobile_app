# Atualização V2 — Desafios e atividades por turma/aluno

## Objetivo

Permitir que docentes publiquem e retirem desafios ou atividades:

- para a turma inteira;
- para um aluno específico;
- com nível de dificuldade;
- com prazo;
- com IRREAIS ajustados por dificuldade;
- com entregável esperado.

## Níveis de dificuldade

| Nível | Multiplicador sugerido |
|---|---:|
| Básico | 1.00x |
| Intermediário | 1.25x |
| Avançado | 1.50x |
| Desafio Mestre | 2.00x |

## Tipos disponíveis

- Atividade;
- Desafio;
- Missão extra;
- Diagnóstico;
- Recuperação.

## Retirada de desafio

O desafio não é apagado fisicamente. Ele é marcado como inativo:

```text
active = false
removed_at = data/hora
removed_by = usuário
```

Isso preserva rastreabilidade pedagógica.

## Como aplicar em banco existente

Execute no Supabase SQL Editor:

```text
sql/migration_v1_to_v2_challenges.sql
```
