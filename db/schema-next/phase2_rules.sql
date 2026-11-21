-- Phase 2 (AI engine) rules. Hand-written; apply after phase2_schema.sql.

-- Score bands of one context may not overlap.
ALTER TABLE scoring_bands ADD CONSTRAINT scoring_bands_no_overlap
    EXCLUDE USING gist (context_code WITH =, score_range WITH &&);

-- Hallucination guard: a scored dimension must cite at least one piece of evidence (checked at commit).
CREATE OR REPLACE FUNCTION telcron_dimension_score_cited() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'scored' AND NOT EXISTS (
        SELECT 1 FROM hazard_score_citations c
         WHERE c.assessment_id = NEW.assessment_id AND c.dimension_code = NEW.dimension_code) THEN
        RAISE EXCEPTION 'telcron: dimension % of assessment % is scored without a citation',
            NEW.dimension_code, NEW.assessment_id USING ERRCODE = 'TC007';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER hazard_dimension_scores_cited AFTER INSERT ON hazard_dimension_scores
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION telcron_dimension_score_cited();

-- Embedding vectors must match their model's registered dimensions.
CREATE OR REPLACE FUNCTION telcron_embedding_dims_check() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    dims int;
BEGIN
    SELECT dimensions INTO dims FROM embedding_models WHERE code = NEW.model_code;
    IF vector_dims(NEW.embedding) <> dims THEN
        RAISE EXCEPTION 'telcron: % embedding has % dims, model % expects %',
            TG_TABLE_NAME, vector_dims(NEW.embedding), NEW.model_code, dims USING ERRCODE = 'TC008';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER media_embeddings_dims BEFORE INSERT OR UPDATE ON media_embeddings
    FOR EACH ROW EXECUTE FUNCTION telcron_embedding_dims_check();
CREATE TRIGGER recall_embeddings_dims BEFORE INSERT OR UPDATE ON recall_embeddings
    FOR EACH ROW EXECUTE FUNCTION telcron_embedding_dims_check();
CREATE TRIGGER product_embeddings_dims BEFORE INSERT OR UPDATE ON product_embeddings
    FOR EACH ROW EXECUTE FUNCTION telcron_embedding_dims_check();
CREATE TRIGGER evidence_embeddings_dims BEFORE INSERT OR UPDATE ON evidence_embeddings
    FOR EACH ROW EXECUTE FUNCTION telcron_embedding_dims_check();

-- Creates the HNSW index for an embedding model when it is activated (one index per model+table).
CREATE OR REPLACE FUNCTION telcron_create_embedding_index(p_table text, p_model text) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    dims int;
BEGIN
    SELECT dimensions INTO STRICT dims FROM embedding_models WHERE code = p_model;
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I USING hnsw ((embedding::vector(%s)) vector_cosine_ops) WHERE model_code = %L',
                   left(p_table || '_' || regexp_replace(p_model, '[^a-z0-9]+', '_', 'g'), 55) || '_hnsw',
                   p_table, dims, p_model);
END $$;
