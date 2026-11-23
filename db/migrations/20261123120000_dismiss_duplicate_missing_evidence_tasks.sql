-- One open "missing evidence" task per product (DEF-120, after DEF-032). Hand-written, data only.
-- Before DEF-032 every re-screen opened a new `hazard_insufficient_data` task, so some products hold
-- several open ones. The application has kept one per product since DEF-032
-- (backend/app/modules/screening/service.py `_open_insufficient_data_task`); this clears the backlog.
-- For each product (payload->>'product_id'), the newest open or in-progress task (created_at, then id)
-- stays; the older ones become `dismissed` with a resolution note and resolved_at, which
-- review_tasks_chk2 requires. Other task types, tasks without a product id and closed tasks are not
-- touched. Running it again changes nothing.

-- migrate:up
WITH ranked AS (
    SELECT id,
           row_number() OVER (PARTITION BY payload->>'product_id'
                              ORDER BY created_at DESC, id DESC) AS rn
      FROM review_tasks
     WHERE task_type = 'hazard_insufficient_data'
       AND status IN ('open', 'in_progress')
       AND payload->>'product_id' IS NOT NULL
)
UPDATE review_tasks t
   SET status = 'dismissed',
       resolution = 'superseded: one open missing-evidence task per product (DEF-032/DEF-120)',
       resolved_at = now()
  FROM ranked r
 WHERE t.id = r.id AND r.rn > 1;

-- migrate:down
-- Not reversible: which dismissed tasks were open before cannot be told apart from ones a person
-- dismissed with the same note, and reopening them would bring the duplicates back. Deliberate no-op.
SELECT 1;
