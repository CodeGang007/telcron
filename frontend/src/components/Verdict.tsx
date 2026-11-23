import { AlertOctagon, BadgeCheck } from 'lucide-react';
import { motion } from 'motion/react';
import type { Passport } from '../lib/api';

/** "as of 21 Nov 2026": the date a "no recall found" statement is true as of (business rule §4,
    CT-003 §A). A cached or older passport has no date: say "as of the last check", never invent one. */
export function recallAsOf(pass: Pick<Passport, 'recall_checked_as_of'> | null | undefined): string {
  const iso = pass?.recall_checked_as_of;
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return 'as of the last check';
  return `as of ${d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`;
}

/** How serious the scored hazards are: a weighted total of 60+ or any one scored dimension at 60+ is
    "serious"; a total of 30-59 is "some" (business rules §3, Medium band). DEF-113. */
export function hazardLevel(pass: Passport): 'serious' | 'some' | 'none' {
  const total = pass.hazard?.total_score ?? 0;
  const worst = Math.max(0, ...(pass.hazard?.dimensions ?? []).filter((d) => d.status === 'scored' && d.score !== null).map((d) => d.score!));
  if (total >= 60 || worst >= 60) return 'serious';
  if (total >= 30) return 'some';
  return 'none';
}

const sentence = (t: string | null | undefined, fallback: string) => (t ? (/[.!?]$/.test(t.trim()) ? t.trim() : `${t.trim()}.`) : fallback);

/** One sentence on what the passport means for someone holding this product. It never says "checks
    passed" while a hazard is reported, whatever the badge says. */
export function Verdict({ pass, recalls }: { pass: Passport; recalls: Passport['recall_matches'] }) {
  const match = recalls.find((r) => r.verdict === 'match');
  const near = recalls.find((r) => r.verdict === 'near_match');
  const level = hazardLevel(pass);
  const noRecall = `No recall notice matched it ${recallAsOf(pass)}.`;
  const [tone, title, text] = match
    ? ['danger', 'This product is recalled', `${sentence(match.hazard, 'An official recall notice names this product.')} Stop using it and follow the notice's remedy.`]
    : near
      ? ['danger', 'Official recall notices may cover this product', `${sentence(near.hazard, 'A recall names this brand and a product like it.')} Check the notices below against your model and serial number.`]
      : pass.status_badge === 'certification_issue'
        ? ['warn', 'A certificate problem was found', 'One of its certificates has expired or been revoked. See the details below.']
        : level === 'serious'
          ? ['warn', 'Serious hazards are reported', `${noRecall} But sources describe a high hazard on at least one dimension: open the hazard scores below to see the evidence.`]
          : level === 'some'
            ? ['warn', 'Some hazards are reported', `${noRecall} Sources describe some hazards: open the hazard scores below to see what they say.`]
            : pass.status_badge === 'verified'
              ? ['ok', 'No recall found, checks passed', `${noRecall} Nothing we found shows a serious hazard. We keep checking.`]
              : ['neutral', 'Not enough is known yet', 'We have not found enough evidence to rate it. Research runs when a product is added; reviews and reports help too.'];
  const style = { danger: 'border-danger/30 bg-danger-tint text-danger', warn: 'border-warn/30 bg-warn-tint text-warn', ok: 'border-ok/30 bg-ok-tint text-ok', neutral: 'border-line bg-panel text-muted' }[tone as 'danger'];
  const Icon = tone === 'ok' ? BadgeCheck : AlertOctagon;
  return (
    <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} role={tone === 'danger' ? 'alert' : undefined}
      className={`flex items-start gap-3 border-b px-6 py-4 sm:px-8 ${style}`}>
      <Icon className="mt-0.5 size-5 shrink-0" />
      <div><p className="font-semibold">{title}</p><p className="mt-0.5 text-sm text-ink/80">{text}</p></div>
    </motion.div>
  );
}
