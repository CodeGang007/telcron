# Week 4 · Sat 5 – Fri 11 Dec · Media pipeline, photos on contributions, certificates, QA environment

## Goal
Every image that enters Telcron is safe and useful, members can attach photos, and passports show certificates.

## Milestone
**M2 Scan to passport** — a scanned product is identified and shows a passport with a recall verdict (tech doc §15.4), now with certificates; promoted to QA.

## Starting point
Identification photos are stored and read by Rekognition, but nothing checks, strips or resizes them; the `media` and `identity` queues have no handler; certificates exist only in sample data.

## Work orders

- **WO-007 · Media pipeline** (`data-ai-engineer`): Upload → stored → safety check → location data removed → resized → image vector; rejected images never shown; handlers for `media` (and the `identity` queue's skeleton); up to 8 images per item.
- **WO-030 · Photos on reviews and flags** (`community-rewards-engineer, frontend-engineer`): A Level 1 member attaches photos to a review or flag; the safety team sees them; earn rule `photo` paid once; another member's photo is not editable (404).
- **WO-031 · Certificates** (`catalogue-engineer, data-ai-engineer`): FCC and Energy Star imported and matched; each certification check stores evidence; UL/ETL shown as "not checked", never "not certified"; passport page shows them.
- **WO-032 · QA environment** (`infra-deploy-engineer`): Built per D2 with the human's yes and the cost; its own database and secrets; promoted from a tagged build, not on every push; M2 demonstrated there.

## Decisions due by the end of this week
D3 AI provider and daily budget · D5 Level 2 provider and ID-data basis · D6 business accounts schema · D15 production email sender.

## Performance plan
Image work only in the Worker; a passport read stays under 300 ms cached with certificates added; screening with images under 5 s (p99).

## Friday demo
Scan → identified → passport with recall verdict and certificates, on QA. A review with a photo.

## The gate (Friday, before the demo)
The seven checks in `PLAN.md` §5, run and pasted into each WO's log: QA verdict with the revert proof ·
browser walk (phone width, reload, console, network, async loop) · security review where it applies · all
gates green and the pipeline green on `main` · performance targets for new reads · no stub called done ·
board, worklog and resume note updated.
