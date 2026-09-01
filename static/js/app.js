// Drives the multi-step form: step visibility, participant ID / duplicate
// prevention, word-count warnings, and the fetch calls to the Flask API.
// No framework — just DOM lookups by id/name, on purpose, so it's easy to
// read top to bottom.

const PARTICIPANT_ID_KEY = "aivs_participant_id";
const COMPLETED_KEY = "aivs_completed";

function getParticipantId() {
  let id = localStorage.getItem(PARTICIPANT_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(PARTICIPANT_ID_KEY, id);
  }
  return id;
}

function showStep(id) {
  document.querySelectorAll(".step").forEach((el) => el.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  window.scrollTo(0, 0);
}

function getRadioValue(name) {
  const el = document.querySelector(`input[name="${name}"]:checked`);
  return el ? el.value : null;
}

function collectLikertRange(prefix, count) {
  const values = [];
  for (let i = 1; i <= count; i++) {
    const v = getRadioValue(`${prefix}_${i}`);
    values.push(v === null ? null : parseInt(v, 10));
  }
  return values;
}

function wordCount(text) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

async function postJSON(url, body, extraHeaders) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(extraHeaders || {}) },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    // Attach the parsed JSON body (if there is one) to the thrown error so
    // callers can distinguish known failure modes (e.g. the AI provider's
    // daily quota) from unexpected ones, instead of every failure looking
    // the same.
    let errorBody = null;
    try {
      errorBody = await res.json();
    } catch (e) {
      // response wasn't JSON (e.g. a generic 500 HTML error page) — fine,
      // errorBody just stays null and callers fall back to a generic message
    }
    const err = new Error(`Request to ${url} failed: ${res.status}`);
    err.status = res.status;
    err.body = errorBody;
    throw err;
  }
  return res.json();
}

const participantId = getParticipantId();

document.addEventListener("DOMContentLoaded", () => {
  if (localStorage.getItem(COMPLETED_KEY) === "true") {
    showStep("already-participated");
    return;
  }

  // --- Step 0: consent ---
  const consentCheckbox = document.getElementById("consent-checkbox");
  const consentContinue = document.getElementById("consent-continue");
  consentCheckbox.addEventListener("change", () => {
    consentContinue.disabled = !consentCheckbox.checked;
  });
  consentContinue.addEventListener("click", async () => {
    await postJSON("/api/consent", {
      participant_id: participantId,
      recruitment_source: window.STUDY_META.recruitmentSource,
    });
    showStep("step-1");
  });

  // --- Step 1: covariates ---
  document.getElementById("step1-continue").addEventListener("click", async () => {
    const errorEl = document.getElementById("step1-error");
    errorEl.textContent = "";

    const aiUse = getRadioValue("ai_use_frequency");
    const techAffinity = [1, 2, 3].map((i) => getRadioValue(`tech_affinity_${i}`));
    const finLitAnswers = window.STUDY_META.financialLiteracyAnswers.map((_, i) =>
      getRadioValue(`fin_lit_${i}`)
    );
    const finLitSelf = getRadioValue("fin_lit_self_rating");
    const age = document.getElementById("age").value;
    const gradeYear = document.getElementById("grade_year").value.trim();

    if (
      !aiUse ||
      techAffinity.includes(null) ||
      finLitAnswers.includes(null) ||
      !finLitSelf ||
      !age ||
      !gradeYear
    ) {
      errorEl.textContent = "Please answer every question before continuing.";
      return;
    }

    // Backs up the age attestation on the Step 0 consent checkbox with an
    // actual check against the age entered here, in case of a mismatch.
    if (parseInt(age, 10) < window.STUDY_META.minimumAge) {
      errorEl.textContent =
        `Our records indicate you are under ${window.STUDY_META.minimumAge}. ` +
        "Unfortunately we're unable to include participants under that age in this study. " +
        "Thank you for your interest.";
      return;
    }

    const finLitCorrect = finLitAnswers.map(
      (ans, i) => parseInt(ans, 10) === window.STUDY_META.financialLiteracyAnswers[i]
    );

    await postJSON("/api/covariates", {
      participant_id: participantId,
      ai_use_frequency: parseInt(aiUse, 10),
      tech_affinity: techAffinity.map((v) => parseInt(v, 10)),
      fin_lit_correct: finLitCorrect,
      fin_lit_self_rating: parseInt(finLitSelf, 10),
      age: parseInt(age, 10),
      grade_year: gradeYear,
    });
    showStep("step-2");
  });

  // --- Step 2: scenario + initial stance ---
  const preRationale = document.getElementById("pre_rationale");
  const preWarning = document.getElementById("pre_rationale_warning");
  preRationale.addEventListener("input", () => {
    preWarning.hidden = wordCount(preRationale.value) >= 20;
  });

  document.getElementById("step2-continue").addEventListener("click", async () => {
    const stance = getRadioValue("pre_stance");
    const confidence = getRadioValue("pre_confidence");
    const rationale = preRationale.value.trim();
    if (!stance || !confidence || !rationale) return;

    showStep("step-loading");

    // Randomization happens server-side in /api/submit-stance — see
    // randomization.py and app.py for the guarantee. This call sends
    // the participant's answer; the server draws the condition BEFORE
    // it even reads that answer out of the request body.
    await postJSON(
      "/api/submit-stance",
      { stance, confidence: parseInt(confidence, 10), rationale },
      { "X-Participant-Id": participantId }
    );

    let verdict;
    try {
      ({ verdict } = await postJSON("/api/generate-verdict", {
        participant_id: participantId,
      }));
    } catch (err) {
      // Without this, a failure here (e.g. the AI provider's daily quota
      // being used up) left participants stuck on "Generating your
      // second opinion..." forever with no explanation. Show whatever
      // message the server gave for known failure modes, or a generic
      // one otherwise — either way, never leave them on a silent spinner.
      const loadingError = document.getElementById("loading-error");
      loadingError.textContent =
        (err.body && err.body.message) ||
        "Something went wrong generating your response. Please try refreshing the page in a few minutes, or contact the researcher if this keeps happening.";
      loadingError.hidden = false;
      return;
    }
    document.getElementById("verdict-text").textContent = verdict;
    // Also populate the collapsible reference copy on Step 6, so
    // participants can re-read the verdict while answering the
    // post-verdict questions instead of relying on memory.
    document.getElementById("verdict-reference-text").textContent = verdict;
    showStep("step-5");
  });

  // --- Step 5: verdict display ---
  document.getElementById("step5-continue").addEventListener("click", () => {
    showStep("step-6");
  });

  // --- Step 6: post-verdict measures ---
  const postRationale = document.getElementById("post_rationale");
  const postWarning = document.getElementById("post_rationale_warning");
  postRationale.addEventListener("input", () => {
    postWarning.hidden = wordCount(postRationale.value) >= 20;
  });

  document.getElementById("step6-continue").addEventListener("click", async () => {
    const errorEl = document.getElementById("step6-error");
    errorEl.textContent = "";

    const stance = getRadioValue("post_stance");
    const confidence = getRadioValue("post_confidence");
    const rationale = postRationale.value.trim();
    const { trust, competence, bias, intention } = window.STUDY_META.scaleCounts;
    const trustItems = collectLikertRange("trust", trust);
    const competenceItems = collectLikertRange("competence", competence);
    const biasItems = collectLikertRange("bias", bias);
    const intentionItems = collectLikertRange("intention", intention);

    const allScalesAnswered = [trustItems, competenceItems, biasItems, intentionItems].every(
      (arr) => !arr.includes(null)
    );

    if (!stance || !confidence || !rationale || !allScalesAnswered) {
      errorEl.textContent = "Please answer every question before continuing.";
      return;
    }

    await postJSON("/api/post-verdict", {
      participant_id: participantId,
      stance,
      confidence: parseInt(confidence, 10),
      rationale,
      trust_items: trustItems,
      competence_items: competenceItems,
      bias_items: biasItems,
      intention_items: intentionItems,
    });

    // The debrief text (config.py) contains the literal token
    // "{{PARTICIPANT_ID}}" where the participant's real ID should appear —
    // substitute it in now, since the ID isn't known server-side at the
    // time the page was first rendered.
    const debriefBlock = document.querySelector("#step-7 .content-block");
    debriefBlock.textContent = debriefBlock.textContent.replace(
      "{{PARTICIPANT_ID}}",
      participantId
    );

    showStep("step-7");
  });

  // --- Step 7: debrief ---
  document.getElementById("step7-finish").addEventListener("click", async () => {
    const feedback = document.getElementById("debrief_feedback").value.trim();
    await postJSON("/api/debrief-feedback", {
      participant_id: participantId,
      feedback,
    });
    localStorage.setItem(COMPLETED_KEY, "true");
    showStep("step-done");
  });
});
