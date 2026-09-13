// UI state belongs to this replay, not to a deployed memory controller.
const futureOptions = {horizon:3,gamma:.9,pA:.5,pA1:.5,pB1:.5,policy:'reuse'};
const number = n => `${n > 0 ? '+' : ''}${n.toFixed(2)}`;
const art = (kind, panel) => `assets/${state.caseId}-${kind}-${panel}.webp`;

function continuationControls(world) {
  const open = state.expandedWorlds.includes(world.id);
  return `<div class="continuation"><button class="outline-button" type="button" data-expand-world="${world.id}" aria-expanded="${open}">${open ? 'Hide' : 'Follow'} ${world.id}'s next tasks <span aria-hidden="true">↳</span></button>
    ${open ? `<div class="child-fork" aria-label="Two continuations of world ${world.id}">${[1,2].map(n => {
      const id = world.id+n, text = SQFuture.stories[state.caseId][id];
      return `<button class="leaf-card" type="button" data-leaf="${id}" aria-pressed="${state.leaf === id}"><img loading="lazy" src="${art('future',id)}" alt="${text[0]}" width="1024" height="1024"><span class="leaf-copy"><small>POSSIBLE FUTURE ${id} · TASKS 2–3</small><strong>${text[0]}</strong><span>${text[2]}</span><em>Follow this path ↗</em></span></button>`;
    }).join('')}</div>` : ''}</div>`;
}

function bindContinuations() {
  document.querySelectorAll('[data-expand-world]').forEach(b => b.addEventListener('click', () => {
    const id = b.dataset.expandWorld;
    state.expandedWorlds = state.expandedWorlds.includes(id) ? state.expandedWorlds.filter(x=>x!==id) : [...state.expandedWorlds,id];
    renderBranches();
  }));
  document.querySelectorAll('[data-leaf]').forEach(b => b.addEventListener('click', () => {
    state.leaf = b.dataset.leaf;
    renderBranches();
    $('trajectory').scrollIntoView({behavior:reducedMotion()?'instant':'smooth',block:'start'});
  }));
  renderTrajectory();
  $('whatAboutProbe').disabled = !state.leaf;
}

function renderTrajectory() {
  const target = $('trajectory');
  target.hidden = !state.leaf;
  $('valueLandscape').hidden = !state.leaf;
  if (!state.leaf) return;
  const id = state.leaf, s = SQFuture.stories[state.caseId][id];
  const k = SQFuture.steps(id,'keep',futureOptions.policy), a = SQFuture.steps(id,'archive',futureOptions.policy);
  const delta = SQFuture.value(id,'keep',futureOptions)-SQFuture.value(id,'archive',futureOptions);
  target.innerHTML = `<div class="trajectory-cover"><img src="${art('future',id)}" alt="${s[0]}" width="1024" height="1024"><div><p class="eyebrow">YOU FOLLOWED ${id} / INITIAL ${state.choice.toUpperCase()}</p><h3>${s[0]}</h3><p>Keep and Archive below share this task sequence and the same continuation policy. They differ in exposure, cost and what can be recovered.</p><span class="small-label">HYPOTHETICAL TEACHING UNITS · NOT MEASURED RESULTS</span></div></div>
    <div class="task-ledger">${[1,2,3].map((t,i)=>{
      const ku = k[i][0]-k[i][1]-k[i][2], au = a[i][0]-a[i][1]-a[i][2];
      return `<article class="${t>futureOptions.horizon?'beyond-horizon':''}"><span class="small-label">TASK ${t}${t>futureOptions.horizon?' / OUTSIDE SELECTED H':''}</span><p>${s[t]}</p><div class="paired-utility"><span>Keep <b>${number(ku)}</b></span><span>Archive <b>${number(au)}</b></span></div><small>Task contrast: ${number(ku-au)} · before discounting</small></article>`;
    }).join('')}</div><div class="trajectory-verdict"><strong>${id}: G(Keep) − G(Archive) = ${number(delta)}</strong><p>${id==='B1'?'The first missed opportunity remains a loss. Later tasks can make retention useful again; increasing the horizon can even reverse the cumulative contrast.':id==='A2'?'A useful warning can become irrelevant on later tasks. Exposure costs continue even when there is no obvious harmful answer.':'Following more tasks can accumulate the effect of a memory decision.'} This path return is one term in an expectation, not the expectation itself.</p></div>`;
  renderLandscape();
}

function renderLandscape() {
  const weights = SQFuture.weights(futureOptions.pA,futureOptions.pA1,futureOptions.pB1);
  const vk = SQFuture.aggregate('keep',futureOptions), va = SQFuture.aggregate('archive',futureOptions);
  const dA = futureOptions.pA1*(SQFuture.value('A1','keep',futureOptions)-SQFuture.value('A1','archive',futureOptions))+(1-futureOptions.pA1)*(SQFuture.value('A2','keep',futureOptions)-SQFuture.value('A2','archive',futureOptions));
  const dB = futureOptions.pB1*(SQFuture.value('B1','keep',futureOptions)-SQFuture.value('B1','archive',futureOptions))+(1-futureOptions.pB1)*(SQFuture.value('B2','keep',futureOptions)-SQFuture.value('B2','archive',futureOptions));
  $('valueRows').innerHTML = Object.keys(weights).map(id => `<tr><th>${id}<small>${SQFuture.stories[state.caseId][id][0]}</small></th><td>${(weights[id]*100).toFixed(1)}%</td><td>${number(SQFuture.value(id,'keep',futureOptions))}</td><td>${number(SQFuture.value(id,'archive',futureOptions))}</td><td>${number(SQFuture.value(id,'keep',futureOptions)-SQFuture.value(id,'archive',futureOptions))}</td></tr>`).join('');
  $('valueTotals').innerHTML = `<div><span>V<sup>π</sup>(Keep)</span><strong>${number(vk)}</strong></div><div><span>V<sup>π</sup>(Archive)</span><strong>${number(va)}</strong></div><div><span>τ<sup>π</sup> = V<sup>π</sup>(Keep) − V<sup>π</sup>(Archive)</span><strong>${number(vk-va)}</strong></div>`;
  $('fiberResult').innerHTML = `<strong>Within A: τ = ${number(dA)}. Within B: τ = ${number(dB)}.</strong><p>${dA*dB<0 ? 'The two conditional contrasts have opposite signs under these declared assumptions. A score-only commitment that cannot tell A from B cannot select the best action in both.' : 'These assumptions do not produce opposite signs. This setting does NOT establish the score-fiber theorem’s premise. An evidence-aware retrieval strategy is allowed to remove this example’s collision.'}</p><p>The displayed belief mixture over A and B is different from the theorem’s worst-case comparison between states. A single unlucky path does not prove either expected or worst-case commitment regret.</p>`;
  $('payoffRows').innerHTML = Object.keys(weights).flatMap(id=>['keep','archive'].map(action=>`<tr><th>${id} / ${action}</th>${SQFuture.steps(id,action,futureOptions.policy).map(row=>`<td>(${row.join(', ')})</td>`).join('')}</tr>`)).join('');
  for (const id of ['pA','pA1','pB1']) $(id+'Output').textContent = Math.round(futureOptions[id]*100)+'%';
  $('gammaOutput').textContent = futureOptions.gamma.toFixed(2);
}

function initFutureView() {
  $('trajectory').before(document.createTextNode(''));
  $('branchGrid').after($('trajectory'));
  $('trajectory').after($('whatAboutProbe'));
  $('whatAboutProbe').addEventListener('click',()=>{
    $('investigate').hidden = false;
    $('investigate').scrollIntoView({behavior:reducedMotion()?'instant':'smooth',block:'start'});
  });
  for (const id of ['pA','pA1','pB1','gamma','horizon','policy']) $(id).addEventListener('input',()=>{
    futureOptions[id] = id==='policy'?$(id).value:Number($(id).value);
    $('horizonOutput').textContent = futureOptions.horizon;
    renderTrajectory();
  });
}

function renderEvidenceTree(action) {
  const selected = state.evidenceBranch;
  const lookup = action === 'resolve', waiting = action === 'defer';
  const definitions = waiting ? [
    ['arrives','A later review brings evidence','The pending task reaches an authorized reviewer. A fresh, scoped observation can now support a conditional action.','probe'],
    ['silent','No new observation','Silence leaves qualification unresolved. Preserve the review task; do not infer truth from waiting.','uncertain'],
    ['deadline','The window closes','The review remains unresolved while an opportunity or service window is lost. Deferral has a real cost.','delay']
  ] : [
    ['useful',lookup?'The source resolves the scope':'A scoped check is informative',lookup?caseDetails[state.caseId].lookup:caseDetails[state.caseId].check,lookup?'resolve':'probe'],
    ['uncertain',lookup?'The source is incomplete':'The answer is inconclusive',caseDetails[state.caseId].inconclusive,'uncertain'],
    ['mismatch','Evidence from the wrong scope','A plausible result belongs to another date, identity or deployment. Qualification rejects its use for this decision.','resolve'],
    ['deadline','The check misses its window',caseDetails[state.caseId].costly,'delay']
  ];
  $('investigationResult').innerHTML = `<div class="evidence-stage-heading"><p class="eyebrow">COUNTERFACTUAL REWIND / ${action.toUpperCase()}</p><h3>${waiting?'Wait, then follow what happens.':lookup?'Recover the source. Follow its possible answers.':'Ask once. Follow the possible answers.'}</h3><p>Return to the original decision point, before any lasting commitment. The original Keep/Archive path stays intact above. Choose an illustrated observation branch below; this is a replay, not a live query.</p><p class="cost-note">${waiting?caseDetails[state.caseId].wait:'The check may inspect the source for this task only. Reading it does not grant permanent exposure.'}</p></div>
    <div class="evidence-tree">${definitions.map(([id,title,description,panel])=>`<button type="button" class="leaf-card" data-observation="${id}" aria-pressed="${selected===id}"><img src="${art('evidence',panel)}" alt="${title}" width="1024" height="1024" loading="lazy"><span class="leaf-copy"><small>${action.toUpperCase()} → ${id.toUpperCase()}</small><strong>${title}</strong><span>${description}</span><em>Reveal this future ↗</em></span></button>`).join('')}</div><div id="evidenceContinuation" ${selected?'':'hidden'}></div>`;
  document.querySelectorAll('[data-observation]').forEach(b=>b.addEventListener('click',()=>{
    state.evidenceBranch=b.dataset.observation; state.qualifiedChoices={};
    renderInvestigation(); renderInspector();
    $('evidenceContinuation').scrollIntoView({behavior:reducedMotion()?'instant':'smooth',block:'start'});
  }));
  if (selected) renderEvidenceContinuation();
}

function renderEvidenceContinuation() {
  const qualified = ['useful','arrives'].includes(state.evidenceBranch);
  const c=caseDetails[state.caseId];
  $('evidenceContinuation').innerHTML = qualified ? `<div class="qualification-gate"><span class="small-label">EVIDENCE → QUALIFICATION → AUTHORIZATION</span><h3>Now choose within each supported scope.</h3><p>For this authored replay, assume the check also yields a sufficient sign certificate for the next authorization scope. A quote about validity alone does not establish a full-horizon value certificate. Actual SQCAD needs audited value bounds, costs and scope.</p></div><div class="resolved-worlds">${currentWorlds().map(w=>{
    const choice=state.qualifiedChoices[w.id], best=w.id==='A'?'keep':'archive';
    return `<article class="qualified-world"><span class="small-label">OBSERVATION ${w.id} / ${best.toUpperCase()} SUPPORTED IN THE DECLARED SCOPE</span><blockquote>${state.investigation==='resolve'?w.source:w.probe}</blockquote><div class="conditional-actions">${['keep','archive'].map(a=>`<button type="button" data-qualified-world="${w.id}" data-qualified-choice="${a}" aria-pressed="${choice===a}">${a==='keep'?'✧ Keep':'◇ Archive'}</button>`).join('')}<button type="button" data-qualified-world="${w.id}" data-qualified-choice="defer" aria-pressed="${choice==='defer'}">Defer</button></div>${choice?`<div class="qualified-outcome"><img src="${choice==='defer'?art('evidence','delay'):choice===best?art('future',w.id+'1'):w.image}" alt="${choice==='defer'?'A review remains pending':w[choice].outcome}" width="1024" height="1024"><h4>${choice==='defer'?'The decision remains pending':choice===best?'A supported action in this scope':'An unsupported commitment'}</h4><p>${choice==='defer'?c.wait:w[choice].outcome}</p><p>${choice==='defer'?'Even with useful evidence, waiting may incur delay.':choice===best?'The relevant error is avoided on this next task, while evidence and review still cost time. Later tasks must be checked in their own scope.':'This choice overrides the assumed certificate. The simulator lets you inspect the consequence; SQCAD would not authorize it.'}</p><small>The earlier root choice remains ${state.choice}. No past loss is erased.</small></div>`:'<p class="cost-note">Select a lasting action to reveal its illustrated outcome.</p>'}</article>`;
  }).join('')}</div>` : `<div class="pending-path"><img class="pending-art" src="${art('evidence',state.evidenceBranch==='deadline'?'delay':'uncertain')}" alt="A pending review with no sufficient evidence" width="1024" height="1024"><p class="small-label">QUALIFICATION UNRESOLVED / NO NEW PERSISTENT AUTHORIZATION</p><h3>${state.evidenceBranch==='mismatch'?'A relevant answer from the wrong world.':state.evidenceBranch==='deadline'?'Waiting has a consequence.':'No answer is not an answer.'}</h3><p>${state.evidenceBranch==='deadline'?c.costly:state.evidenceBranch==='mismatch'?'The retrieved evidence does not match this identity, time or version. It cannot authorize a lasting change.':c.inconclusive}</p><p>${c.wait}</p><div class="conditional-actions"><button type="button" data-next-route="defer">Defer & follow the waiting branch ↗</button><button type="button" data-next-route="${state.investigation==='resolve'?'probe':'resolve'}">Try ${state.investigation==='resolve'?'Probe':'Resolve'} instead ↗</button></div><p class="cost-note">A second check needs its own cost and evidence budget. No route guarantees a successful answer.</p></div>`;
  document.querySelectorAll('[data-qualified-choice]').forEach(b=>b.addEventListener('click',()=>{
    state.qualifiedChoices[b.dataset.qualifiedWorld]=b.dataset.qualifiedChoice;
    renderEvidenceContinuation(); renderInspector();
  }));
  document.querySelectorAll('[data-next-route]').forEach(b=>b.addEventListener('click',()=>investigate(b.dataset.nextRoute)));
}

initFutureView();
