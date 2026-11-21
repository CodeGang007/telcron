-- migrate:up
-- WO-015: vectors for products and evidence, and the product assistant's conversations.
-- These tables are phase 2 in docs/database/schema_spec.py, so a fresh database gets them from
-- db/schema-next/phase2_schema.sql (+ phase2_rules.sql). A database where phase 2 was applied before
-- they existed (the dev environment) gets the same statements here, copied from the generated file.
-- On a fresh database this runs before phase 2 and does nothing.
DO $$
BEGIN
    IF to_regclass('embedding_models') IS NOT NULL AND to_regclass('product_embeddings') IS NULL THEN
        CREATE TABLE product_embeddings (
            product_id uuid NOT NULL,
            model_code text NOT NULL,
            content_sha256 bytea NOT NULL,
            embedding vector NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT product_embeddings_pkey PRIMARY KEY (product_id, model_code)
        );
        COMMENT ON TABLE product_embeddings IS 'Semantic vector of a product''s identity and known safety facts, per model.';
        COMMENT ON COLUMN product_embeddings.content_sha256 IS 're-embed only when the text changes';
        CREATE TABLE evidence_embeddings (
            evidence_id uuid NOT NULL,
            model_code text NOT NULL,
            embedding vector NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT evidence_embeddings_pkey PRIMARY KEY (evidence_id, model_code)
        );
        COMMENT ON TABLE evidence_embeddings IS 'Semantic vector of one evidence item''s excerpt (finding, recall, review, flag), per model.';
        CREATE TABLE chat_threads (
            id uuid NOT NULL DEFAULT uuidv7(),
            user_id uuid NOT NULL,
            product_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            last_message_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT chat_threads_pkey PRIMARY KEY (id)
        );
        COMMENT ON TABLE chat_threads IS 'A member''s conversation with the product assistant about one product (its memory).';
        CREATE TABLE chat_messages (
            id uuid NOT NULL DEFAULT uuidv7(),
            thread_id uuid NOT NULL,
            role text NOT NULL,
            content text NOT NULL,
            citations jsonb NOT NULL DEFAULT '[]'::jsonb,
            model_code text,
            prompt_version text,
            input_tokens integer,
            output_tokens integer,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT chat_messages_pkey PRIMARY KEY (id),
            CONSTRAINT chat_messages_chk1 CHECK (role IN ('user', 'assistant')),
            CONSTRAINT chat_messages_chk2 CHECK (char_length(content) BETWEEN 1 AND 8000)
        );
        COMMENT ON TABLE chat_messages IS 'One turn of a conversation. An answer keeps the evidence it cited and the model that wrote it.';
        COMMENT ON COLUMN chat_messages.citations IS '[{evidence_id, url, excerpt}]';
        CREATE INDEX chat_threads_i1_idx ON chat_threads (user_id, product_id, last_message_at DESC);
        CREATE INDEX chat_messages_i1_idx ON chat_messages (thread_id, created_at);
        ALTER TABLE product_embeddings ADD CONSTRAINT product_embeddings_product_id_fkey FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE;
        ALTER TABLE product_embeddings ADD CONSTRAINT product_embeddings_model_code_fkey FOREIGN KEY (model_code) REFERENCES embedding_models (code) ON DELETE RESTRICT;
        CREATE INDEX product_embeddings_model_code_fk_idx ON product_embeddings (model_code);
        ALTER TABLE evidence_embeddings ADD CONSTRAINT evidence_embeddings_evidence_id_fkey FOREIGN KEY (evidence_id) REFERENCES evidence_items (id) ON DELETE CASCADE;
        ALTER TABLE evidence_embeddings ADD CONSTRAINT evidence_embeddings_model_code_fkey FOREIGN KEY (model_code) REFERENCES embedding_models (code) ON DELETE RESTRICT;
        CREATE INDEX evidence_embeddings_model_code_fk_idx ON evidence_embeddings (model_code);
        ALTER TABLE chat_threads ADD CONSTRAINT chat_threads_user_id_fkey FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE;
        ALTER TABLE chat_threads ADD CONSTRAINT chat_threads_product_id_fkey FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE;
        CREATE INDEX chat_threads_product_id_fk_idx ON chat_threads (product_id);
        ALTER TABLE chat_messages ADD CONSTRAINT chat_messages_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES chat_threads (id) ON DELETE CASCADE;
        CREATE TRIGGER chat_messages_guard_immutable BEFORE UPDATE OR DELETE ON chat_messages FOR EACH ROW EXECUTE FUNCTION telcron_guard_immutable();
        CREATE TRIGGER product_embeddings_dims BEFORE INSERT OR UPDATE ON product_embeddings
            FOR EACH ROW EXECUTE FUNCTION telcron_embedding_dims_check();
        CREATE TRIGGER evidence_embeddings_dims BEFORE INSERT OR UPDATE ON evidence_embeddings
            FOR EACH ROW EXECUTE FUNCTION telcron_embedding_dims_check();
    END IF;
END $$;

-- migrate:down
DROP TABLE IF EXISTS chat_messages, chat_threads, evidence_embeddings, product_embeddings;
