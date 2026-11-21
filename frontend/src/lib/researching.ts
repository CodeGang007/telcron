/** Products whose research this browser is waiting for, so progress follows the member around the
    app. Per-browser convenience only: the server is the record. */
export type Tracked = { slug: string; name: string };
const KEY = 'telcron-researching';
const EVENT = 'telcron-researching';

export function tracked(): Tracked[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as Tracked[];
  } catch {
    return [];
  }
}

function save(list: Tracked[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list.slice(-5)));
  } catch { /* storage blocked: the page still shows progress itself */ }
  window.dispatchEvent(new Event(EVENT));
}

export const track = (slug: string, name: string) => save([...tracked().filter((t) => t.slug !== slug), { slug, name }]);
export const untrack = (slug: string) => save(tracked().filter((t) => t.slug !== slug));
export const onTrackedChange = (fn: () => void) => {
  window.addEventListener(EVENT, fn);
  return () => window.removeEventListener(EVENT, fn);
};
