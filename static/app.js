/**
 * ProofPay Frontend Application Logic
 * "Verify the payment. Not just the screenshot."
 * Parakram Hackathon 26
 */

document.addEventListener("DOMContentLoaded", () => {
    // State variables
    let selectedFile = null;
    let currentPreviewUrl = null;

    // DOM Elements - Navigation Tabs
    const tabButtons = document.querySelectorAll(".nav-tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");

    // DOM Elements - Upload & Dropzone
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");
    const dropzoneDefault = document.getElementById("dropzone-default");
    const dropzonePreview = document.getElementById("dropzone-preview");
    const previewImage = document.getElementById("preview-image");
    const previewFilename = document.getElementById("preview-filename");
    const btnChangeFile = document.getElementById("btn-change-file");
    const btnAnalyze = document.getElementById("btn-analyze");
    const samplesGrid = document.getElementById("samples-grid");

    // Order matching inputs
    const inputExpectedAmount = document.getElementById("input-expected-amount");
    const inputOrderId = document.getElementById("input-order-id");

    // DOM Elements - Results & Progress
    const emptyState = document.getElementById("empty-state");
    const loadingState = document.getElementById("loading-state");
    const resultContent = document.getElementById("result-content");
    const loadingPreviewImg = document.getElementById("loading-preview-img");
    const currentStageDesc = document.getElementById("current-stage-desc");

    // DOM Elements - Verdict & Scores
    const verdictBanner = document.getElementById("verdict-banner");
    const verdictIcon = document.getElementById("verdict-icon");
    const verdictTitle = document.getElementById("verdict-title");
    const verdictBadge = document.getElementById("verdict-badge");
    const verdictSummary = document.getElementById("verdict-summary");
    const riskLevelBadge = document.getElementById("risk-level-badge");
    const orderMatchBanner = document.getElementById("order-match-banner");
    const orderMatchIcon = document.getElementById("order-match-icon");
    const orderMatchText = document.getElementById("order-match-text");

    const gaugeFill = document.getElementById("gauge-fill");
    const gaugeVal = document.getElementById("gauge-val");
    const scoreRule = document.getElementById("score-rule");
    const scoreMl = document.getElementById("score-ml");
    const scoreOcr = document.getElementById("score-ocr");
    const reasonsList = document.getElementById("reasons-list");

    // DOM Elements - Extracted Details
    const extractedAppBadge = document.getElementById("extracted-app-badge");
    const detailAmount = document.getElementById("detail-amount");
    const detailStatus = document.getElementById("detail-status");
    const detailUtr = document.getElementById("detail-utr");
    const detailDate = document.getElementById("detail-date");
    const detailSender = document.getElementById("detail-sender");
    const detailReceiver = document.getElementById("detail-receiver");

    // DOM Elements - Match & Forensics
    const matchStatusBadge = document.getElementById("match-status-badge");
    const matchDetailsBody = document.getElementById("match-details-body");
    const elaOrigImg = document.getElementById("ela-orig-img");
    const elaHeatmapImg = document.getElementById("ela-heatmap-img");
    const checksList = document.getElementById("checks-list");

    // DOM Elements - History & Merchant Ledger
    const btnRefreshHistory = document.getElementById("btn-refresh-history");
    const historyTbody = document.getElementById("history-tbody");
    const btnRefreshLedger = document.getElementById("btn-refresh-ledger");
    const ledgerTbody = document.getElementById("ledger-tbody");
    const ledgerCount = document.getElementById("ledger-count");
    const addLedgerForm = document.getElementById("add-ledger-form");
    const ledgerFormMsg = document.getElementById("ledger-form-msg");

    // Merchant Summary Metrics
    const metricTotalScans = document.getElementById("metric-total-scans");
    const metricFlagged = document.getElementById("metric-flagged");
    const metricDuplicates = document.getElementById("metric-duplicates");

    // ==========================================
    // 1. Navigation Tab Switching
    // ==========================================
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");

            tabButtons.forEach(b => {
                b.classList.remove("active");
                b.setAttribute("aria-selected", "false");
            });
            tabPanes.forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            btn.setAttribute("aria-selected", "true");

            const activePane = document.getElementById(targetTab);
            if (activePane) activePane.classList.add("active");

            // Auto-refresh data on tab switch
            if (targetTab === "tab-history") loadScanHistory();
            if (targetTab === "tab-ledger") {
                loadDemoLedger();
                loadScanHistory();
            }
        });
    });

    // ==========================================
    // 2. Dropzone & File Selection Handlers
    // ==========================================
    dropzone.addEventListener("click", (e) => {
        if (e.target !== btnChangeFile && !dropzonePreview.contains(e.target)) {
            fileInput.click();
        }
    });

    btnChangeFile.addEventListener("click", (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    fileInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) handleFileSelected(file);
    });

    // Drag-and-drop events
    ["dragenter", "dragover"].forEach(evt => {
        dropzone.addEventListener(evt, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add("drag-active");
        });
    });

    ["dragleave", "drop"].forEach(evt => {
        dropzone.addEventListener(evt, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove("drag-active");
        });
    });

    dropzone.addEventListener("drop", (e) => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleFileSelected(files[0]);
        }
    });

    function handleFileSelected(file) {
        if (!file.type.match(/^image\/(png|jpeg|webp)$/i) && !file.name.match(/\.(png|jpe?g|webp)$/i)) {
            alert("Please upload a valid image file (PNG, JPG, or JPEG).");
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            alert("File size exceeds 5 MB limit. Please select a smaller screenshot.");
            return;
        }

        selectedFile = file;

        // Clean up previous blob URL
        if (currentPreviewUrl) {
            URL.revokeObjectURL(currentPreviewUrl);
        }

        currentPreviewUrl = URL.createObjectURL(file);
        previewImage.src = currentPreviewUrl;
        previewFilename.textContent = file.name;

        dropzoneDefault.classList.add("hidden");
        dropzonePreview.classList.remove("hidden");
        btnAnalyze.disabled = false;
    }

    // ==========================================
    // 3. Pre-Generated Sample Test Selector
    // ==========================================
    async function loadSamples() {
        try {
            const resp = await fetch("/api/samples");
            const data = await resp.json();
            if (data.success && data.samples) {
                renderSamples(data.samples);
            }
        } catch (err) {
            console.error("Failed to load demo samples:", err);
        }
    }

    function renderSamples(samples) {
        samplesGrid.innerHTML = "";
        samples.forEach(s => {
            const card = document.createElement("div");
            card.className = "sample-card";
            card.innerHTML = `
                <div class="sample-card-info">
                    <h4>
                        <span>${s.title}</span>
                        <span class="sample-badge badge-${s.expected_color}">${s.expected}</span>
                    </h4>
                    <p>${s.desc}</p>
                </div>
                <div class="sample-arrow">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
                </div>
            `;

            card.addEventListener("click", async () => {
                try {
                    // Pre-fill expected order amount for demonstration
                    if (s.id.includes("genuine")) {
                        inputExpectedAmount.value = "750.00";
                        inputOrderId.value = "ORD-101";
                    } else if (s.id.includes("tampered")) {
                        inputExpectedAmount.value = "750.00";
                        inputOrderId.value = "ORD-101";
                    } else {
                        inputExpectedAmount.value = "";
                        inputOrderId.value = "";
                    }

                    // Fetch sample blob
                    const res = await fetch(s.url);
                    const blob = await res.blob();
                    const file = new File([blob], s.id, { type: blob.type || "image/png" });
                    handleFileSelected(file);

                    // Immediate auto-analysis on tap for fast phone testing
                    runAnalysis(file);
                } catch (e) {
                    console.error("Error loading sample:", e);
                }
            });

            samplesGrid.appendChild(card);
        });
    }

    // ==========================================
    // 4. Analysis Execution & 5-Step Animation
    // ==========================================
    btnAnalyze.addEventListener("click", () => {
        if (!selectedFile) return;
        runAnalysis(selectedFile);
    });

    async function runAnalysis(file) {
        // UI State: Hide empty and result, show animated scanner
        emptyState.classList.add("hidden");
        resultContent.classList.add("hidden");
        loadingState.classList.remove("hidden");
        loadingPreviewImg.src = currentPreviewUrl;
        btnAnalyze.disabled = true;

        // Reset step tracker
        const stages = [
            { step: 1, label: "Stage 1 of 5: Ingesting image and computing perceptual hash..." },
            { step: 2, label: "Stage 2 of 5: Running OCR text extraction and currency parsing..." },
            { step: 3, label: "Stage 3 of 5: Performing Error Level Analysis & metadata inspection..." },
            { step: 4, label: "Stage 4 of 5: Matching against expected order & bank records..." },
            { step: 5, label: "Stage 5 of 5: Computing hybrid ML risk score and final report..." },
        ];

        let currentStageIdx = 0;
        setStage(stages[0]);

        const stageInterval = setInterval(() => {
            currentStageIdx++;
            if (currentStageIdx < stages.length) {
                setStage(stages[currentStageIdx]);
            }
        }, 320);

        function setStage(stageInfo) {
            currentStageDesc.textContent = stageInfo.label;
            for (let i = 1; i <= 5; i++) {
                const el = document.getElementById(`step-${i}`);
                if (i < stageInfo.step) {
                    el.className = "tracker-step completed";
                } else if (i === stageInfo.step) {
                    el.className = "tracker-step active";
                } else {
                    el.className = "tracker-step";
                }
            }
        }

        // Prepare multipart form data
        const formData = new FormData();
        formData.append("image", file);

        const expAmt = inputExpectedAmount ? inputExpectedAmount.value.trim() : "";
        const orderId = inputOrderId ? inputOrderId.value.trim() : "";
        const manualUtr = document.getElementById("input-manual-utr") ? document.getElementById("input-manual-utr").value.trim() : "";
        if (expAmt) formData.append("expected_amount", expAmt);
        if (orderId) formData.append("order_id", orderId);
        if (manualUtr) formData.append("manual_utr", manualUtr);

        try {
            const response = await fetch("/api/analyze", {
                method: "POST",
                body: formData,
            });

            const result = await response.json();
            clearInterval(stageInterval);

            // Complete step 5
            setStage({ step: 5, label: "Stage 5 of 5: Analysis Complete!" });

            setTimeout(() => {
                loadingState.classList.add("hidden");
                btnAnalyze.disabled = false;

                if (result.success) {
                    renderResult(result);
                    // Refresh metrics in background
                    loadScanHistory();
                } else {
                    alert("Analysis error: " + (result.error || "Unknown server error."));
                    emptyState.classList.remove("hidden");
                }
            }, 300);

        } catch (err) {
            clearInterval(stageInterval);
            loadingState.classList.add("hidden");
            btnAnalyze.disabled = false;
            emptyState.classList.remove("hidden");
            alert("Failed to analyze screenshot: " + err.message);
        }
    }

    // ==========================================
    // 5. Render Verification Results
    // ==========================================
    function renderResult(data) {
        resultContent.classList.remove("hidden");

        const status = data.status || "UNVERIFIED";
        const risk = Number(data.risk_score || 0);

        // A. Verdict Banner
        verdictBanner.className = `verdict-banner ${status.toLowerCase()}`;
        verdictTitle.textContent = status;

        if (status === "VERIFIED") {
            verdictBadge.textContent = "AUTHENTIC PAYMENT (पैसे खाते में आ चुके हैं)";
            verdictSummary.textContent = "Confirmed! Valid transaction record found in bank ledger and forensic integrity verified.";
            verdictIcon.innerHTML = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>`;
        } else if (status === "SUSPICIOUS") {
            verdictBadge.textContent = "HIGH CONCERN / TAMPERED (धोखाधड़ी - सामान मत दो)";
            verdictSummary.textContent = "Warning! High forensic risk, record discrepancy, or duplicate screenshot detected.";
            verdictIcon.innerHTML = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
        } else {
            verdictBadge.textContent = "UNVERIFIED • RECORD NOT FOUND (बैंक में नहीं मिला - चेक करें)";
            verdictSummary.textContent = "Caution! No trusted bank transaction record found. A screenshot alone is never proof of payment.";
            verdictIcon.innerHTML = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
        }

        // B. Risk Level Indicator
        if (risk < 35) {
            riskLevelBadge.textContent = "Low Concern";
            riskLevelBadge.className = "risk-level-badge low";
        } else if (risk < 60) {
            riskLevelBadge.textContent = "Needs Review";
            riskLevelBadge.className = "risk-level-badge medium";
        } else {
            riskLevelBadge.textContent = "High Concern";
            riskLevelBadge.className = "risk-level-badge high";
        }

        // B2. 1-Click Bank Settlement Simulation Banner
        const simulationBanner = document.getElementById("simulation-banner");
        const simUtrDisplay = document.getElementById("sim-utr-display");
        const simAmtDisplay = document.getElementById("sim-amt-display");
        const btnQuickVerify = document.getElementById("btn-quick-verify");
        const quickVerifyStatus = document.getElementById("quick-verify-status");

        const extUtr = data.extracted?.txn_id;
        const extAmt = data.extracted?.amount;

        if (status === "UNVERIFIED" && extUtr && simulationBanner) {
            simulationBanner.classList.remove("hidden");
            if (simUtrDisplay) simUtrDisplay.textContent = extUtr;
            if (simAmtDisplay) simAmtDisplay.textContent = extAmt ? `₹${Number(extAmt).toFixed(2)}` : "amount";
            if (quickVerifyStatus) quickVerifyStatus.textContent = "";

            if (btnQuickVerify) {
                btnQuickVerify.disabled = false;
                btnQuickVerify.onclick = async () => {
                    btnQuickVerify.disabled = true;
                    if (quickVerifyStatus) quickVerifyStatus.textContent = "Simulating bank credit in ledger...";
                    try {
                        const res = await fetch("/api/quick-verify", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                txn_id: extUtr,
                                amount: extAmt || 500.0,
                                payer_name: data.extracted?.sender || "Google Pay User",
                                payer_vpa: "customer@okaxis",
                            }),
                        });
                        const qData = await res.json();
                        if (qData.success) {
                            if (quickVerifyStatus) quickVerifyStatus.textContent = "Funds credited! Verifying...";
                            setTimeout(() => {
                                if (selectedFile) {
                                    runAnalysis(selectedFile);
                                }
                            }, 500);
                        } else {
                            if (quickVerifyStatus) quickVerifyStatus.textContent = "Error: " + (qData.error || "Failed");
                            btnQuickVerify.disabled = false;
                        }
                    } catch (e) {
                        if (quickVerifyStatus) quickVerifyStatus.textContent = "Network error: " + e.message;
                        btnQuickVerify.disabled = false;
                    }
                };
            }
        } else if (simulationBanner) {
            simulationBanner.classList.add("hidden");
        }

        // C. Optional Order Matching Banner
        if (data.order_match && data.order_match.checked) {
            orderMatchBanner.classList.remove("hidden");
            if (data.order_match.matched) {
                orderMatchBanner.className = "order-match-banner matched";
                orderMatchIcon.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
                orderMatchText.innerHTML = `<span><strong>Order Amount Matched:</strong> Expected ₹${Number(data.order_match.expected_amount).toFixed(2)} matches screenshot claimed amount.</span>`;
            } else {
                orderMatchBanner.className = "order-match-banner mismatch";
                orderMatchIcon.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
                const claimed = data.extracted?.amount ? `₹${Number(data.extracted.amount).toFixed(2)}` : "unreadable";
                orderMatchText.innerHTML = `<span><strong>Order Mismatch Warning:</strong> Expected ₹${Number(data.order_match.expected_amount).toFixed(2)}, but screenshot displays ${claimed}.</span>`;
            }
        } else {
            orderMatchBanner.classList.add("hidden");
        }

        // D. Gauge Meter
        gaugeVal.textContent = Math.round(risk);
        const strokeOffset = Math.max(0, 126 - (126 * (risk / 100)));
        gaugeFill.style.strokeDashoffset = strokeOffset;

        if (risk < 35) {
            gaugeFill.style.stroke = "var(--verified-emerald)";
            gaugeVal.style.color = "var(--verified-emerald)";
        } else if (risk < 60) {
            gaugeFill.style.stroke = "var(--unverified-amber)";
            gaugeVal.style.color = "var(--unverified-amber)";
        } else {
            gaugeFill.style.stroke = "var(--suspicious-crimson)";
            gaugeVal.style.color = "var(--suspicious-crimson)";
        }

        // E. Metrics
        scoreRule.textContent = `${data.rule_score}/100`;
        scoreMl.textContent = `${data.ml_score}/100`;
        scoreOcr.textContent = `${data.extracted?.parse_confidence || 0}%`;

        // F. Verdict Reasons
        reasonsList.innerHTML = "";
        const reasons = data.verdict_reasons || [];
        if (reasons.length === 0) {
            reasonsList.innerHTML = "<li>All consistency and ledger checks satisfied.</li>";
        } else {
            reasons.forEach(r => {
                const li = document.createElement("li");
                li.textContent = r;
                reasonsList.appendChild(li);
            });
        }

        // G. Extracted Details Table
        const ext = data.extracted || {};
        extractedAppBadge.textContent = ext.app_name || "UPI";
        detailAmount.textContent = ext.amount_formatted || (ext.amount ? `₹${ext.amount}` : "Not Found");
        detailStatus.textContent = ext.status || "UNKNOWN";
        detailUtr.textContent = ext.txn_id || "Not Found (12-digit UTR)";
        detailDate.textContent = ext.datetime || "Not Found";
        detailSender.textContent = ext.sender || "Not Specified";
        detailReceiver.textContent = ext.receiver || "Merchant / Payee";

        // H. Trusted Bank Match Card
        const match = data.record_match || {};
        if (match.found && match.matched) {
            matchStatusBadge.className = "badge badge-emerald";
            matchStatusBadge.textContent = "RECORD CONFIRMED";
            matchDetailsBody.innerHTML = `
                <div class="match-summary-box success">
                    <div>
                        <strong>Bank Ledger Match Confirmed</strong>
                        <p style="font-size:12px; margin-top:2px;">UTR: ${match.details.txn_id} &bull; Received Amount: ₹${Number(match.details.amount).toFixed(2)} &bull; ${match.details.timestamp}</p>
                    </div>
                    <span class="badge badge-emerald">SETTLED</span>
                </div>
            `;
        } else if (match.found && !match.matched) {
            matchStatusBadge.className = "badge badge-crimson";
            matchStatusBadge.textContent = "RECORD MISMATCH";
            let mismatchesHtml = (match.mismatches || []).map(m => `<li>${m}</li>`).join("");
            matchDetailsBody.innerHTML = `
                <div class="match-summary-box danger">
                    <div>
                        <strong>Discrepancy Detected in Trusted Bank Record!</strong>
                        <ul class="match-mismatches-list">${mismatchesHtml}</ul>
                    </div>
                </div>
            `;
        } else {
            matchStatusBadge.className = "badge badge-amber";
            matchStatusBadge.textContent = "NOT FOUND IN LEDGER";
            matchDetailsBody.innerHTML = `
                <div class="match-summary-box warning">
                    <div>
                        <strong>No Corresponding Bank Ledger Record</strong>
                        <p style="font-size:12px; margin-top:2px;">The UTR ID '${ext.txn_id || "N/A"}' was not found in the bank ledger. Payment has not settled into the merchant account.</p>
                    </div>
                </div>
            `;
        }

        // I. Forensic Visual Inspection (Original vs ELA Heatmap)
        elaOrigImg.src = currentPreviewUrl;
        elaHeatmapImg.src = data.ela_image_url || currentPreviewUrl;

        // J. Forensic Checks Breakdown
        renderForensicChecks(data.checks || []);

        // Scroll results into view
        resultContent.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function renderForensicChecks(checks) {
        checksList.innerHTML = "";
        checks.forEach(chk => {
            const item = document.createElement("div");
            item.className = `check-item ${chk.flag ? "flagged" : ""}`;

            let pillClass = "pill-green";
            if (chk.score >= 60) pillClass = "pill-red";
            else if (chk.score >= 30) pillClass = "pill-amber";

            item.innerHTML = `
                <div class="check-header">
                    <span class="check-title">${chk.name}</span>
                    <span class="check-score-pill ${pillClass}">Risk: ${chk.score}/100</span>
                </div>
                <p class="check-detail">${chk.detail}</p>
            `;
            checksList.appendChild(item);
        });
    }

    // ==========================================
    // 6. Scan History & Dashboard Metrics Logic
    // ==========================================
    btnRefreshHistory.addEventListener("click", loadScanHistory);

    async function loadScanHistory() {
        try {
            const resp = await fetch("/api/history");
            const data = await resp.json();
            if (data.success && data.scans) {
                renderScanHistory(data.scans);
                updateDashboardMetrics(data.scans);
            }
        } catch (e) {
            historyTbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">Failed to load history: ${e.message}</td></tr>`;
        }
    }

    function updateDashboardMetrics(scans) {
        if (!metricTotalScans) return;
        metricTotalScans.textContent = scans.length;
        const flagged = scans.filter(s => s.verdict === "SUSPICIOUS").length;
        const dups = scans.filter(s => {
            const r = JSON.stringify(s.verdict_reasons || []);
            return r.toLowerCase().includes("duplicate");
        }).length;
        if (metricFlagged) metricFlagged.textContent = flagged;
        if (metricDuplicates) metricDuplicates.textContent = dups;
    }

    function renderScanHistory(scans) {
        if (!scans || scans.length === 0) {
            historyTbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No historical scans recorded yet. Upload a screenshot to begin.</td></tr>`;
            return;
        }

        historyTbody.innerHTML = "";
        scans.forEach(s => {
            const tr = document.createElement("tr");

            let badgeColor = "amber";
            if (s.verdict === "VERIFIED") badgeColor = "emerald";
            if (s.verdict === "SUSPICIOUS") badgeColor = "crimson";

            const amt = s.extracted_amount ? `₹${Number(s.extracted_amount).toFixed(2)}` : "N/A";
            const reasonsSummary = (s.verdict_reasons && s.verdict_reasons.length > 0)
                ? s.verdict_reasons[0]
                : "No flags reported";

            tr.innerHTML = `
                <td class="font-mono text-muted" style="font-size:11px;">${s.scan_id ? s.scan_id.substring(0, 8) + '...' : 'N/A'}</td>
                <td>${s.created_at || 'Just now'}</td>
                <td style="font-weight:600;">${amt}</td>
                <td class="font-mono">${s.extracted_txn_id || 'Not detected'}</td>
                <td><span style="font-weight:700;">${s.risk_score || 0}</span>/100</td>
                <td><span class="sample-badge badge-${badgeColor}">${s.verdict}</span></td>
                <td style="font-size:12px; color:var(--text-secondary); max-width:300px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${reasonsSummary}</td>
            `;
            historyTbody.appendChild(tr);
        });
    }

    // ==========================================
    // 7. Merchant Ledger Tab Logic
    // ==========================================
    btnRefreshLedger.addEventListener("click", loadDemoLedger);

    async function loadDemoLedger() {
        ledgerTbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">Loading ledger entries...</td></tr>`;
        try {
            const resp = await fetch("/api/ledger");
            const data = await resp.json();
            if (data.success && data.records) {
                renderDemoLedger(data.records);
            }
        } catch (e) {
            ledgerTbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">Failed to load ledger: ${e.message}</td></tr>`;
        }
    }

    function renderDemoLedger(records) {
        if (ledgerCount) ledgerCount.textContent = records.length;
        if (!records || records.length === 0) {
            ledgerTbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">Ledger is empty. Add a custom entry using the form.</td></tr>`;
            return;
        }

        ledgerTbody.innerHTML = "";
        records.forEach(r => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td class="font-mono" style="font-weight:600; color:#38bdf8;">${r.txn_id}</td>
                <td style="font-weight:700;">₹${Number(r.amount).toFixed(2)}</td>
                <td>${r.payer_name || 'Customer'} <span class="text-muted" style="font-size:11px;">(${r.payer_vpa || 'upi'})</span></td>
                <td>${r.timestamp}</td>
                <td><span class="sample-badge badge-emerald">${r.status || 'SUCCESS'}</span></td>
                <td>${r.app_source || 'UPI'}</td>
            `;
            ledgerTbody.appendChild(tr);
        });
    }

    // Handle adding a transaction to the demo ledger
    addLedgerForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const utr = document.getElementById("form-utr").value.trim();
        const amount = document.getElementById("form-amount").value.trim();
        const payer = document.getElementById("form-payer").value.trim() || "Customer";
        const payerVpa = document.getElementById("form-payer-vpa").value.trim() || "customer@okaxis";
        const notes = document.getElementById("form-notes").value.trim() || "Simulated Payment";

        if (!utr || !amount) {
            showLedgerMsg("Please provide both UTR and Amount.", false);
            return;
        }

        try {
            const resp = await fetch("/api/ledger", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    txn_id: utr,
                    amount: parseFloat(amount),
                    payer_name: payer,
                    payer_vpa: payerVpa,
                    notes: notes,
                }),
            });

            const res = await resp.json();
            if (res.success) {
                showLedgerMsg(`Success! UTR '${utr}' added to trusted bank ledger.`, true);
                addLedgerForm.reset();
                loadDemoLedger();
            } else {
                showLedgerMsg("Error: " + (res.error || "Failed to add record"), false);
            }
        } catch (err) {
            showLedgerMsg("Failed to connect to ledger API: " + err.message, false);
        }
    });

    function showLedgerMsg(text, isSuccess) {
        ledgerFormMsg.textContent = text;
        ledgerFormMsg.className = `form-status-msg ${isSuccess ? "success" : "error"}`;
        setTimeout(() => {
            ledgerFormMsg.style.display = "none";
        }, 5000);
    }

    // Initial data load on startup
    loadSamples();
    loadScanHistory();
});
