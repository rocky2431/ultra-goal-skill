// Optional execution attachment; requires the shared goal and decisions record.
// It targets one specific workflow runtime: the host feature that provides agent(),
// pipeline(), parallel() and the meta block. This Skill ships the sample, not the
// engine - validate_artifact.py checks the structure and node --check parses the
// source, and neither executes it nor proves the runtime exists in this session.
// The returned { confirmed } object is the runtime's answer, not Goal completion:
// completion is settled only by the shared contract below - the frozen evaluator
// baselines, any required independent review, and the current anchor run.
// Use only with an installed, exercised workflow consumer. All shapes arm the
// same goal and submit completion candidates against that contract.
// goal: `review-changed-files.goal.md`
// `meta` must stay the first statement and a pure literal.
// The runtime evaluates this inside an async function, so top-level await and return
// are legal. Every phase used below must appear in meta.phases.

// anchor: `pnpm test -- --run`
export const meta = {
  name: 'review-changed-files',
  description: 'Review the diff across dimensions, then verify each finding adversarially',
  phases: [{ title: 'Review' }, { title: 'Verify' }],
}

const DIMENSIONS = [
  { key: 'correctness', prompt: 'Find correctness bugs in the current diff.' },
  { key: 'security', prompt: 'Find security defects in the current diff.' },
]

const FINDINGS = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: { title: { type: 'string' }, file: { type: 'string' } },
        required: ['title', 'file'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT = {
  type: 'object',
  properties: { isReal: { type: 'boolean' }, evidence: { type: 'string' } },
  required: ['isReal', 'evidence'],
}

// pipeline streams each dimension into verification as soon as that dimension finishes,
// so 'security' verifies while 'correctness' is still reviewing.
const results = await pipeline(
  DIMENSIONS,
  d => agent(`Read .goals/review-changed-files.goal.md and follow its authority and acceptance contract. ${d.prompt}`,
    { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS }),
  review => parallel(review.findings.map(f => () =>
    agent(`Read .goals/review-changed-files.goal.md and follow its contract. Adversarially verify, running the code: ${f.title} in ${f.file}`,
      { label: `verify:${f.file}`, phase: 'Verify', schema: VERDICT })
      .then(v => ({ ...f, verdict: v }))
  )),
)

const confirmed = results.flat().filter(Boolean).filter(f => f.verdict?.isReal)

return { confirmed }
