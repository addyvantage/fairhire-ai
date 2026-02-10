import type { Transition, Variants } from "framer-motion"

export const premiumEase = [0.16, 1, 0.3, 1] as const

export const transitions = {
  micro: { duration: 0.14, ease: premiumEase } satisfies Transition,
  fast: { duration: 0.2, ease: premiumEase } satisfies Transition,
  base: { duration: 0.32, ease: premiumEase } satisfies Transition,
  slow: { duration: 0.45, ease: premiumEase } satisfies Transition,
}

export const staggerContainer = (stagger = 0.07, delayChildren = 0): Variants => ({
  hidden: {},
  show: {
    transition: {
      staggerChildren: stagger,
      delayChildren,
    },
  },
})

export const fadeUp = (distance = 10): Variants => ({
  hidden: { opacity: 0, y: distance },
  show: {
    opacity: 1,
    y: 0,
    transition: transitions.base,
  },
})

export const pageEnter: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: transitions.base },
}

export const subtleScaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.985 },
  show: { opacity: 1, scale: 1, transition: transitions.fast },
}
