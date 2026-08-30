import clsx, { type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

// Design tokens added by Gate 3B (docs/design/design.md §6) must be
// recognized as font-size classes, otherwise tailwind-merge treats
// `text-label`/`text-metadata`/… as colors and drops them when a
// text-color class follows (e.g. Badge className overrides).
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [{ text: ['page-title', 'section-heading', 'notice-title', 'body', 'detail-body', 'metadata', 'label'] }],
    },
  },
})

export const cn = (...values: ClassValue[]) => twMerge(clsx(values))
