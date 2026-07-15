-- Migration: 001_initial_schema.sql
-- Creates all 4 core LexFlow tables

CREATE TABLE IF NOT EXISTS clienti (
    id SERIAL PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'admin',
    nome TEXT NOT NULL,
    email TEXT,
    telefono TEXT,
    azienda TEXT,
    status TEXT DEFAULT 'lead',
    tags TEXT[],
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pratiche (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clienti(id) ON DELETE RESTRICT,
    owner_id TEXT NOT NULL DEFAULT 'admin',
    titolo TEXT NOT NULL,
    valore_stimato NUMERIC,
    fase TEXT DEFAULT 'nuovo_incarico',
    scadenza DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attivita (
    id SERIAL PRIMARY KEY,
    pratica_id INTEGER REFERENCES pratiche(id) ON DELETE CASCADE,
    client_id INTEGER REFERENCES clienti(id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL DEFAULT 'admin',
    tipo TEXT NOT NULL,
    descrizione TEXT,
    data_attivita TIMESTAMPTZ DEFAULT now(),
    completata BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS registro (
    id SERIAL PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'admin',
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    azione TEXT NOT NULL,
    dettagli JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
