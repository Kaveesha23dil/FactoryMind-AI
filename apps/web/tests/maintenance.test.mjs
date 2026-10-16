import assert from 'node:assert/strict';
import test from 'node:test';
import { buildMaintenanceDrafts, loadMaintenance } from '../src/lib/maintenance.ts';

function fixture(id = 'INV-TEST') {
 const hypothesis = { hypothesis_id: 'H-1', title: 'Candidate overload', description: 'Needs inspection', supporting_evidence_ids: ['EV-1', 'EV-1', 'EV-GHOST'], contradicting_evidence_ids: ['EV-2'], missing_evidence: ['Vibration'], verification_steps: [], assessment: 'weak' };
 const report = { investigation_id: id, incident_id: 'INC-TEST', status: 'completed', provider: 'google', evidence_catalog: ['EV-1', 'EV-2'], hypotheses: [hypothesis], recommended_actions: [{ action: 'Inspect tool condition', rationale: 'Verify candidate explanation', requires_human_approval: true, supporting_hypothesis_ids: ['H-1'] }], critic_review: { issues_found: ['Unverified explanation'], unsupported_claims: [], contradictions: [], citation_issues: [], deterministic_findings: [], excluded_evidence_reused: [], missing_evidence: ['Vibration'], revision_required: false } };
 return { job: { investigation_id: id, incident_id: 'INC-TEST', status: 'completed', provider: 'google', report }, evidence: ['EV-1', 'EV-2'].map(evidence_id => ({ evidence_id, investigation_id: id, incident_id: 'INC-TEST', source: 'Saved source', provenance: 'Benchmark observation' })) };
}
test('only saved completed Google reports produce drafts; no synthetic fallback', () => {
 const { job, evidence } = fixture();
 assert.deepEqual(buildMaintenanceDrafts({ ...job, status: 'failed' }, evidence), []);
 assert.deepEqual(buildMaintenanceDrafts({ ...job, provider: 'scripted' }, evidence), []);
 assert.deepEqual(buildMaintenanceDrafts({ ...job, report: { ...job.report, recommended_actions: [] } }, evidence), []);
 assert.throws(() => buildMaintenanceDrafts({ ...job, report: null }, evidence), /no matching completed report/);
});
test('unique resolved counts, contradictions and historical critic concerns remain visible', () => {
 const { job, evidence } = fixture(); const before = structuredClone(job);
 const [draft] = buildMaintenanceDrafts(job, evidence);
 assert.deepEqual(draft.supportingIds, ['EV-1']);
 assert.deepEqual(draft.contradictingIds, ['EV-2']);
 assert.deepEqual(draft.unresolvedIds, ['EV-GHOST']);
 assert.deepEqual(draft.missingInformation, ['Vibration']);
 assert.deepEqual(draft.concerns, ['Unverified explanation']); // Even revision_required=false.
 assert.deepEqual(job, before);
 const incomplete = buildMaintenanceDrafts(job, [{ ...evidence[0], provenance: '' }, evidence[1]])[0];
 assert.equal(incomplete.supportingIds.length, 0);
 assert.ok(incomplete.unresolvedIds.includes('EV-1'));
});
test('reject foreign report/evidence ownership and expose missing hypothesis links', () => {
 const { job, evidence } = fixture();
 assert.throws(() => buildMaintenanceDrafts({ ...job, report: { ...job.report, incident_id: 'INC-OTHER' } }, evidence), /ownership/);
 assert.throws(() => buildMaintenanceDrafts(job, [{ ...evidence[0], investigation_id: 'INV-OTHER' }]), /different investigation/);
 job.report.recommended_actions[0].supporting_hypothesis_ids = ['H-MISSING'];
 const [draft] = buildMaintenanceDrafts(job, evidence);
 assert.equal(draft.supportingIds.length, 0);
 assert.ok(draft.missingInformation.includes('Unknown supporting hypothesis: H-MISSING'));
});
test('pagination reads all completed records, excludes scripted runs and counts real actions', async () => {
 const data = [fixture('INV-A'), fixture('INV-B')]; const offsets = [];
 const snapshot = await loadMaintenance({
  list: async offset => { offsets.push(offset); return { total: 3, items: offset === 0 ? [data[0].job, { investigation_id: 'INV-SCRIPTED', provider: 'scripted' }] : [data[1].job] }; },
  job: async id => data.find(item => item.job.investigation_id === id).job,
  evidence: async id => ({ investigation_id: id, incident_id: 'INC-TEST', items: data.find(item => item.job.investigation_id === id).evidence }),
 });
 assert.deepEqual(offsets, [0, 2]); assert.equal(snapshot.completedReports, 3);
 assert.equal(snapshot.eligibleReports, 2); assert.equal(snapshot.drafts.length, 2);
});
test('empty is genuine; incomplete reads and network failures do not become zero counts', async () => {
 const unused = async () => { throw new Error('Should not fetch'); };
 assert.deepEqual(await loadMaintenance({ list: async () => ({ total: 0, items: [] }), job: unused, evidence: unused }), { drafts: [], completedReports: 0, eligibleReports: 0 });
 await assert.rejects(loadMaintenance({ list: async () => ({ total: 1, items: [] }), job: unused, evidence: unused }), /incomplete/);
 await assert.rejects(loadMaintenance({ list: async () => { throw new Error('Offline'); }, job: unused, evidence: unused }), /Offline/);
});
test('malformed evidence responses and invalid relationship verdicts are not hidden', async () => {
 const { job, evidence } = fixture();
 await assert.rejects(loadMaintenance({ list: async () => ({ total: 1, items: [job] }), job: async () => job, evidence: async () => ({ investigation_id: 'INV-OTHER', incident_id: job.incident_id, items: evidence }) }), /ownership/);
 job.report.critic_review.citation_reviews = [{ evidence_id: 'EV-1', valid: false, reason: 'Does not support hypothesis' }];
 assert.ok(buildMaintenanceDrafts(job, evidence)[0].concerns.some(reason => reason.includes('Does not support hypothesis')));
});
