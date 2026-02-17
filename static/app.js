/* ============================================================
   Uncharted Waters Explorer — Frontend Logic
   ============================================================ */

// Configure marked.js to treat single newlines as <br> (safety net)
if (typeof marked !== "undefined") {
  marked.setOptions({ breaks: true });
}

// Add target="_blank" to all external links (skip internal anchors)
function openLinksInNewTab(html) {
  return html.replace(/<a href="(?!#)/g, '<a target="_blank" rel="noopener noreferrer" href="');
}

// State
let currentMarkdown = "";
let elapsedTimer = null;
let stageTimer = null;
let chartInstances = [];

// Elements
const form = document.getElementById("analyze-form");
const submitBtn = document.getElementById("submit-btn");
const loadingSection = document.getElementById("loading");
const resultsSection = document.getElementById("results");
const errorSection = document.getElementById("error");
const formSection = document.getElementById("form-section");
const howSection = document.getElementById("how-it-works");

// Verdict display labels
const VERDICT_LABELS = {
  UNIQUE: "Open Landscape",
  NAVY_UNIQUE: "Branch Opportunity",
  AT_RISK: "Well Covered",
  NEEDS_REVIEW: "Mixed Coverage",
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
    topic_description: (form.topic_description ? form.topic_description.value.trim() : ""),
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
    const resp = await fetch("/api/explore", {
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

  // Branch relevance indicator
  const relEl = document.getElementById("verdict-relevance");
  const br = (data.report && data.report.branch_relevance) || "";
  const brReason = (data.report && data.report.branch_relevance_reasoning) || "";
  if (br === "branch_specific") {
    relEl.textContent = "Branch-Specific — " + brReason;
    relEl.className = "verdict-relevance branch-specific";
  } else if (br === "cross_branch") {
    relEl.textContent = "Cross-Branch Applicable — " + brReason;
    relEl.className = "verdict-relevance cross-branch";
  } else {
    relEl.textContent = "";
  }

  // Show executive summary in the verdict card, rendered as HTML
  const fullSummary = data.summary || "";
  const verdictSummaryEl = document.getElementById("verdict-summary");
  if (typeof marked !== "undefined" && fullSummary) {
    verdictSummaryEl.innerHTML = openLinksInNewTab(marked.parse(fullSummary));
  } else {
    verdictSummaryEl.textContent = fullSummary;
  }

  // Render charts
  renderCharts(data);

  // Render markdown report
  const reportEl = document.getElementById("report-content");
  if (typeof marked !== "undefined" && currentMarkdown) {
    reportEl.innerHTML = openLinksInNewTab(marked.parse(currentMarkdown));
  } else {
    reportEl.textContent = currentMarkdown;
  }

  resultsSection.classList.remove("hidden");
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---- Charts ----

function getVerdictColor(verdict) {
  const colors = {
    UNIQUE: "#3ecf8e",
    NAVY_UNIQUE: "#5ba4f5",
    AT_RISK: "#f07178",
    NEEDS_REVIEW: "#f0c674",
  };
  return colors[verdict] || "#6b8baf";
}

function getOverlapColor(rating) {
  const r = (rating || "").toLowerCase();
  if (r === "low") return "#3ecf8e";
  if (r === "medium") return "#f0c674";
  if (r === "high") return "#f07178";
  return "#6b8baf";
}

function renderCharts(data) {
  if (typeof Chart === "undefined") return;

  const dashboard = document.getElementById("charts-dashboard");

  // Destroy previous chart instances
  chartInstances.forEach((c) => c.destroy());
  chartInstances = [];

  const comparisons = (data.report && data.report.comparisons) || [];
  if (comparisons.length === 0 && !data.confidence) {
    dashboard.classList.add("hidden");
    return;
  }
  dashboard.classList.remove("hidden");

  const confidence = data.confidence || 0;
  const verdict = data.verdict || "NEEDS_REVIEW";
  const verdictColor = getVerdictColor(verdict);

  // --- 1. Confidence Gauge (doughnut) ---
  const confCtx = document.getElementById("chart-confidence").getContext("2d");
  const confPct = Math.round(confidence * 100);
  chartInstances.push(
    new Chart(confCtx, {
      type: "doughnut",
      data: {
        datasets: [
          {
            data: [confPct, 100 - confPct],
            backgroundColor: [verdictColor, "rgba(30, 47, 69, 0.5)"],
            borderWidth: 0,
          },
        ],
      },
      options: {
        cutout: "75%",
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: { enabled: false },
        },
      },
      plugins: [
        {
          id: "centerText",
          afterDraw(chart) {
            const { ctx, chartArea } = chart;
            const cx = (chartArea.left + chartArea.right) / 2;
            const cy = (chartArea.top + chartArea.bottom) / 2;
            ctx.save();
            ctx.font = "600 1.4rem 'IBM Plex Mono', monospace";
            ctx.fillStyle = verdictColor;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(`${confPct}%`, cx, cy);
            ctx.restore();
          },
        },
      ],
    })
  );

  // --- 2. Overlap Rating Breakdown (doughnut) ---
  const overlapCtx = document.getElementById("chart-overlap").getContext("2d");
  let lowCount = 0,
    medCount = 0,
    highCount = 0;
  comparisons.forEach((c) => {
    const r = (c.overlap_rating || "low").toLowerCase();
    if (r === "low") lowCount++;
    else if (r === "medium") medCount++;
    else if (r === "high") highCount++;
  });

  const overlapLabels = [];
  const overlapData = [];
  const overlapColors = [];
  if (lowCount > 0) {
    overlapLabels.push("Low");
    overlapData.push(lowCount);
    overlapColors.push("#3ecf8e");
  }
  if (medCount > 0) {
    overlapLabels.push("Medium");
    overlapData.push(medCount);
    overlapColors.push("#f0c674");
  }
  if (highCount > 0) {
    overlapLabels.push("High");
    overlapData.push(highCount);
    overlapColors.push("#f07178");
  }

  if (overlapData.length > 0) {
    chartInstances.push(
      new Chart(overlapCtx, {
        type: "doughnut",
        data: {
          labels: overlapLabels,
          datasets: [
            {
              data: overlapData,
              backgroundColor: overlapColors,
              borderWidth: 0,
            },
          ],
        },
        options: {
          cutout: "55%",
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              position: "bottom",
              labels: {
                color: "#94b0cf",
                font: { family: "'IBM Plex Sans', sans-serif", size: 11 },
                padding: 12,
                usePointStyle: true,
                pointStyleWidth: 8,
              },
            },
            tooltip: {
              backgroundColor: "#172234",
              titleColor: "#e2ebf3",
              bodyColor: "#c1d3e6",
              borderColor: "#1e2f45",
              borderWidth: 1,
            },
          },
        },
      })
    );
  }

  // --- 3. Similarity Score Distribution (horizontal bar) ---
  const simCtx = document.getElementById("chart-similarity").getContext("2d");
  // Limit to top 15 for readability, sorted by similarity descending
  const sorted = [...comparisons]
    .filter((c) => c.similarity_score > 0)
    .sort((a, b) => b.similarity_score - a.similarity_score)
    .slice(0, 15);

  if (sorted.length > 0) {
    const labels = sorted.map((c) => {
      const t = c.title || c.publication_id || "?";
      return t.length > 50 ? t.slice(0, 47) + "..." : t;
    });
    const scores = sorted.map((c) => c.similarity_score);
    const barColors = sorted.map((c) => getOverlapColor(c.overlap_rating));

    chartInstances.push(
      new Chart(simCtx, {
        type: "bar",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Similarity",
              data: scores,
              backgroundColor: barColors,
              borderRadius: 3,
              barPercentage: 0.7,
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              min: 0,
              max: 1,
              ticks: {
                color: "#6b8baf",
                font: { family: "'IBM Plex Mono', monospace", size: 10 },
              },
              grid: { color: "rgba(30, 47, 69, 0.5)" },
            },
            y: {
              ticks: {
                color: "#94b0cf",
                font: { family: "'IBM Plex Sans', sans-serif", size: 11 },
              },
              grid: { display: false },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: "#172234",
              titleColor: "#e2ebf3",
              bodyColor: "#c1d3e6",
              borderColor: "#1e2f45",
              borderWidth: 1,
              callbacks: {
                label: (ctx) => `Similarity: ${ctx.parsed.x.toFixed(3)}`,
              },
            },
          },
        },
      })
    );

    // Dynamically size the bar chart container based on item count
    const barContainer = document.getElementById("chart-similarity").parentElement;
    barContainer.style.height = Math.max(180, sorted.length * 28 + 40) + "px";
  }

  // --- 4. Landscape Map (scatter plot) ---
  renderLandscapeMap(data);
}

function renderLandscapeMap(data) {
  const mapCard = document.getElementById("landscape-map-card");
  const points = data.landscape_map || [];
  if (points.length < 2) {
    mapCard.classList.add("hidden");
    return;
  }
  mapCard.classList.remove("hidden");

  const mapCtx = document.getElementById("chart-landscape").getContext("2d");

  const queryPoints = points.filter((p) => p.type === "query");
  const relevantPoints = points.filter((p) => p.type === "relevant");
  const bgPoints = points.filter((p) => p.type === "background");

  // Split relevant publications into overlap tiers for distinct legend entries
  const highPoints = relevantPoints.filter((p) => p.similarity >= 0.70);
  const medPoints = relevantPoints.filter((p) => p.similarity >= 0.50 && p.similarity < 0.70);
  const lowPoints = relevantPoints.filter((p) => p.similarity < 0.50);

  const datasets = [];
  const ptData = (p) => ({ x: p.x, y: p.y, label: p.label, similarity: p.similarity });

  // Background publications (below threshold)
  if (bgPoints.length > 0) {
    datasets.push({
      label: "Below Threshold",
      data: bgPoints.map(ptData),
      backgroundColor: "rgba(61, 90, 128, 0.25)",
      borderColor: "rgba(61, 90, 128, 0.4)",
      borderWidth: 1,
      pointRadius: 4,
      pointHoverRadius: 6,
    });
  }

  // Low overlap (above threshold but below medium)
  if (lowPoints.length > 0) {
    datasets.push({
      label: "Low Overlap",
      data: lowPoints.map(ptData),
      backgroundColor: "rgba(62, 207, 142, 0.7)",
      borderColor: "#3ecf8e",
      borderWidth: 1.5,
      pointRadius: 5,
      pointHoverRadius: 8,
    });
  }

  // Medium overlap
  if (medPoints.length > 0) {
    datasets.push({
      label: "Medium Overlap",
      data: medPoints.map(ptData),
      backgroundColor: "rgba(240, 198, 116, 0.8)",
      borderColor: "#f0c674",
      borderWidth: 1.5,
      pointRadius: 6,
      pointHoverRadius: 9,
    });
  }

  // High overlap
  if (highPoints.length > 0) {
    datasets.push({
      label: "High Overlap",
      data: highPoints.map(ptData),
      backgroundColor: "rgba(240, 113, 120, 0.8)",
      borderColor: "#f07178",
      borderWidth: 1.5,
      pointRadius: 7,
      pointHoverRadius: 10,
    });
  }

  // Query point at center (star)
  if (queryPoints.length > 0) {
    datasets.push({
      label: "Your Topic",
      data: queryPoints.map(ptData),
      backgroundColor: "#d4a853",
      borderColor: "#e0be72",
      borderWidth: 2,
      pointRadius: 12,
      pointHoverRadius: 14,
      pointStyle: "star",
    });
  }

  // Plugin: draw concentric threshold rings
  const ringPlugin = {
    id: "radialRings",
    beforeDatasetsDraw(chart) {
      const { ctx, scales } = chart;
      const xScale = scales.x;
      const yScale = scales.y;
      const cx = xScale.getPixelForValue(0);
      const cy = yScale.getPixelForValue(0);

      const rings = [
        { radius: 0.30, label: "High 0.70" },
        { radius: 0.50, label: "Med 0.50" },
        { radius: 0.70, label: "Min 0.30" },
      ];

      ctx.save();
      rings.forEach((ring) => {
        const px = xScale.getPixelForValue(ring.radius);
        const pr = Math.abs(px - cx);

        ctx.beginPath();
        ctx.arc(cx, cy, pr, 0, 2 * Math.PI);
        ctx.strokeStyle = "rgba(148, 176, 207, 0.2)";
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label at top of ring
        ctx.font = "10px 'IBM Plex Mono', monospace";
        ctx.fillStyle = "rgba(148, 176, 207, 0.45)";
        ctx.textAlign = "center";
        ctx.fillText(ring.label, cx, cy - pr - 4);
      });
      ctx.restore();
    },
  };

  chartInstances.push(
    new Chart(mapCtx, {
      type: "scatter",
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            min: -1.15,
            max: 1.15,
            display: false,
            grid: { display: false },
          },
          y: {
            min: -1.15,
            max: 1.15,
            display: false,
            grid: { display: false },
          },
        },
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: "#94b0cf",
              font: { family: "'IBM Plex Sans', sans-serif", size: 11 },
              padding: 14,
              usePointStyle: true,
              pointStyleWidth: 10,
            },
          },
          tooltip: {
            backgroundColor: "#172234",
            titleColor: "#e2ebf3",
            bodyColor: "#c1d3e6",
            borderColor: "#1e2f45",
            borderWidth: 1,
            callbacks: {
              title: (items) => items[0]?.raw?.label || "",
              label: (ctx) => {
                const raw = ctx.raw;
                if (raw.similarity >= 1.0) return "Your topic (center)";
                return `Similarity: ${raw.similarity.toFixed(3)}`;
              },
            },
          },
        },
      },
      plugins: [ringPlugin],
    })
  );
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
  a.download = "uncharted_waters_report.md";
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
