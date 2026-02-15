/* ============================================================
   DTIC Uniqueness Analyzer — Frontend Logic
   ============================================================ */

// State
let currentMarkdown = "";
let elapsedTimer = null;
let stageTimer = null;

// Elements
const form = document.getElementById("analyze-form");
const submitBtn = document.getElementById("submit-btn");
const loadingSection = document.getElementById("loading");
const resultsSection = document.getElementById("results");
const errorSection = document.getElementById("error");
const formSection = document.getElementById("form-section");
const howSection = document.getElementById("how-it-works");

// Abstract character counter
const abstractField = document.getElementById("abstract");
const abstractCount = document.getElementById("abstract-count");

abstractField.addEventListener("input", () => {
  const len = abstractField.value.length;
  abstractCount.textContent = `${len.toLocaleString()} character${len !== 1 ? "s" : ""}`;
});

// Verdict display labels
const VERDICT_LABELS = {
  UNIQUE: "Unique",
  NAVY_UNIQUE: "Navy Unique",
  AT_RISK: "At Risk",
  NEEDS_REVIEW: "Needs Review",
};

// ---- Loading stage progression ----

const STAGES = ["stage-search", "stage-embed", "stage-analyze", "stage-report"];
const STAGE_TIMES = [0, 15000, 45000, 90000]; // estimated ms for each stage start
const STAGE_PROGRESS = [10, 35, 65, 85]; // progress bar values

function startLoadingAnimation() {
  const startTime = Date.now();

  // Reset stages
  STAGES.forEach((id) => {
    document.getElementById(id).setAttribute("data-status", "pending");
  });
  document.getElementById("loading-bar").style.width = "0%";
  document.getElementById("loading-elapsed").textContent = "0:00";

  // Elapsed timer
  elapsedTimer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const min = Math.floor(elapsed / 60);
    const sec = String(elapsed % 60).padStart(2, "0");
    document.getElementById("loading-elapsed").textContent = `${min}:${sec}`;
  }, 1000);

  // Stage progression (simulated based on typical timing)
  let currentStage = 0;

  function advanceStage() {
    if (currentStage >= STAGES.length) return;

    // Mark previous stages as done
    for (let i = 0; i < currentStage; i++) {
      document.getElementById(STAGES[i]).setAttribute("data-status", "done");
    }

    // Mark current as active
    document.getElementById(STAGES[currentStage]).setAttribute("data-status", "active");
    document.getElementById("loading-bar").style.width = STAGE_PROGRESS[currentStage] + "%";

    currentStage++;

    if (currentStage < STAGES.length) {
      const nextDelay = STAGE_TIMES[currentStage] - STAGE_TIMES[currentStage - 1];
      stageTimer = setTimeout(advanceStage, nextDelay);
    }
  }

  advanceStage();
}

function stopLoadingAnimation() {
  clearInterval(elapsedTimer);
  clearTimeout(stageTimer);

  // Mark all stages done
  STAGES.forEach((id) => {
    document.getElementById(id).setAttribute("data-status", "done");
  });
  document.getElementById("loading-bar").style.width = "100%";
}

// ---- Form submission ----

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const keywordsRaw = form.keywords.value.trim();
  const keywords = keywordsRaw ? keywordsRaw.split(",").map((k) => k.trim()).filter(Boolean) : [];

  const payload = {
    title: form.title.value.trim(),
    abstract: form.abstract.value.trim(),
    keywords: keywords,
    military_branch: form.military_branch.value,
    additional_context: form.additional_context.value.trim(),
  };

  // Transition to loading state
  resultsSection.classList.add("hidden");
  errorSection.classList.add("hidden");
  formSection.classList.add("hidden");
  howSection.classList.add("hidden");
  loadingSection.classList.remove("hidden");
  submitBtn.disabled = true;

  startLoadingAnimation();

  // Scroll to loading
  loadingSection.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const resp = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`Server returned ${resp.status}: ${text}`);
    }

    const data = await resp.json();

    stopLoadingAnimation();

    // Brief pause for the final stage animation
    await new Promise((r) => setTimeout(r, 400));

    showResults(data);
  } catch (err) {
    stopLoadingAnimation();
    showError(err.message);
  } finally {
    loadingSection.classList.add("hidden");
    submitBtn.disabled = false;
  }
});

// ---- Results display ----

function showResults(data) {
  currentMarkdown = data.markdown || "";

  // Verdict card
  const verdictCard = document.getElementById("verdict-card");
  verdictCard.className = "verdict-card " + data.verdict;

  document.getElementById("verdict-value").textContent =
    VERDICT_LABELS[data.verdict] || data.verdict;

  document.getElementById("verdict-confidence").textContent =
    `Confidence: ${Math.round(data.confidence * 100)}%`;

  document.getElementById("verdict-summary").textContent = data.summary || "";

  // Render markdown report
  const reportEl = document.getElementById("report-content");
  if (typeof marked !== "undefined" && currentMarkdown) {
    reportEl.innerHTML = marked.parse(currentMarkdown);
  } else {
    reportEl.textContent = currentMarkdown;
  }

  resultsSection.classList.remove("hidden");
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---- Error display ----

function showError(message) {
  document.getElementById("error-message").textContent = message;
  errorSection.classList.remove("hidden");
  formSection.classList.remove("hidden");
  howSection.classList.remove("hidden");
  errorSection.scrollIntoView({ behavior: "smooth", block: "center" });
}

// ---- Action buttons ----

document.getElementById("download-btn").addEventListener("click", () => {
  if (!currentMarkdown) return;
  const blob = new Blob([currentMarkdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "dtic_uniqueness_report.md";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});

document.getElementById("new-analysis-btn").addEventListener("click", () => {
  resultsSection.classList.add("hidden");
  formSection.classList.remove("hidden");
  howSection.classList.remove("hidden");
  formSection.scrollIntoView({ behavior: "smooth", block: "start" });
});

document.getElementById("retry-btn").addEventListener("click", () => {
  errorSection.classList.add("hidden");
  formSection.scrollIntoView({ behavior: "smooth", block: "start" });
});
