# External design resources

Advisory pattern library for Khepri UI work. These sources can help answer a **bounded visual
question** when current Khepri authority leaves presentation underdetermined. They are never
product authority.

## Non-negotiable rule

Resolve Khepri authority first. Active specifications, governed product/design documents,
approved Khepri handoffs, and repository evidence beat every source below.

External references may suggest:
- visual hierarchy and composition;
- component presentation patterns;
- interaction and motion techniques;
- accessibility or responsive patterns worth checking.

They may **not** define:
- routes, capabilities, workflow steps, data, metrics, claims, copy, refusals, or states;
- Khepri tokens, typeface, icon family, assets, dependencies, or security policy;
- new product behavior merely because another product demonstrates it.

Do not copy a foreign `DESIGN.md` into the Khepri root or treat one as Khepri's design system.
Extract principles, map them back to Khepri authority, then implement only the mapped part.

## Source map

| Source | Use it for | Khepri guardrail |
|---|---|---|
| [Refero Styles](https://styles.refero.design/) | Compare complete visual systems and agent-readable `DESIGN.md` examples when hierarchy, density, typography roles, or surface treatment need inspiration. | Read one or two relevant styles; extract principles, not foreign tokens. Never replace §16.5, Khepri type, or component rules with a captured brand system. |
| [VoltAgent awesome-design-md](https://github.com/VoltAgent/awesome-design-md) | Browse alternative design-language descriptions and see how visual rules are expressed for coding agents. | Reference only. Do not drop a third-party `DESIGN.md` into the repository or adopt its palette, radii, shadows, icon set, or responsive rules wholesale. |
| [The Component Gallery](https://component.gallery/) | Compare how established design systems handle the same component, including usage and accessibility guidance. | Use semantics and interaction patterns as research. Khepri's active spec still decides the component, states, wording, and presentation. |
| [21st.dev](https://21st.dev/) | Search real component patterns or inspect implementation ideas when Claude would otherwise invent a generic component from memory. | Khepri product surfaces are server-rendered Jinja/CSS. Do not install React/shadcn components, add npm packages, or expand the dependency tree without a separate approved technical decision. Reimplement only a compatible pattern inside admitted Khepri files. |
| [Kinetics](https://kinetics.colorion.co/) | Motion references for state transitions, disclosure, loading, or focus feedback when motion is actually permitted. | Master spec §12 and reduced-motion behavior win. Prefer the smallest local CSS technique; do not add a motion library just to reproduce an example. |
| [What Ships](https://whatships.com/) | Study pacing, product walkthroughs, and how interfaces reveal information over time. | Presentation inspiration only. Never infer a Khepri capability, workflow step, CTA, progress state, or claim from a launch video. |
| [HyperFrames](https://www.hyperframes.dev/) | Mobile-ad and promotional-motion reference when an explicitly requested marketing/demo artifact needs it. | Not a Khepri product-UI source. Do not use it to drive application screens, workflow, or product behavior. |
| [Impeccable](https://impeccable.style/) | Existing Khepri finish/review tool for generic design quality and anti-pattern detection. | Follow §6 of this skill: Khepri constraints and approved references are inputs; Impeccable does not redirect the product. |

## Practical operating loop

1. **Name the unresolved question.** Example: “How should this analytical block separate headline,
   supporting context, and evidence without nesting cards?”
2. **Check Khepri first.** If the active spec, design language, current handoff, v2 reference, or
   accepted implementation already answers it, stop researching and use that answer.
3. **Choose one source by job.** Use a second only when comparison adds value. Do not browse the
   whole library.
4. **Extract at most three principles.** Record each as:
   `source → observed principle → Khepri mapping → rejected foreign assumptions`.
5. **Map before code.** Each adopted principle must map to an active Khepri requirement or an
   admitted presentation decision and to files the governing spec allows.
6. **Implement the smallest mapped change.** No new route, fact, wording, token system, icon family,
   dependency, or capability.
7. **Validate normally.** External inspiration does not replace Khepri browser matrices,
   bilingual/RTL checks, accessibility evidence, governance validation, or the Impeccable finish
   pass.

## Which source to pick

- Need a **visual direction or hierarchy reference** → Refero Styles or awesome-design-md.
- Need a **component behavior/semantics comparison** → Component Gallery.
- Need a **concrete component implementation pattern** → 21st.dev, reference-only.
- Need **motion technique** → Kinetics, only after §12 permits motion.
- Need **walkthrough/presentation pacing** → What Ships.
- Need a **marketing/demo animation** → HyperFrames, outside product UI.
- Need a **finished Khepri quality pass** → Impeccable.

## Agent handoff pattern

Use this shape when a Khepri UI slice genuinely needs outside reference research:

> Resolve the Khepri authority for this slice first. The unresolved design question is:
> `<question>`. Consult `<one named source>` only as non-governing pattern research. Return no
> more than three useful principles and explicitly map each one to the active Khepri spec/design
> rule and admitted files. Reject any foreign product behavior, copy, token, typeface, icon,
> dependency, or capability. Then implement only the smallest mapped change and validate it with
> the normal Khepri evidence.

If there is no unresolved visual question, skip external research entirely.
