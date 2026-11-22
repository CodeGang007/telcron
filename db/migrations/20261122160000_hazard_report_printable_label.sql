-- The hazard report's store label says what is delivered (DEF-035, WO-019, CT-002). Hand-written.
-- The report is a printable HTML page, not a PDF file, so the label stops promising a PDF. Only the
-- label changes: the item code `hazard_report_pdf`, its fulfilment_type `pdf_report`, its cost and every
-- other column stay as they are (the code is the stable key callers and past redemptions use).
-- Each step touches the row only when it still carries the label it expects, so it is safe to re-run.

-- migrate:up
UPDATE redemption_items
   SET name = 'Full hazard report (printable)'
 WHERE code = 'hazard_report_pdf' AND name = 'Full hazard report (PDF)';

-- migrate:down
UPDATE redemption_items
   SET name = 'Full hazard report (PDF)'
 WHERE code = 'hazard_report_pdf' AND name = 'Full hazard report (printable)';
