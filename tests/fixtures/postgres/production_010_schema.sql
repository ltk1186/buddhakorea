-- Schema-only snapshot: PostgreSQL 15.15, production revision 010, 2026-09-08.
-- No production rows, credentials, ownership, or grants.



SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA IF NOT EXISTS public;



COMMENT ON SCHEMA public IS 'standard public schema';


SET default_tablespace = '';

SET default_table_access_method = heap;


CREATE TABLE public.admin_audit_logs (
    id integer NOT NULL,
    admin_user_id integer,
    action character varying(100) NOT NULL,
    target_type character varying(50) NOT NULL,
    target_id character varying(100),
    before_state json,
    after_state json,
    context json,
    ip_hash character varying(64),
    user_agent character varying(255),
    created_at timestamp with time zone NOT NULL
);



CREATE SEQUENCE public.admin_audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.admin_audit_logs_id_seq OWNED BY public.admin_audit_logs.id;



CREATE TABLE public.admin_query_reviews (
    id integer NOT NULL,
    message_id integer NOT NULL,
    status character varying(20) NOT NULL,
    reason character varying(50),
    note text,
    created_by_admin_id integer,
    updated_by_admin_id integer,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);



CREATE SEQUENCE public.admin_query_reviews_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.admin_query_reviews_id_seq OWNED BY public.admin_query_reviews.id;



CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);



CREATE TABLE public.anonymous_usage (
    id integer NOT NULL,
    ip_hash character varying(64) NOT NULL,
    usage_date date NOT NULL,
    chat_count integer,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);



CREATE SEQUENCE public.anonymous_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.anonymous_usage_id_seq OWNED BY public.anonymous_usage.id;



CREATE TABLE public.chat_messages (
    id integer NOT NULL,
    session_id integer NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    model_used character varying(50),
    sources_count integer,
    response_mode character varying(20),
    created_at timestamp without time zone,
    tokens_used integer,
    latency_ms integer,
    sources_json jsonb,
    trace_json jsonb
);



CREATE SEQUENCE public.chat_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.chat_messages_id_seq OWNED BY public.chat_messages.id;



CREATE TABLE public.chat_sessions (
    id integer NOT NULL,
    session_uuid character varying(36),
    user_id integer,
    title character varying(200),
    created_at timestamp without time zone,
    last_message_at timestamp without time zone,
    is_active boolean,
    summary text,
    is_archived boolean DEFAULT false,
    message_count integer DEFAULT 0,
    deleted_at timestamp without time zone
);



CREATE SEQUENCE public.chat_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.chat_sessions_id_seq OWNED BY public.chat_sessions.id;



CREATE TABLE public.literatures (
    id character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    pali_name character varying(255) NOT NULL,
    pitaka character varying(50) NOT NULL,
    nikaya character varying(100),
    status character varying(20),
    total_segments integer,
    translated_segments integer,
    source_pdf character varying(255),
    hierarchy_labels jsonb,
    display_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);



CREATE TABLE public.query_logs (
    id integer NOT NULL,
    session_id character varying(100),
    literature_id character varying(100),
    segment_id integer,
    question text NOT NULL,
    answer text,
    model character varying(50),
    tokens_used integer,
    created_at timestamp without time zone
);



CREATE SEQUENCE public.query_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.query_logs_id_seq OWNED BY public.query_logs.id;



CREATE TABLE public.saved_exchanges (
    id integer NOT NULL,
    user_id integer NOT NULL,
    question text NOT NULL,
    answer text NOT NULL,
    sources_json json,
    model_used character varying(50),
    response_mode character varying(20),
    created_at timestamp with time zone
);



CREATE SEQUENCE public.saved_exchanges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.saved_exchanges_id_seq OWNED BY public.saved_exchanges.id;



CREATE TABLE public.segments (
    id integer NOT NULL,
    literature_id character varying(100) NOT NULL,
    vagga_id integer,
    vagga_name character varying(255),
    sutta_id integer,
    sutta_name character varying(255),
    page_number integer,
    paragraph_id integer NOT NULL,
    original_text text NOT NULL,
    translation jsonb,
    is_translated boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);



CREATE SEQUENCE public.segments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.segments_id_seq OWNED BY public.segments.id;



CREATE TABLE public.social_accounts (
    id integer NOT NULL,
    user_id integer NOT NULL,
    provider character varying(20) NOT NULL,
    provider_user_id character varying(255) NOT NULL,
    provider_email character varying(255),
    access_token text,
    refresh_token text,
    token_expires_at timestamp with time zone,
    raw_profile json,
    created_at timestamp with time zone,
    last_used_at timestamp with time zone,
    access_token_encrypted text,
    refresh_token_encrypted text
);



CREATE SEQUENCE public.social_accounts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.social_accounts_id_seq OWNED BY public.social_accounts.id;



CREATE TABLE public.user_usage (
    id integer NOT NULL,
    user_id integer NOT NULL,
    usage_date date NOT NULL,
    chat_count integer,
    tokens_used integer,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);



CREATE SEQUENCE public.user_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.user_usage_id_seq OWNED BY public.user_usage.id;



CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying,
    nickname character varying,
    provider character varying,
    social_id character varying,
    profile_img character varying,
    created_at timestamp without time zone,
    last_login timestamp without time zone,
    role character varying(20) DEFAULT 'user'::character varying,
    is_active boolean DEFAULT true,
    daily_chat_limit integer DEFAULT 50,
    updated_at timestamp without time zone
);



CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;



ALTER TABLE ONLY public.admin_audit_logs ALTER COLUMN id SET DEFAULT nextval('public.admin_audit_logs_id_seq'::regclass);



ALTER TABLE ONLY public.admin_query_reviews ALTER COLUMN id SET DEFAULT nextval('public.admin_query_reviews_id_seq'::regclass);



ALTER TABLE ONLY public.anonymous_usage ALTER COLUMN id SET DEFAULT nextval('public.anonymous_usage_id_seq'::regclass);



ALTER TABLE ONLY public.chat_messages ALTER COLUMN id SET DEFAULT nextval('public.chat_messages_id_seq'::regclass);



ALTER TABLE ONLY public.chat_sessions ALTER COLUMN id SET DEFAULT nextval('public.chat_sessions_id_seq'::regclass);



ALTER TABLE ONLY public.query_logs ALTER COLUMN id SET DEFAULT nextval('public.query_logs_id_seq'::regclass);



ALTER TABLE ONLY public.saved_exchanges ALTER COLUMN id SET DEFAULT nextval('public.saved_exchanges_id_seq'::regclass);



ALTER TABLE ONLY public.segments ALTER COLUMN id SET DEFAULT nextval('public.segments_id_seq'::regclass);



ALTER TABLE ONLY public.social_accounts ALTER COLUMN id SET DEFAULT nextval('public.social_accounts_id_seq'::regclass);



ALTER TABLE ONLY public.user_usage ALTER COLUMN id SET DEFAULT nextval('public.user_usage_id_seq'::regclass);



ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);



ALTER TABLE ONLY public.admin_audit_logs
    ADD CONSTRAINT admin_audit_logs_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.admin_query_reviews
    ADD CONSTRAINT admin_query_reviews_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);



ALTER TABLE ONLY public.anonymous_usage
    ADD CONSTRAINT anonymous_usage_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.literatures
    ADD CONSTRAINT literatures_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.query_logs
    ADD CONSTRAINT query_logs_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.saved_exchanges
    ADD CONSTRAINT saved_exchanges_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.segments
    ADD CONSTRAINT segments_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT social_accounts_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.anonymous_usage
    ADD CONSTRAINT uq_anon_ip_date UNIQUE (ip_hash, usage_date);



ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT uq_provider_user_id UNIQUE (provider, provider_user_id);



ALTER TABLE ONLY public.segments
    ADD CONSTRAINT uq_segment_location UNIQUE (literature_id, vagga_id, sutta_id, paragraph_id);



ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT uq_user_provider UNIQUE (user_id, provider);



ALTER TABLE ONLY public.user_usage
    ADD CONSTRAINT uq_user_usage_date UNIQUE (user_id, usage_date);



ALTER TABLE ONLY public.user_usage
    ADD CONSTRAINT user_usage_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);



CREATE INDEX idx_admin_audit_logs_action ON public.admin_audit_logs USING btree (action);



CREATE INDEX idx_admin_audit_logs_admin_user_id ON public.admin_audit_logs USING btree (admin_user_id);



CREATE INDEX idx_query_logs_created ON public.query_logs USING btree (created_at);



CREATE INDEX idx_query_logs_session ON public.query_logs USING btree (session_id);



CREATE INDEX idx_segments_literature ON public.segments USING btree (literature_id);



CREATE INDEX idx_segments_location ON public.segments USING btree (literature_id, vagga_id, sutta_id);



CREATE INDEX idx_segments_page ON public.segments USING btree (literature_id, page_number);



CREATE INDEX idx_segments_translated ON public.segments USING btree (is_translated);



CREATE INDEX ix_admin_query_reviews_id ON public.admin_query_reviews USING btree (id);



CREATE UNIQUE INDEX ix_admin_query_reviews_message_id ON public.admin_query_reviews USING btree (message_id);



CREATE INDEX ix_anonymous_usage_id ON public.anonymous_usage USING btree (id);



CREATE INDEX ix_anonymous_usage_ip_hash ON public.anonymous_usage USING btree (ip_hash);



CREATE INDEX ix_chat_messages_id ON public.chat_messages USING btree (id);



CREATE INDEX ix_chat_messages_session_id ON public.chat_messages USING btree (session_id);



CREATE INDEX ix_chat_sessions_id ON public.chat_sessions USING btree (id);



CREATE UNIQUE INDEX ix_chat_sessions_session_uuid ON public.chat_sessions USING btree (session_uuid);



CREATE INDEX ix_chat_sessions_user_id ON public.chat_sessions USING btree (user_id);



CREATE INDEX ix_saved_exchanges_id ON public.saved_exchanges USING btree (id);



CREATE INDEX ix_saved_exchanges_user_id ON public.saved_exchanges USING btree (user_id);



CREATE INDEX ix_social_accounts_id ON public.social_accounts USING btree (id);



CREATE INDEX ix_social_accounts_user_id ON public.social_accounts USING btree (user_id);



CREATE INDEX ix_user_usage_id ON public.user_usage USING btree (id);



CREATE INDEX ix_user_usage_user_id ON public.user_usage USING btree (user_id);



CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);



CREATE INDEX ix_users_id ON public.users USING btree (id);



CREATE INDEX ix_users_social_id ON public.users USING btree (social_id);



ALTER TABLE ONLY public.admin_audit_logs
    ADD CONSTRAINT admin_audit_logs_admin_user_id_fkey FOREIGN KEY (admin_user_id) REFERENCES public.users(id) ON DELETE SET NULL;



ALTER TABLE ONLY public.admin_query_reviews
    ADD CONSTRAINT admin_query_reviews_created_by_admin_id_fkey FOREIGN KEY (created_by_admin_id) REFERENCES public.users(id) ON DELETE SET NULL;



ALTER TABLE ONLY public.admin_query_reviews
    ADD CONSTRAINT admin_query_reviews_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.chat_messages(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.admin_query_reviews
    ADD CONSTRAINT admin_query_reviews_updated_by_admin_id_fkey FOREIGN KEY (updated_by_admin_id) REFERENCES public.users(id) ON DELETE SET NULL;



ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id);



ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);



ALTER TABLE ONLY public.query_logs
    ADD CONSTRAINT query_logs_literature_id_fkey FOREIGN KEY (literature_id) REFERENCES public.literatures(id) ON DELETE SET NULL;



ALTER TABLE ONLY public.saved_exchanges
    ADD CONSTRAINT saved_exchanges_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.segments
    ADD CONSTRAINT segments_literature_id_fkey FOREIGN KEY (literature_id) REFERENCES public.literatures(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.social_accounts
    ADD CONSTRAINT social_accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.user_usage
    ADD CONSTRAINT user_usage_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;




