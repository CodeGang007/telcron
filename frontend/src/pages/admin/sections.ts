import { ClipboardCheck, Database, LayoutDashboard, type LucideIcon } from 'lucide-react';

export type StaffRole = 'admin' | 'moderator';

export type AdminSection = {
  to: string;
  label: string;
  blurb: string;
  icon: LucideIcon;
  roles: readonly StaffRole[];
};

/** The admin area's sections and who may open each (WO-055). WO-045 adds the rest of the console here. */
export const SECTIONS: readonly AdminSection[] = [
  { to: '/admin', label: 'Overview', blurb: 'Everything you can open in the admin area.', icon: LayoutDashboard, roles: ['admin', 'moderator'] },
  { to: '/admin/data-sources', label: 'Data sources', blurb: 'Import recall notices and watch the runs.', icon: Database, roles: ['admin'] },
  { to: '/admin/review-queue', label: 'Review queue', blurb: 'Reports, corrections and holds waiting for a decision.', icon: ClipboardCheck, roles: ['admin', 'moderator'] },
];

export function isStaff(role: string | undefined): role is StaffRole {
  return role === 'admin' || role === 'moderator';
}

export function sectionsFor(role: string | undefined): AdminSection[] {
  return isStaff(role) ? SECTIONS.filter((s) => s.roles.includes(role)) : [];
}
