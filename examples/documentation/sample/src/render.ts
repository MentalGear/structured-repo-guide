// Measure every item once per frame, not once per item: a size read inside the loop
// forces a reflow each time (backlog 3).
export function measureAll(items: HTMLElement[]): number[] {
  return items.map((el) => el.offsetHeight);
}

/* The panel width is 2px narrower than its container so the focus ring never clips
   inside an overflow:hidden parent. */
export const PANEL_INSET = 2;
