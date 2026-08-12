-- Keep recent-flow pagination bounded as flow_summaries grows.
CREATE INDEX IF NOT EXISTS idx_flow_summaries_window_id
    ON flow_summaries (window_start DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_flow_summaries_machine_window_id
    ON flow_summaries (machine_id, window_start DESC, id DESC);
