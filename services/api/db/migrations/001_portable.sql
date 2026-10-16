-- Explicit migration; executed only by scripts.migrate_postgres schema.
CREATE SCHEMA IF NOT EXISTS factorymind;
REVOKE ALL ON SCHEMA factorymind FROM PUBLIC;
SET LOCAL search_path TO factorymind,public;
CREATE TABLE factorymind_schema_versions(version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE incidents(
 incident_id TEXT PRIMARY KEY, record_id INTEGER NOT NULL, product_id TEXT NOT NULL,
 machine_type TEXT NOT NULL, algorithm TEXT NOT NULL, anomaly_score DOUBLE PRECISION NOT NULL,
 severity TEXT NOT NULL, status TEXT NOT NULL, source_measurements TEXT NOT NULL,
 evidence TEXT NOT NULL, explanations TEXT NOT NULL, note TEXT, detection_config TEXT,
 created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE UNIQUE INDEX idx_incident_active ON incidents(record_id,algorithm) WHERE status!='resolved';
CREATE INDEX idx_incident_status ON incidents(status);
CREATE INDEX idx_incident_severity ON incidents(severity);
CREATE TABLE incident_events(
 id BIGSERIAL PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
 status TEXT NOT NULL, note TEXT, timestamp TIMESTAMPTZ NOT NULL
);
CREATE TABLE investigations(
 investigation_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
 status TEXT NOT NULL, stage TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
 summary TEXT, report TEXT, error TEXT, stage_history TEXT NOT NULL, agent_activity TEXT NOT NULL DEFAULT '[]',
 prepared_context TEXT, attempt_count INTEGER NOT NULL DEFAULT 0,
 created_at TIMESTAMPTZ NOT NULL, started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, updated_at TIMESTAMPTZ NOT NULL,
 execution_token TEXT, UNIQUE(investigation_id,incident_id)
);
CREATE UNIQUE INDEX idx_investigation_active ON investigations(incident_id) WHERE status IN ('queued','running');
CREATE INDEX idx_investigation_status_created ON investigations(status,created_at DESC);
CREATE TABLE investigation_evidence(
 investigation_id TEXT NOT NULL, evidence_id TEXT NOT NULL, incident_id TEXT NOT NULL,
 evidence_type TEXT NOT NULL, source TEXT NOT NULL, observation TEXT NOT NULL,
 value DOUBLE PRECISION, units TEXT, provenance TEXT NOT NULL, payload TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
 PRIMARY KEY(investigation_id,evidence_id),
 FOREIGN KEY(investigation_id,incident_id) REFERENCES investigations(investigation_id,incident_id)
);
CREATE TABLE counterfactual_scenarios(
 scenario_id TEXT PRIMARY KEY, original_investigation_id TEXT NOT NULL REFERENCES investigations(investigation_id),
 incident_id TEXT NOT NULL REFERENCES incidents(incident_id), revised_investigation_id TEXT REFERENCES investigations(investigation_id),
 excluded_evidence_ids TEXT NOT NULL, excluded_feature_keys TEXT NOT NULL DEFAULT '[]', rationale TEXT,
 status TEXT NOT NULL, error TEXT, comparison TEXT, dependency_trace TEXT NOT NULL DEFAULT '[]',
 created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
 FOREIGN KEY(original_investigation_id,incident_id) REFERENCES investigations(investigation_id,incident_id),
 FOREIGN KEY(revised_investigation_id,incident_id) REFERENCES investigations(investigation_id,incident_id)
);
CREATE INDEX idx_counterfactual_original ON counterfactual_scenarios(original_investigation_id);
CREATE TABLE visual_evidence(
 image_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
 investigation_id TEXT REFERENCES investigations(investigation_id), storage_ref TEXT NOT NULL,
 filename TEXT NOT NULL, mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL CHECK(size_bytes>0), width INTEGER, height INTEGER,
 provenance TEXT NOT NULL, storage_backend TEXT NOT NULL, status TEXT NOT NULL,
 summary TEXT, observations TEXT NOT NULL DEFAULT '[]', limitations TEXT NOT NULL DEFAULT '[]', error TEXT,
 created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
 FOREIGN KEY(investigation_id,incident_id) REFERENCES investigations(investigation_id,incident_id)
);
CREATE INDEX idx_visual_incident ON visual_evidence(incident_id);
CREATE TABLE gemini_request_leases(token TEXT PRIMARY KEY, expires_at DOUBLE PRECISION NOT NULL);
CREATE TABLE gemini_provider_cooldowns(model TEXT PRIMARY KEY, category TEXT NOT NULL, expires_at DOUBLE PRECISION NOT NULL);
CREATE TABLE portable_ai_usage(day TEXT NOT NULL, principal TEXT NOT NULL, requests INTEGER NOT NULL, PRIMARY KEY(day,principal));
REVOKE ALL ON ALL TABLES IN SCHEMA factorymind FROM PUBLIC;
-- factorymind is intentionally NOT an exposed Supabase Data API schema.
INSERT INTO factorymind_schema_versions(version) VALUES(1);
