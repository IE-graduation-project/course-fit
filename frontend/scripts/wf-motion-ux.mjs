export const meta = {
  name: 'motion-ux-directions',
  description: 'Research motion-driven minimal-text UX, then produce 3 buildable design directions for course-fit',
  phases: [
    { title: 'Research', detail: '6 parallel web-research agents on motion-first, wordless UX' },
    { title: 'Synthesize', detail: 'merge findings into one motion design language' },
    { title: 'Direction', detail: '3 distinct buildable directions, divergent lenses' },
    { title: 'Critique', detail: 'adversarial taste + presentation-safety scoring' },
  ],
}

const PRODUCT = [
  'PRODUCT: course-fit, a Hongik University Industrial Data Engineering graduation project.',
  "A student pastes their transcript TEXT and picks a target job; an ILP optimizer recommends a conflict-free next-semester timetable that fills the chosen job's skill gaps.",
  "STACK: Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind CSS v4 (CSS-variable tokens, oklch warm-neutral palette, ONE green accent, hairline blueprint grid, borders-over-shadows, radius ~11px), Framer Motion via 'motion/react', Recharts, Radix primitives, Pretendard font.",
  'CURRENT SINGLE-SCREEN FLOW (4 states): (1) idle/input = big textarea to paste transcript + a detailed how-to-fetch-transcript guide; (2) recognized = chips show 학번/학과/이수학점/GPA; (3) job-selection = 6 job cards + a 잘 모르겠어요 option; (4) result = weekly timetable grid (월~금 columns by 교시 rows, course blocks) + per-job competency viz + a switch-job toggle bar. Demo uses MOCK data.',
  'GOAL NOW: MAXIMIZE visual + MOTION, MINIMIZE text. Movement should do the explaining. Award-site taste (awwwards.com, 21st.dev, codrops, mobbin, godly.website). HARD RULE (THE LILA RULE): NO generic AI purple/blue gradients, no default serif; warm-neutral + single green accent only, borders over shadows.',
  'CONSTRAINT: it is for a graduation PRESENTATION that is imminent, so every state must screenshot beautifully AND be demo-safe (no fragile/janky motion on a projector).',
].join('\n')

const RESEARCH_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    angle: { type: 'string' },
    patterns: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          name: { type: 'string' },
          whatItIs: { type: 'string' },
          whyItWorks: { type: 'string' },
          howToBuild: { type: 'string', description: 'concrete implementation in our stack (motion/react, Tailwind v4)' },
          source: { type: 'string', description: 'url or product name' },
        },
        required: ['name', 'whatItIs', 'whyItWorks', 'howToBuild'],
      },
    },
    antipatterns: { type: 'array', items: { type: 'string' } },
    keyTakeaway: { type: 'string' },
  },
  required: ['angle', 'patterns', 'keyTakeaway'],
}

const SYNTH_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    principles: { type: 'array', items: { type: 'string' } },
    motionVocabulary: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: { name: { type: 'string' }, use: { type: 'string' } },
        required: ['name', 'use'],
      },
    },
    perStateGuidance: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: { state: { type: 'string' }, guidance: { type: 'string' } },
        required: ['state', 'guidance'],
      },
    },
    dos: { type: 'array', items: { type: 'string' } },
    donts: { type: 'array', items: { type: 'string' } },
  },
  required: ['principles', 'motionVocabulary', 'perStateGuidance', 'dos', 'donts'],
}

const DIRECTION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    name: { type: 'string' },
    tagline: { type: 'string' },
    coreMetaphor: { type: 'string' },
    choreography: {
      type: 'array',
      description: 'step-by-step across the full flow: what motion happens at each trigger',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          trigger: { type: 'string' },
          whatHappens: { type: 'string' },
          motionDetail: { type: 'string', description: 'easing/spring/stagger/shared-element specifics' },
        },
        required: ['trigger', 'whatHappens', 'motionDetail'],
      },
    },
    layoutByState: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: { state: { type: 'string' }, layout: { type: 'string' } },
        required: ['state', 'layout'],
      },
    },
    textRemoved: { type: 'array', items: { type: 'string' } },
    textReplacement: { type: 'string' },
    framerNotes: { type: 'string', description: 'concrete motion/react APIs' },
    presentationSafety: { type: 'string' },
    buildEffort: { type: 'string' },
  },
  required: ['name', 'tagline', 'coreMetaphor', 'choreography', 'layoutByState', 'framerNotes', 'presentationSafety', 'buildEffort'],
}

const CRITIQUE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    scores: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          direction: { type: 'string' },
          tasteScore: { type: 'number' },
          presentationSafety: { type: 'number' },
          buildability: { type: 'number' },
          notes: { type: 'string' },
        },
        required: ['direction', 'tasteScore', 'presentationSafety', 'buildability', 'notes'],
      },
    },
    recommended: { type: 'string' },
    rationale: { type: 'string' },
    graftsFromOthers: { type: 'array', items: { type: 'string' } },
    risks: { type: 'array', items: { type: 'string' } },
  },
  required: ['scores', 'recommended', 'rationale'],
}

phase('Research')
const ANGLES = [
  { key: 'motion-first-award', q: 'Research how 2025-2026 award-winning sites (awwwards.com, godly.website, 21st.dev, codrops tutorials) achieve a MOTION-FIRST feel with almost no body text. Find specific recurring techniques: scroll-choreographed reveals, shared-element/FLIP transitions, sticky-scroll storytelling, kinetic typography used sparingly, magnetic/spring micro-interactions. For each, exactly how to build it with motion/react + Tailwind v4 in a warm-neutral + single-green palette.' },
  { key: 'wordless-onboarding', q: 'Research WORDLESS / minimal-text UI: how top products replace written instructions with motion, demonstration, and progressive disclosure. How onboarding teaches by showing not telling (animated placeholders, self-demonstrating empty states, ghost/skeleton previews that animate into real content). Sources: mobbin, real products (Linear, Raycast, Arc, Vercel, Things, Superhuman). Concrete buildable patterns only.' },
  { key: 'paste-to-structure', q: 'Research the PASTE-A-BLOB to STRUCTURED-OUTPUT interaction: how trendy tools take a pasted text dump and morph it elegantly into structured UI. Linear/Notion paste parsing, Raycast, Vercel v0, AI tools that animate raw text resolving into cards/tables. Focus on transition choreography (text dissolving, tokens flying into slots, shimmer-to-solid) and how to do it in motion/react with AnimatePresence + layout animations.' },
  { key: 'schedule-result-reveal', q: 'Research how schedule/timetable/calendar and optimizer tools ANIMATE a result into view compellingly: blocks dropping/assembling into a weekly grid, staggered course-block entrances, conflict-resolution shown as motion, data-viz entrances (radar/gauge/gap charts) via Recharts or SVG. Career/course recommendation product examples. Concrete stagger + spring recipes for a Monday-to-Friday grid.' },
  { key: 'explainability-motion', q: 'Research how to show WHY this was recommended through MOTION instead of prose, for recommendation/career/education systems. Patterns: animated gap-fill (empty skill slots filling as courses are added), before/after coverage morph, highlight-the-covered, a single one-line rationale that fades in. Academic + product UX on explanation depth vs trust. Goal: a student understands the timetable fills their job-skill gaps with zero conflicts in under 5 seconds, mostly without reading.' },
  { key: 'framer-craft', q: "Research the CRAFT of premium micro-interaction and transition in Framer Motion (the 'motion/react' package, current API): layoutId shared-element transitions, AnimatePresence popLayout mode, useScroll + useTransform scroll choreography, spring physics that read as expensive (stiffness/damping/mass values pros use), stagger via variants, useSpring smoothing, reduced-motion fallbacks. Give copy-pasteable patterns and the numeric values that separate premium from amateur." },
]
const researchRaw = await parallel(ANGLES.map((a) => () =>
  agent(PRODUCT + '\n\nYOU ARE A UX/MOTION RESEARCH AGENT. Angle: ' + a.key + '.\n' + a.q + '\n\nActually use WebSearch and WebFetch on real award/reference sites, do not rely on memory alone. Return 4-7 concrete, buildable patterns (not vague advice), each with how-to-build in OUR stack, plus antipatterns to avoid for a projector demo. Be specific and skimmable.',
    { schema: RESEARCH_SCHEMA, agentType: 'general-purpose', phase: 'Research', label: a.key })
))
const research = researchRaw.filter(Boolean)

phase('Synthesize')
const synth = await agent(
  PRODUCT + '\n\nYou are the SYNTHESIS lead. Here are findings from 6 research angles:\n' + JSON.stringify(research) + '\n\nMerge them into ONE coherent MOTION DESIGN LANGUAGE for course-fit. Resolve conflicts, drop the weak/gimmicky, keep only what is buildable in motion/react and demo-safe on a projector. Map guidance to the 4 flow states (input, recognized, job-selection, result). Be opinionated and concrete.',
  { schema: SYNTH_SCHEMA, phase: 'Synthesize' },
)

phase('Direction')
const LENSES = [
  { key: 'A-morph', brief: 'DIRECTION A, MORPH / SHARED-ELEMENT. The pasted transcript text literally transforms into the result: text lines dissolve and their tokens fly into recognition chips, then chips reflow into the timetable grid. One continuous spatial transformation, heavy use of layoutId / shared-element transitions. Input shrinks as result grows. Almost zero instructional text, the morph IS the explanation.' },
  { key: 'B-canvas', brief: "DIRECTION B, SPATIAL CANVAS / SCROLL-CHOREOGRAPHED. A single fixed canvas where progress (paste, then scroll or auto-advance) moves a camera across stations: input, recognition, job, timetable. useScroll/useTransform drive a horizontal or depth pan. Feels like one living document. Text is reduced to tiny station labels that fade in/out with the camera." },
  { key: 'C-assembly', brief: 'DIRECTION C, ASSEMBLY / SELF-DEMONSTRATING. Minimal static chrome. The empty state self-demonstrates (a ghost timetable faintly animates in the background showing what will happen). On paste, the result ASSEMBLES piece by piece: course blocks fly into the grid with stagger, skill-gap slots visibly fill, a single one-line rationale fades in. Onboarding-by-demonstration, no written guide.' },
]
const directionsRaw = await parallel(LENSES.map((l) => () =>
  agent(PRODUCT + '\n\nMOTION DESIGN LANGUAGE (agreed):\n' + JSON.stringify(synth) + '\n\nYou design ONE direction.\n' + l.brief + '\n\nGround it fully in the agreed language and the real stack/data. Specify the FULL choreography across all 4 states, the layout per state, exactly which current texts get removed and what motion/visual replaces them, concrete motion/react implementation notes (layoutId, AnimatePresence, useScroll, spring values), a presentation-safety assessment (projector, 1440px, screenshots), and a realistic build-effort estimate in hours. Make it buildable, beautiful, and distinct from the other two directions.',
    { schema: DIRECTION_SCHEMA, phase: 'Direction', label: l.key })
))
const directions = directionsRaw.filter(Boolean)

phase('Critique')
const critique = await agent(
  PRODUCT + '\n\nYou are an adversarial DESIGN CRITIC with awwwards-jury taste. Score these 3 directions:\n' + JSON.stringify(directions) + '\n\nFor each: tasteScore (0-10 award-bar), presentationSafety (0-10 projector/screenshot/demo robustness), buildability (0-10 deliverable before an imminent presentation). Be harsh on anything that risks looking like AI slop, anything fragile, anything that hides the core value. Recommend exactly ONE to build first, with rationale, the best elements to GRAFT from the other two, and the top risks to watch. Remember THE LILA RULE and that it must screenshot beautifully in every state.',
  { schema: CRITIQUE_SCHEMA, phase: 'Critique', model: 'opus' },
)

return { synth, directions, critique }
