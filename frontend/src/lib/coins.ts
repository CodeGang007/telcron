const EVENT = 'telcron:coins';

/** Call after anything that may change the member's TelCoin balance (a redemption, a contribution,
    a page that read a newer balance), so every balance on screen reads it again (DEF-034). */
export function coinsChanged() {
  window.dispatchEvent(new Event(EVENT));
}

/** Run `fn` whenever coinsChanged() is called; returns the unsubscribe. */
export function onCoinsChanged(fn: () => void): () => void {
  window.addEventListener(EVENT, fn);
  return () => window.removeEventListener(EVENT, fn);
}
