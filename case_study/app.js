// Narrative continuations are presentation fixtures, never controller inputs.
const state = { choice: null, revealed: false, investigation: null, caseId: 'alex', evidenceMode: 'decisive' };
const $ = (id) => document.getElementById(id);
const cases = {
  alex: {label:'Alex · weekend', short:'Personal', avatar:'A', age:'A MEMORY FROM TWO WEEKS AGO', quote:'“Avoid loud venues<br>for Alex.”', source:'Extracted from an older conversation.<br>The original context is incomplete.', scope:'PERSONAL · v1', requestLabel:'ALEX · NOW', request:'“Can you plan something fun for Saturday?”', context:'The note matches the request. It has appeared in successful answers before. But you do not know whether it describes an ongoing need or a one-weekend exception.', branchCaptions:['A QUIET PLAN PREVENTS HARM','A STALE RULE CLOSES A DOOR'], chips:['Relevant to this request','Previously co-retrieved','Current validity unknown'], worlds:null},
  finance: {label:'Credit · loan review', short:'Finance', avatar:'F', age:'A MEMORY FROM LAST QUARTER', quote:'“Flag thin liquidity<br>before approval.”', source:'Extracted from an analyst note.<br>The borrower context is incomplete.', scope:'RISK · POLICY v2', requestLabel:'CREDIT DESK · NOW', request:'“Can we approve this founder-led company?”', context:'The note is relevant to the application and correlated with past defaults. It may describe a temporary cash squeeze or a durable risk signal.', probeQuestion:'“Does the liquidity warning still apply to this borrower?”', branchCaptions:['A COVENANT RISK IS CAUGHT','A HEALTHY BORROWER IS HELD BACK'], chips:['High semantic match','Past risk co-occurrence','Scope uncertain'], worlds:null},
  care: {label:'Care · appointment triage', short:'Healthcare', avatar:'C', age:'A MEMORY FROM THREE MONTHS AGO', quote:'“Avoid this medication<br>with kidney issues.”', source:'Extracted from a care-team handoff.<br>The patient state may have changed.', scope:'PATIENT · v3', requestLabel:'CARE TEAM · NOW', request:'“Suggest a routine medication refill.”', context:'The warning is safety-relevant, but the source may be an old contraindication, a temporary lab result, or a different patient context.', probeQuestion:'“Does this contraindication still apply to the current patient and labs?”', branchCaptions:['A CURRENT SAFETY CHECK SPEAKS','AN EXPIRED EPISODE LINGERS'], chips:['Safety-relevant','Sparse lineage','Current labs missing'], worlds:null},
  atlas: {label:'Atlas · release checklist', short:'Software', avatar:'S', age:'A MEMORY FROM ATLAS v2', quote:'“Rotate credentials<br>before release.”', source:'Extracted from the v2 runbook.<br>The project version is ambiguous.', scope:'PROJECT · v2', requestLabel:'ATLAS TEAM · NOW', request:'“Prepare the Atlas v3 release checklist.”', context:'The rule is highly relevant and was successful in the previous release. The current version may have changed the security workflow.', probeQuestion:'“Which credential workflow is enforced by the Atlas v3 target?”', branchCaptions:['A LEGACY CONTROL STILL PROTECTS','A V2 RULE BLOCKS THE V3 PATH'], chips:['Version match uncertain','Previously successful','Scope conflict'], worlds:null}
};
const worlds = [
  {
    id: 'A', title: 'The warning still matters.', truth: 'The original note described an ongoing sensitivity: loud sound triggers Alex’s migraines.', image: 'assets/future-noise.webp', alt: 'Alex in an orange coat holds a hand to their temple near a glowing outdoor concert.',
    keep: { regret: false, action: 'The note stays in default exposure.', answer: '“Let’s visit the quiet riverside exhibition.”', outcome: 'The recommendation respects a continuing need.', future: 'The constraint remains available for the next planning task.' },
    archive: { regret: true, action: 'The note leaves default exposure.', answer: '“There’s an outdoor concert on Saturday.”', outcome: 'A missing warning leads to a recommendation that violates Alex’s constraint.', future: 'Less exposure can mean fewer chances to discover that the note was useful.' },
    source: '“Loud sound triggers my migraines. Please avoid loud venues when planning for me.”', probe: '“Yes, that still applies. Please choose somewhere quiet.”', qualified: 'Ongoing scope supported → keep can be authorized.'
  },
  {
    id: 'B', title: 'The exception has expired.', truth: 'The original note was only about that weekend: Alex wanted quiet before an early exam. The extracted note lost that scope.', image: 'assets/future-missed.webp', alt: 'Alex sits by the river with an unused ticket, watching a warmly lit festival in the distance.',
    keep: { regret: true, action: 'The old exception remains a default rule.', answer: '“I’ve excluded the concert. Try a quiet exhibition.”', outcome: 'An outdated restriction closes off an activity Alex now wants.', future: 'Successful quiet outings could reinforce the stale rule without checking why it existed.' },
    archive: { regret: false, action: 'The expired restriction leaves default exposure.', answer: '“The outdoor concert could be a good fit.”', outcome: 'The old exception no longer narrows Alex’s choices.', future: 'The original conversation remains stored for audit or later scoped access.' },
    source: '“Avoid loud venues this weekend. I have an early exam the next morning.”', probe: '“That was only for exam weekend. I’d like the concert now.”', qualified: 'Expired scope supported → archive can be authorized.'
  }
];
cases.alex.worlds = worlds;
function scenarioWorlds(config) {
  return config.map((w, i) => ({
    id: String.fromCharCode(65 + i), image: w.image || (i === 0 ? 'assets/future-noise.webp' : 'assets/future-missed.webp'),
    alt: w.alt || 'Illustrative possible future.', ...w,
    keep: w.keep, archive: w.archive
  }));
}
cases.finance.worlds = scenarioWorlds([
  {title:'Liquidity risk is structural.', image:'assets/finance-risk.webp', truth:'The borrower has no durable cash buffer and a covenant breach is likely.', source:'“Liquidity remains structurally thin; approve only with collateral.”', probe:'“The latest statements confirm the structural liquidity gap.”', qualified:'Durable risk supported → keep as a guarded policy.', keep:{regret:false,action:'The warning stays available to the credit gate.',answer:'“Escalate for collateral before approval.”',outcome:'The review catches a risk that correlation alone could not prove.',future:'The policy remains scoped to this borrower and review.'}, archive:{regret:true,action:'The warning is hidden from default review.',answer:'“Approve without the extra collateral step.”',outcome:'A missing constraint exposes the lender to a covenant breach.',future:'Archiving removed a still-valid safeguard.'}},
  {title:'The cash squeeze was temporary.', image:'assets/finance-delay.webp', truth:'One receivable was delayed, then cleared; the old flag no longer describes the borrower.', source:'“Flag liquidity until the Q3 receivable clears.”', probe:'“The receivable cleared; this was a temporary squeeze.”', qualified:'Temporary context supported → archive the stale flag.', keep:{regret:true,action:'The old flag remains a default blocker.',answer:'“Decline or delay approval despite healthy cash flow.”',outcome:'A stale restriction creates an avoidable opportunity cost.',future:'Repeated conservative decisions reinforce the wrong policy.'}, archive:{regret:false,action:'The time-bounded flag leaves default exposure.',answer:'“Proceed, with the current statements attached.”',outcome:'The expired warning no longer blocks a sound decision.',future:'The source remains auditable if the borrower is reviewed again.'}}
]);
cases.care.worlds = scenarioWorlds([
  {title:'The contraindication is still active.', image:'assets/care-risk.webp', truth:'Current labs still show the kidney risk described by the handoff.', source:'“Current kidney function remains reduced; avoid this medication.”', probe:'“The current lab result confirms the contraindication.”', qualified:'Current safety scope supported → keep with clinical authorization.', keep:{regret:false,action:'The warning stays visible to the care team.',answer:'“Route the refill for clinician review.”',outcome:'A current safety constraint prevents an unsafe routine refill.',future:'The scoped warning can be revisited with new labs.'}, archive:{regret:true,action:'The contraindication is removed from default context.',answer:'“Suggest the routine refill.”',outcome:'An unresolved safety risk is missed.',future:'The absence of the warning cannot be interpreted as clinical clearance.'}},
  {title:'The handoff belonged to an old patient state.', image:'assets/care-delay.webp', truth:'The warning referred to an acute episode that has resolved.', source:'“Avoid this medication during the acute episode only.”', probe:'“The episode resolved; the routine refill is safe.”', qualified:'Expired episode supported → archive the old warning.', keep:{regret:true,action:'The old episode remains a default restriction.',answer:'“Do not suggest the routine refill.”',outcome:'A resolved event continues to constrain care unnecessarily.',future:'Stale safety notes can accumulate and obscure current evidence.'}, archive:{regret:false,action:'The expired warning leaves default exposure.',answer:'“Continue the routine refill workflow.”',outcome:'The team avoids treating historical context as a current contraindication.',future:'The original handoff remains available for audit.'}}
]);
cases.atlas.worlds = scenarioWorlds([
  {title:'The v2 security rule still applies.', image:'assets/atlas-risk.webp', truth:'The deployment target still uses the legacy credential path.', source:'“This release still needs manual credential rotation.”', probe:'“The target remains v2-compatible; manual rotation is required.”', qualified:'Current deployment scope supported → keep for this project.', keep:{regret:false,action:'The v2 rule stays in the release gate.',answer:'“Rotate credentials and attach the audit record.”',outcome:'The checklist preserves a control the target still requires.',future:'The rule remains scoped to the legacy deployment.'}, archive:{regret:true,action:'The v2 rule is hidden from the checklist.',answer:'“Skip the manual rotation step.”',outcome:'A version assumption creates a credential exposure.',future:'The missing step is difficult to reconstruct after release.'}},
  {title:'Atlas v3 removed the old rotation step.', image:'assets/atlas-delay.webp', truth:'The v3 workflow moved credentials to managed rotation.', source:'“Atlas v3 uses managed credentials; do not add the v2 step.”', probe:'“The target is v3; managed credentials are already enforced.”', qualified:'Version mismatch supported → archive/isolate the v2 rule.', keep:{regret:true,action:'The legacy rule remains a default checklist item.',answer:'“Pause release for a manual rotation that cannot run.”',outcome:'A stale version rule blocks a valid deployment.',future:'Teams may learn to bypass the checklist entirely.'}, archive:{regret:false,action:'The v2 note is archived from the v3 checklist.',answer:'“Use the managed credential workflow.”',outcome:'The current process stays aligned with the project version.',future:'The old runbook remains searchable with its version scope.'}}
]);
function activeCase(){ return cases[state.caseId]; }
function currentWorlds(){ return activeCase().worlds; }

function renderCasePicker(){ $('casePicker').innerHTML=Object.entries(cases).map(([id,item])=>`<button type="button" class="case-pill ${id===state.caseId?'active':''}" data-case="${id}"><span>${item.avatar}</span><strong>${item.label}</strong></button>`).join(''); $('casePicker').querySelectorAll('[data-case]').forEach(b=>b.addEventListener('click',()=>{state.caseId=b.dataset.case; reset(); renderCase(); renderCasePicker();})); }
function renderCase(){const c=activeCase(); $('memoryAge').textContent=c.age; $('memoryQuote').innerHTML=c.quote; $('memorySource').innerHTML=c.source; $('memoryScope').textContent=c.scope; $('avatar').textContent=c.avatar; $('requestLabel').textContent=c.requestLabel; $('requestText').textContent=c.request; $('contextText').textContent=c.context; $('evidenceChips').innerHTML=c.chips.map(x=>`<li>${x}</li>`).join(''); $('decisionTitle').textContent=c.requestLabel.split(' · ')[0]+' needs a decision.'; document.title=`SQCAD — ${c.label}`; }

function selectChoice(choice) {
  state.choice = choice;
  state.investigation = null;
  document.querySelectorAll('[data-choice]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.choice === choice)));
  $('revealBtn').disabled = false;
  $('choiceFeedback').textContent = choice === 'keep' ? 'You kept the note in default exposure. Follow both possible futures.' : 'You archived the note. It is stored, but no longer exposed by default.';
  if (state.revealed) renderBranches();
  renderInvestigation();
  renderInspector();
}

function reveal() {
  if (!state.choice) return;
  state.revealed = true;
  $('futures').hidden = false;
  $('investigate').hidden = false;
  $('revealBtn').textContent = 'Return to your future branches ↓';
  renderBranches();
  renderMethodContrast();
  if (!$('deferBtn')) {
    const button = document.createElement('button');
    button.id = 'deferBtn'; button.type = 'button'; button.dataset.investigation = 'defer';
    button.innerHTML = '<span>00</span><div><strong>Defer the lasting change</strong><small>Keep a review route; do not turn uncertainty into permission.</small></div><b>↗</b>';
    button.addEventListener('click', () => investigate('defer'));
    document.querySelector('.investigation-controls').prepend(button);
  }
  $('futures').scrollIntoView({ behavior: reducedMotion() ? 'instant' : 'smooth', block: 'start' });
}

function renderMethodContrast() {
  if ($('methodContrast')) return;
  const panel = document.createElement('section');
  panel.id = 'methodContrast';
  panel.className = 'method-contrast wrap';
  panel.setAttribute('aria-labelledby', 'contrastTitle');
  const methods = [
    ['Relevance threshold', 'Query similarity', 'keep', 'The note matches the topic. The threshold accepts it in both worlds.'],
    ['Success-credit rule', 'Past co-exposure with successful answers', 'keep', 'The same recorded successes do not reveal whether the note was necessary or still valid.'],
    ['Age-based decay', 'Age and use history', 'archive', 'The same decay decision removes a stale rule in B and a still-useful warning in A.']
  ];
  panel.innerHTML = `<div class="center-title"><p class="eyebrow">02B / PUT THE RULE ON TRIAL</p>
    <h2>The score is the same.<br><em>The right action is not.</em></h2>
    <p>These are explicit mechanism controls, not native runs of named systems.<br>Try their commitments on this exact case. Changing a threshold can flip the choice, but cannot distinguish these two worlds.</p></div>
    <div class="method-table-scroll"><table class="method-table"><caption>Same visible evidence; two latent contexts; fixed keep/archive objective</caption>
    <thead><tr><th>Control / input</th><th>Rule in this fixture</th><th>World A</th><th>World B</th><th>Replay</th></tr></thead>
    <tbody>${methods.map(([name, input, action, reason]) => `<tr><th>${name}<small>${input}</small></th><td>${reason}</td>${currentWorlds().map(w => `<td class="${w[action].regret ? 'loss' : 'gain'}">${w[action].regret ? 'Regret' : 'Aligned'}<small>${w[action].outcome}</small></td>`).join('')}<td><button class="outline-button" data-control="${action}">Try ${action}</button></td></tr>`).join('')}
    <tr class="strong-control"><th>Evidence-aware control<small>Same source lookup or scoped check as SQCAD</small></th><td>Obtain distinguishing evidence, then choose per world. This control is allowed to succeed.</td><td class="gain">Conditional keep</td><td class="gain">Conditional archive</td><td><button class="outline-button" id="tryEvidenceControl">Try evidence</button></td></tr></tbody></table></div>
    <div class="fairness-note"><h3>Could an existing method avoid this?</h3><p>Yes—if it preserves the missing scope, asks a useful question, or estimates the relevant access effect. Then it has information outside this score-only comparison. The paper's Trivium audit is an informative negative case, not a method we should force to fail.</p>
    <p>The precise gap is <strong>using a proposal score as persistent authorization when compatible worlds require opposite actions</strong>. SQCAD makes that evidence boundary, the cost of checking, and the separation of temporary access from persistent permission explicit.</p>
    <a href="docs/guide.html#theory">Inspect the theorem, evidence boundary and control definitions ↗</a></div>`;
  $('investigate').before(panel);
  panel.querySelectorAll('[data-control]').forEach(button => button.addEventListener('click', () => {
    selectChoice(button.dataset.control);
    $('futures').scrollIntoView({behavior: reducedMotion() ? 'instant' : 'smooth'});
  }));
  $('tryEvidenceControl').addEventListener('click', () => {
    investigate('resolve');
    $('investigationResult').scrollIntoView({behavior: reducedMotion() ? 'instant' : 'smooth'});
  });
}

function renderEvidencePath(action) {
  const c = caseDetails[state.caseId];
  const success = action !== 'defer' && state.evidenceMode === 'decisive';
  const controls = action === 'defer' ? '' : `<fieldset class="evidence-modes"><legend>Stress-test the evidence check</legend>
    ${[['decisive','Useful evidence'],['inconclusive','No useful evidence'],['costly','Check too costly']].map(([id,label]) => `<button type="button" data-evidence-mode="${id}" aria-pressed="${state.evidenceMode === id}">${label}</button>`).join('')}</fieldset>`;
  const heading = action === 'defer' ? 'Pause the lasting change. Keep a route back.' : action === 'resolve' ? 'Recover the missing scope.' : 'Read once. Qualify before keeping.';
  const question = action === 'probe' ? c.check : c.lookup;
  const failure = action === 'defer' ? c.wait : state.evidenceMode === 'costly' ? c.costly : c.inconclusive;
  $('investigationResult').innerHTML = `<p class="eyebrow">COUNTERFACTUAL REWIND / ${action.toUpperCase()}</p><h3>${heading}</h3>
    <p>Return to the original decision point. Your earlier choice remains visible above; this alternative path does not undo a past outcome.</p>
    <ol class="path-steps"><li><strong>1 · Defer persistent change</strong><span>No new keep/archive authorization. Preserve source and provenance.</span></li><li><strong>2 · ${action === 'defer' ? 'Wait with a review route' : action === 'resolve' ? 'Inspect the source' : 'Allow a scoped check'}</strong><span>${action === 'defer' ? c.wait : question}</span></li><li><strong>3 · Qualify, then authorize</strong><span>Only evidence that resolves the decision in the correct scope can authorize a lasting change.</span></li></ol>
    ${controls}
    ${success ? `<div class="resolved-worlds">${currentWorlds().map((w,i) => {
      const best = i === 0 ? 'keep' : 'archive';
      const counter = best === 'keep' ? 'archive' : 'keep';
      return `<article><span class="small-label">WORLD ${w.id} / ${best.toUpperCase()} AFTER QUALIFICATION</span><blockquote>${action === 'resolve' ? w.source : w.probe}</blockquote>
        <p>${w.qualified}</p><h4>What the next task can now do</h4><blockquote>${w[best].answer}</blockquote><p>${w[best].outcome}</p>
        <div class="avoided"><strong>Avoided</strong><span>${w[counter].outcome}</span></div></article>`;
    }).join('')}</div><p class="cost-note">Conditional benefit in this scripted fixture: avoid the wrong memory commitment in either world, at the cost of the check and delay. This is not a measured zero-regret claim. The quotes stand in for sufficient domain evidence; production certificates require validated bounds and scope.</p>`
    : `<div class="pending-path"><h4>Still unresolved → Defer</h4><p>${failure}</p><p>${c.wait}</p><strong>No new persistent authorization; uncertainty stays visible.</strong><p>Deferral preserves the option to learn, but does not itself discover the truth. Delay can be costly. A probe that cannot reduce enough decision risk is not automatically worth buying.</p></div>`}
    <details class="ablation-note"><summary>Remove a component: what breaks?</summary><ul>
      <li><strong>Without an evidence route:</strong> deferring forever leaves this ambiguity unresolved.</li>
      <li><strong>Without a qualification gate:</strong> an inconclusive check can be mistaken for permission to keep.</li>
      <li><strong>Without scope/version checks:</strong> useful evidence from another patient, borrower or release can authorize the wrong memory.</li>
      <li><strong>Without temporary-access separation:</strong> retrieving the note once can silently promote it into every future task.</li>
    </ul><p>These are mechanism ablations of the explanation, not new benchmark measurements.</p></details>`;
  $('investigationResult').querySelectorAll('[data-evidence-mode]').forEach(b => b.addEventListener('click', () => {
    state.evidenceMode = b.dataset.evidenceMode;
    renderInvestigation(); renderInspector();
  }));
}

const caseDetails = {
  alex: {
    check: 'Ask Alex whether this constraint applies to Saturday; the note is read for this planning task only.',
    lookup: 'Open the dated conversation and recover the duration of the original request.',
    wait: 'Save an unbooked draft and ask for clarification before booking. No venue reservation and no new permanent preference.',
    inconclusive: 'Alex does not reply. Silence provides no evidence that the warning is valid or expired.',
    costly: 'The booking deadline is too close for a reliable check. Preserve uncertainty rather than inventing a preference.'
  },
  finance: {
    check: 'Request an authorized, read-only cash-flow reconciliation for this borrower and review date.',
    lookup: 'Recover the analyst note with borrower ID, review date and the condition under which the liquidity flag expires.',
    wait: 'Keep a manual credit-review task open. Do not infer loan approval from either keeping or archiving a memory flag.',
    inconclusive: 'The latest receivable record is missing. The old flag cannot be validated from another successful loan.',
    costly: 'The required review cannot be completed within the current evidence budget. Escalate rather than automatically approving.'
  },
  care: {
    check: 'Ask the authorized care team to review the current patient record and labs; the assistant never prescribes or administers a drug.',
    lookup: 'Recover the signed handoff, patient identity and clinician-defined review condition.',
    wait: 'Keep the refill request with the clinical team. Defer the memory-policy change; do not withhold, prescribe or declare treatment safe autonomously.',
    inconclusive: 'The current lab report is unavailable. An unanswered check is not clinical clearance.',
    costly: 'The needed clinical assessment is not available in this interaction. The request remains routed to a clinician.'
  },
  atlas: {
    check: 'Read the actual deployment manifest and credential-provider configuration without rotating or modifying credentials.',
    lookup: 'Recover the runbook migration note together with the target release and deployment-scope identifiers.',
    wait: 'Keep the release checklist provisional and route the credential question to the release owner.',
    inconclusive: 'The target manifest cannot be verified. The v3 name alone does not establish which credential workflow is active.',
    costly: 'Verifying the production target exceeds the available review window. Escalate the checklist item instead of trying a destructive rotation.'
  }
};

function renderBranches() {
  $('rootChoice').textContent = `You chose ${state.choice}`;
  $('switchChoice').textContent = `Try ${state.choice === 'keep' ? 'archive' : 'keep'} instead ↺`;
  $('branchGrid').innerHTML = currentWorlds().map(world => {
    const result = world[state.choice];
    return `<article class="future-card ${result.regret ? 'has-regret' : 'no-regret'}"><div class="scene-image"><img src="${world.image}" alt="${world.alt}" width="1536" height="1024"><span class="world-badge">POSSIBLE WORLD ${world.id}</span><span class="scene-caption">${world.id === 'A' ? 'THE COST OF A MISSING WARNING' : 'THE COST OF A STALE RESTRICTION'}</span></div><div class="future-content"><h3>${world.title}</h3><p class="hidden-truth">${world.truth}</p><ol class="consequence-chain"><li><span>YOUR ${state.choice.toUpperCase()}</span><p>${result.action}</p></li><li><span>THE AGENT SUGGESTS</span><blockquote>${result.answer}</blockquote></li><li><span>WHAT FOLLOWS</span><p>${result.outcome}</p></li></ol><div class="regret-status"><span aria-hidden="true">${result.regret ? '↯' : '✓'}</span><div><strong>${result.regret ? 'Regret in this world' : 'Aligned in this world'}</strong><small>Qualitative comparison against the correct keep/archive action.</small></div></div><p class="future-echo">${result.future}</p></div></article>`;
  }).join('');
  $('branchGrid').querySelectorAll('.scene-caption').forEach((node, index) => {
    const captions = activeCase().branchCaptions;
    if (captions?.[index]) node.textContent = captions[index];
  });
}

function investigate(action) {
  if (!state.revealed) return;
  state.investigation = action;
  state.evidenceMode = 'decisive';
  renderInvestigation();
  renderInspector();
}

function renderInvestigation() {
  const action = state.investigation;
  document.querySelectorAll('[data-investigation]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.investigation === action)));
  $('investigationResult').hidden = !action;
  if (!action) return;
  renderEvidencePath(action);
}

function renderInspector() {
  const qualified = state.investigation && state.investigation !== 'defer' && state.evidenceMode === 'decisive';
  $('qualificationState').textContent = qualified ? 'Scope supported, per world' : 'Unresolved';
  $('authorizationState').textContent = qualified ? 'A: keep / B: archive' : state.investigation ? 'Defer; no new authorization' : (state.choice ? `${state.choice} (visitor choice)` : 'Not selected');
  $('accessState').textContent = state.investigation === 'probe' ? 'Temporary scoped read; expired' : state.investigation === 'resolve' ? 'Source inspection' : 'No probe';
  $('auditTrace').textContent = state.investigation ? `Counterfactual rewind → defer persistent change → ${state.investigation} → ${qualified ? 'qualify scope → conditional authorization' : 'insufficient evidence → defer / review'}.` : `Source note → relevance proposal → ${state.choice || 'decision pending'}${state.revealed ? ' → opposite consequences in two latent worlds' : ''}.`;
}

function reset() {
  state.choice = null; state.revealed = false; state.investigation = null;
  $('futures').hidden = true; $('investigate').hidden = true;
  $('branchGrid').replaceChildren(); $('investigationResult').replaceChildren();
  $('methodContrast')?.remove();
  state.evidenceMode = 'decisive';
  $('revealBtn').disabled = true; $('revealBtn').innerHTML = 'Reveal the possible futures <span aria-hidden="true">↓</span>';
  $('choiceFeedback').textContent = 'The source survives either way. Your choice changes its future exposure.';
  document.querySelectorAll('[data-choice]').forEach(button => button.setAttribute('aria-pressed', 'false'));
  $('technicalDetails').open = false;
  renderInvestigation(); renderInspector();
  $('experiment').scrollIntoView({ behavior: reducedMotion() ? 'instant' : 'smooth' });
}
function reducedMotion() { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
document.querySelectorAll('[data-choice]').forEach(button => button.addEventListener('click', () => selectChoice(button.dataset.choice)));
document.querySelectorAll('[data-investigation]').forEach(button => button.addEventListener('click', () => investigate(button.dataset.investigation)));
$('revealBtn').addEventListener('click', reveal);
$('switchChoice').addEventListener('click', () => selectChoice(state.choice === 'keep' ? 'archive' : 'keep'));
$('resetBtn').addEventListener('click', reset);
renderCasePicker();
renderCase();
renderInspector();
// Keep the browser experience on the standalone guide even when an older fixture link remains.
document.querySelectorAll('a[href*="TECHNICAL_GUIDE.md"]').forEach((link) => {
  link.href = link.href.replace('TECHNICAL_GUIDE.md', 'guide.html');
});
