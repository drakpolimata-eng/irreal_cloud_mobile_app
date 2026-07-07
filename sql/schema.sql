-- IRREAL App Cloud Schema
-- Execute este arquivo no SQL Editor do Supabase.

create extension if not exists "uuid-ossp";

create table if not exists app_users (
    id uuid primary key default uuid_generate_v4(),
    full_name text not null,
    email text,
    role text not null check (role in ('super_admin', 'professor', 'student')),
    password_hash text not null,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    created_by uuid references app_users(id)
);

create unique index if not exists idx_app_users_email_unique
on app_users(lower(email))
where email is not null and email <> '';

create index if not exists idx_app_users_full_name
on app_users(lower(full_name));

create table if not exists courses (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    description text default '',
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists classes (
    id uuid primary key default uuid_generate_v4(),
    course_id uuid references courses(id) on delete set null,
    professor_id uuid references app_users(id) on delete set null,
    name text not null,
    shift text not null default '',
    class_code text not null unique,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists enrollments (
    id uuid primary key default uuid_generate_v4(),
    class_id uuid not null references classes(id) on delete cascade,
    student_id uuid not null references app_users(id) on delete cascade,
    team_name text default '',
    active boolean not null default true,
    created_at timestamptz not null default now(),
    unique(class_id, student_id)
);

create table if not exists curricular_units (
    id uuid primary key default uuid_generate_v4(),
    class_id uuid references classes(id) on delete cascade,
    name text not null,
    workload_hours integer default 0,
    description text default '',
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists missions (
    id uuid primary key default uuid_generate_v4(),
    class_id uuid references classes(id) on delete cascade,
    unit_id uuid references curricular_units(id) on delete set null,
    title text not null,
    description text default '',
    max_irreais integer not null default 100,
    deadline_at timestamptz,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists leaders (
    id uuid primary key default uuid_generate_v4(),
    class_id uuid not null references classes(id) on delete cascade,
    class_date date not null,
    student_id uuid not null references app_users(id) on delete cascade,
    notes text default '',
    created_at timestamptz not null default now()
);

create table if not exists transactions (
    id uuid primary key default uuid_generate_v4(),
    class_id uuid references classes(id) on delete cascade,
    student_id uuid references app_users(id) on delete set null,
    team_name text default '',
    amount integer not null,
    reason text not null,
    reference_type text default '',
    reference_id uuid,
    created_at timestamptz not null default now()
);

create table if not exists store_items (
    id uuid primary key default uuid_generate_v4(),
    class_id uuid references classes(id) on delete cascade,
    name text not null,
    cost integer not null,
    description text default '',
    max_per_student integer default 0,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists purchases (
    id uuid primary key default uuid_generate_v4(),
    class_id uuid references classes(id) on delete cascade,
    student_id uuid references app_users(id) on delete cascade,
    item_id uuid references store_items(id) on delete set null,
    cost integer not null,
    notes text default '',
    created_at timestamptz not null default now()
);

create table if not exists deliverables (
    id uuid primary key default uuid_generate_v4(),
    class_id uuid not null references classes(id) on delete cascade,
    mission_id uuid references missions(id) on delete set null,
    student_id uuid not null references app_users(id) on delete cascade,
    title text not null,
    description text default '',
    external_link text default '',
    file_name text default '',
    file_path text default '',
    sent_to_email text default '',
    email_status text default 'pending',
    teacher_feedback text default '',
    created_at timestamptz not null default now()
);

-- Opcional: crie manualmente um bucket chamado "deliverables" no Supabase Storage.
-- O MVP também aceita entregável como texto/link sem arquivo.


-- V2: desafios e atividades

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
