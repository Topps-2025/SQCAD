// A finite, editable teaching model. These constants are NOT experimental results.
(function (root) {
  'use strict';
  const payoffs = {
    A1: { keep: [[4,1,0],[4,1,0],[4,1,0]], archive: [[0,0,3],[0,0,3],[0,0,3]] },
    A2: { keep: [[4,1,0],[0,1,0],[0,1,0]], archive: [[0,0,3],[0,0,0],[0,0,0]] },
    B1: { keep: [[0,1,2],[4,1,0],[4,1,0]], archive: [[3,0,0],[0,0,1],[0,0,1]] },
    B2: { keep: [[0,1,2],[0,1,2],[0,1,2]], archive: [[3,0,0],[3,0,0],[3,0,0]] }
  };
  const stories = {
    alex: {
      A1: ['Another loud invitation', 'Saturday: a quiet exhibition respects the continuing sensitivity.', 'Next week: a loud restaurant invitation makes the warning useful again.', 'The following week: a concert suggestion needs the same constraint.'],
      A2: ['Two tasks that do not need the note', 'Saturday: the quiet plan still helps.', 'Next week: Alex asks for a reading list; venue noise is irrelevant.', 'The following week: a train timetable needs no venue preference. Keeping the note adds exposure cost.'],
      B1: ['A new exam week', 'Saturday: the expired exception blocks a concert Alex wanted.', 'Next week: a new exam makes quiet plans useful again, by coincidence.', 'The following week: the exam period continues. Later benefit does not validate the old note or refund the missed concert.'],
      B2: ['Another invitation filtered out', 'Saturday: the expired note blocks the concert.', 'Next week: Alex wants a lively birthday dinner, but the stale rule filters it out.', 'The following week: another desired festival is excluded. The avoidable loss repeats.']
    },
    finance: {
      A1: ['Risk across three reviews', 'Today: the warning routes structural liquidity risk to review.', 'Next review: another cash-flow shortfall makes the warning useful.', 'Renewal: the structural gap still needs a credit officer.'],
      A2: ['Administrative work follows', 'Today: the warning helps the credit review.', 'Next task: update the borrower address; liquidity is irrelevant.', 'Next task: prepare an account summary. The default flag consumes attention without helping.'],
      B1: ['A fresh payment delay', 'Today: a cleared receivable makes the old flag an unnecessary obstacle.', 'Next month: a different receivable is delayed; the same warning happens to help.', 'Renewal: the new shortfall persists. Coincidental usefulness is not proof of the original flag.'],
      B2: ['Healthy reviews, repeated friction', 'Today: the expired flag delays review.', 'Next month: current finances remain sound but the old flag reappears.', 'Renewal: another manual exception is needed. Repeated review overhead accumulates.']
    },
    care: {
      A1: ['Repeated clinician review', 'Today: an active warning routes the refill to the clinician.', 'Next visit: current labs still require that safety review.', 'Follow-up: the clinician still needs the scoped alert. No autonomous prescribing occurs.'],
      A2: ['Scheduling is not prescribing', 'Today: the warning supports clinician review.', 'Next task: reschedule an appointment; the medication note does not help.', 'Next task: retrieve clinic directions. Extra alerts add attention cost.'],
      B1: ['A new episode needs new evidence', 'Today: the resolved episode causes an unnecessary referral.', 'Next visit: a new lab concern makes review useful again.', 'Follow-up: the new episode still needs clinical review. This cannot retroactively authorize the old warning.'],
      B2: ['The old episode keeps resurfacing', 'Today: the expired warning adds paperwork.', 'Next visit: the clinical team must clear the same historical alert again.', 'Follow-up: another duplicate referral consumes staff time. Historical context is not current clearance.']
    },
    atlas: {
      A1: ['Three legacy deployments', 'Today: the actual target still needs the legacy control.', 'Next release: the same target still requires rotation review.', 'Next patch: the legacy workflow remains in scope.'],
      A2: ['Documentation tasks follow', 'Today: the legacy control helps the release checklist.', 'Next task: edit release notes; credential rotation is irrelevant.', 'Next task: update the changelog. Keeping the note adds irrelevant context.'],
      B1: ['A legacy hotfix returns', 'Today: the v2 rule unnecessarily blocks a managed v3 release.', 'Next task: a legacy hotfix needs the v2 runbook again.', 'Next patch: that legacy target remains active. Usefulness returns in a different scope.'],
      B2: ['More managed releases', 'Today: the obsolete manual step stalls v3.', 'Next release: managed credentials still make the old step unnecessary.', 'Next patch: another release hits the same obsolete gate. Delay accumulates.']
    }
  };
  function steps(id, action, policy = 'reuse') {
    return payoffs[id][action].map((row, t) => {
      if (policy === 'reuse') return [...row];
      // This alternative inspects scope on every task, retrieves archived sources,
      // and filters kept notes. Both interventions pay the same check cost.
      const k = payoffs[id].keep[t], a = payoffs[id].archive[t];
      const best = k[0] - k[2] > a[0] - a[2] ? k : a;
      return [best[0], 1.5 + (action === 'keep' ? 0.3 : 0), best[2]];
    });
  }
  function value(id, action, {horizon = 3, gamma = 0.9, policy = 'reuse'} = {}) {
    return steps(id, action, policy).slice(0, horizon).reduce((sum, [y,c,r], t) => sum + gamma ** t * (y-c-r), 0);
  }
  function weights(pA = .5, pA1 = .5, pB1 = .5) {
    return {A1:pA*pA1, A2:pA*(1-pA1), B1:(1-pA)*pB1, B2:(1-pA)*(1-pB1)};
  }
  function aggregate(action, options = {}) {
    const ps = weights(options.pA, options.pA1, options.pB1);
    return Object.entries(ps).reduce((sum, [id,p]) => sum + p*value(id,action,options),0);
  }
  const api = {payoffs,stories,steps,value,weights,aggregate};
  if (typeof module !== 'undefined') module.exports = api;
  root.SQFuture = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
