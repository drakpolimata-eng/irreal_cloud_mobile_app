
-- IRREAL App - Migração V1 para V2: desafios e atividades por turma/aluno.
-- Execute no Supabase SQL Editor se o banco V1 já existe.

create table if not exists challenges (
    id uuid primary key default uuid_generate_v4(),
    class_id uuid not null references classes(id) on delete cascade,
    unit_id uuid references curricular_units(id) on delete set null,
    mission_id uuid references missions(id) on delete set null,
    created_by uuid references app_users(id) on delete set null,
    title text not null,
    challenge_type text not null default 'atividade' check (challenge_type in ('desafio', 'atividade', 'missao_extra', 'diagnostico', 'recuperacao')),
    difficulty text not null default 'basico' check (difficulty in ('basico', 'intermediario', 'avancado', 'mestre')),
    target_scope text not null default 'turma' check (target_scope in ('turma', 'aluno')),
    target_student_id uuid references app_users(id) on delete cascade,
    description text default '',
    instructions text default '',
    expected_deliverable text default '',
    max_irreais integer not null default 100,
    penalty_irreais integer not null default 0,
    deadline_at timestamptz,
    active boolean not null default true,
    removed_at timestamptz,
    removed_by uuid references app_users(id) on delete set null,
    created_at timestamptz not null default now()
);

create index if not exists idx_challenges_class_active on challenges(class_id, active);
create index if not exists idx_challenges_target_student on challenges(target_student_id);
create index if not exists idx_challenges_difficulty on challenges(difficulty);

create table if not exists challenge_events (
    id uuid primary key default uuid_generate_v4(),
    challenge_id uuid not null references challenges(id) on delete cascade,
    actor_id uuid references app_users(id) on delete set null,
    event_type text not null check (event_type in ('created', 'updated', 'removed', 'reactivated')),
    notes text default '',
    created_at timestamptz not null default now()
);

alter table deliverables
add column if not exists challenge_id uuid references challenges(id) on delete set null;
