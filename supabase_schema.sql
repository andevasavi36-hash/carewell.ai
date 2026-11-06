-- Supabase -> SQL Editor lo run cheyyi

create table if not exists appointments (
  id uuid primary key default gen_random_uuid(),
  patient_name text not null,
  phone text not null,
  email text,
  department text not null,
  doctor text not null,
  appointment_date date not null,
  appointment_time text not null,
  reason text,
  status text not null default 'Pending',
  created_at timestamptz not null default now()
);

create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  appointment_id text,
  kind text not null,
  content text not null,
  created_at timestamptz not null default now()
);

-- Demo kosam RLS disable (production lo proper policies pettali)
alter table appointments disable row level security;
alter table messages disable row level security;
