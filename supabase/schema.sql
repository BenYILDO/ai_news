create extension if not exists pgcrypto;

create table if not exists articles (
  id uuid primary key default gen_random_uuid(),
  url text not null unique,
  title text not null,
  summary text,
  source text not null,
  category text not null,
  published_at timestamptz,
  collected_at timestamptz not null default now(),
  score numeric not null default 0,
  telegram_message_id bigint
);

create table if not exists feedback (
  id uuid primary key default gen_random_uuid(),
  article_id uuid not null references articles(id) on delete cascade,
  choice text not null check (choice in ('like','skip','linkedin')),
  created_at timestamptz not null default now(),
  unique(article_id, choice)
);

create table if not exists bot_state (
  key text primary key,
  value text not null,
  updated_at timestamptz not null default now()
);

alter table articles enable row level security;
alter table feedback enable row level security;
alter table bot_state enable row level security;

