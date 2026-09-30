(() => {
  let activeIndex = 0;
  let slides = [];
  let deck = null;
  let parent = null;
  let osc = null;
  let progress = null;
  let overview = null;
  let presenterPanel = null;
  let presenterWindow = null;
  let tooltip = null;
  let isSyncingSlide = false;

  document.addEventListener("DOMContentLoaded", () => {
    slides = Array.from(document.querySelectorAll("section"));
    if (slides.length === 0) return;
    activeIndex = initialIndex();
    parent = ensureBespokeParent(slides);
    deck = parent.querySelector(".marpit");
    osc = document.createElement("nav");
    osc.className = "bespoke-marp-osc";
    osc.setAttribute("aria-label", "Slide controls");
    osc.innerHTML = `
      <button type="button" data-action="previous" aria-label="Previous slide" data-tooltip="Previous slide (← / PageUp)">${lucideIcon("chevron-left")}</button>
      <span class="bespoke-marp-osc-status" data-role="status"></span>
      <button type="button" data-action="next" aria-label="Next slide" data-tooltip="Next slide (→ / Space / PageDown)">${lucideIcon("chevron-right")}</button>
      <button type="button" data-action="fullscreen" aria-label="Fullscreen" data-tooltip="Fullscreen (F)">${lucideIcon("maximize")}</button>
      <button type="button" data-action="overview" aria-label="Overview" data-tooltip="Overview (O)">${lucideIcon("layout-grid")}</button>
      <button type="button" data-action="presenter" aria-label="Presenter view" data-tooltip="Presenter view (P)">${lucideIcon("presentation")}</button>
    `;
    progress = document.createElement("div");
    progress.className = "bespoke-progress-parent";
    progress.setAttribute("aria-hidden", "true");
    progress.innerHTML = `<span class="bespoke-progress-bar"></span>`;
    osc.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button) return;
      runControlAction(button.dataset.action);
    });
    osc.addEventListener("mouseover", (event) => {
      const button = event.target.closest("button[data-tooltip]");
      if (button) showTooltip(button);
    });
    osc.addEventListener("mouseout", (event) => {
      if (event.target.closest("button[data-tooltip]")) hideTooltip();
    });
    document.body.dataset.bespokeView = currentView();
    document.body.classList.add("internkim-deck-ready");
    parent.appendChild(osc);
    document.body.insertBefore(progress, parent);
    tooltip = document.createElement("div");
    tooltip.className = "bespoke-marp-tooltip";
    document.body.appendChild(tooltip);
    if (currentView() === "presenter") createPresenterPanel();
    updateScale();
    update();
    wakeControls();
  });

  window.addEventListener("resize", () => {
    if (deck) updateScale();
  });

  document.addEventListener("fullscreenchange", updateFullscreenButton);

  let controlsIdleTimer = null;

  function wakeControls() {
    if (!osc) return;
    osc.dataset.idle = "false";
    clearTimeout(controlsIdleTimer);
    controlsIdleTimer = setTimeout(() => {
      if (!osc || osc.matches(":hover")) {
        wakeControls();
        return;
      }
      osc.dataset.idle = "true";
      hideTooltip();
    }, 2600);
  }

  document.addEventListener("mousemove", wakeControls);
  document.addEventListener("pointerdown", wakeControls);

  document.addEventListener("keydown", (event) => {
    if (slides.length === 0) return;
    if (event.defaultPrevented || editableTarget(event.target)) return;
    if (["ArrowRight", "PageDown", " "].includes(event.key)) {
      event.preventDefault();
      go(1);
    }
    if (["ArrowLeft", "PageUp", "Backspace"].includes(event.key)) {
      event.preventDefault();
      go(-1);
    }
    if (event.key === "Home") {
      event.preventDefault();
      show(0);
    }
    if (event.key === "End") {
      event.preventDefault();
      show(slides.length - 1);
    }
    if (event.key === "Escape" && overview?.dataset.open === "true") {
      event.preventDefault();
      closeOverview();
    }
    if ((event.key === "o" || event.key === "O") && !event.altKey && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      toggleOverview();
    }
    if ((event.key === "f" || event.key === "F") && !event.altKey && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      toggleFullscreen();
    }
    if ((event.key === "p" || event.key === "P") && !event.altKey && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      openPresenterView();
    }
  });

  window.addEventListener("hashchange", () => {
    if (slides.length > 0) show(initialIndex(), false);
  });

  window.addEventListener("message", (event) => {
    if (event.data?.type !== "internkim-slide") return;
    isSyncingSlide = true;
    show(Number(event.data.index), false);
    isSyncingSlide = false;
  });

  function initialIndex() {
    const match = location.hash.match(/(?:slide-)?(\d+)/);
    const parsed = match ? Number(match[1]) - 1 : 0;
    return clamp(parsed);
  }

  function editableTarget(target) {
    return target && target.closest && target.closest("input, textarea, select, button, [contenteditable='true']");
  }

  function go(delta) {
    show(activeIndex + delta);
  }

  function show(index, updateHash = true) {
    activeIndex = clamp(index);
    update();
    if (updateHash) history.replaceState(null, "", `#slide-${activeIndex + 1}`);
    broadcastSlideChange();
  }

  function update() {
    if (!osc || !progress) return;
    slides.forEach((slide, index) => {
      slide.classList.toggle("bespoke-active", index === activeIndex);
      slide.classList.toggle("bespoke-before", index < activeIndex);
      slide.classList.toggle("bespoke-after", index > activeIndex);
      slide.setAttribute("aria-hidden", index === activeIndex ? "false" : "true");
    });
    osc.querySelector("[data-action='previous']").disabled = activeIndex === 0;
    osc.querySelector("[data-action='next']").disabled = activeIndex === slides.length - 1;
    osc.querySelector("[data-role='status']").textContent = `${activeIndex + 1} / ${slides.length}`;
    progress.querySelector(".bespoke-progress-bar").style.width = `${((activeIndex + 1) / slides.length) * 100}%`;
    updateFullscreenButton();
    updateOverviewState();
    updatePresenterPanel();
  }

  function runControlAction(action) {
    if (action === "next") go(1);
    if (action === "previous") go(-1);
    if (action === "fullscreen") toggleFullscreen();
    if (action === "overview") toggleOverview();
    if (action === "presenter") openPresenterView();
  }

  function ensureBespokeParent(currentSlides) {
    const existingDeck = currentSlides[0].closest(".marpit");
    if (existingDeck) {
      const existingParent = existingDeck.closest(".bespoke-marp-parent");
      if (existingParent) return existingParent;
      const createdParent = document.createElement("div");
      createdParent.className = "bespoke-marp-parent";
      existingDeck.parentNode.insertBefore(createdParent, existingDeck);
      createdParent.appendChild(existingDeck);
      return createdParent;
    }
    const createdParent = document.createElement("div");
    createdParent.className = "bespoke-marp-parent";
    const createdDeck = document.createElement("div");
    createdDeck.className = "marpit";
    currentSlides[0].parentNode.insertBefore(createdParent, currentSlides[0]);
    createdParent.appendChild(createdDeck);
    currentSlides.forEach((slide) => createdDeck.appendChild(slide));
    return createdParent;
  }

  function updateScale() {
    const horizontalPadding = 0;
    const verticalPadding = 0;
    const bounds = parent.getBoundingClientRect();
    const availableWidth = Math.max(320, bounds.width - horizontalPadding);
    const availableHeight = Math.max(180, bounds.height - verticalPadding);
    const scale = Math.min(availableWidth / 1600, availableHeight / 900);
    deck.style.setProperty("--internkim-deck-scale", String(Math.max(0.1, scale)));
    updateOverviewScale();
    updatePresenterNextScale();
  }

  function clamp(index) {
    return Math.max(0, Math.min(slides.length - 1, Number.isFinite(index) ? index : 0));
  }

  function currentView() {
    return new URLSearchParams(location.search).get("view") === "presenter" ? "presenter" : "slide";
  }

  async function toggleFullscreen() {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      return;
    }
    await document.documentElement.requestFullscreen?.();
  }

  function updateFullscreenButton() {
    const button = osc?.querySelector("[data-action='fullscreen']");
    if (!button) return;
    const isFullscreen = !!document.fullscreenElement;
    button.innerHTML = lucideIcon(isFullscreen ? "minimize" : "maximize");
    button.setAttribute("aria-label", isFullscreen ? "Exit fullscreen" : "Fullscreen");
    button.dataset.tooltip = isFullscreen ? "Exit fullscreen (F)" : "Fullscreen (F)";
  }

  function toggleOverview() {
    if (overview?.dataset.open === "true") {
      closeOverview();
      return;
    }
    openOverview();
  }

  function openOverview() {
    if (!overview) overview = createOverview();
    overview.dataset.open = "true";
    updateOverviewScale();
    updateOverviewState();
  }

  function closeOverview() {
    if (overview) overview.dataset.open = "false";
  }

  function createOverview() {
    const createdOverview = document.createElement("div");
    createdOverview.className = "bespoke-marp-overview";
    createdOverview.innerHTML = `<button type="button" class="bespoke-marp-overview-close" aria-label="Close overview" title="Close overview (Esc)">${lucideIcon("x")}</button><div class="bespoke-marp-overview-grid"></div>`;
    const grid = createdOverview.querySelector(".bespoke-marp-overview-grid");
    slides.forEach((slide, index) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "bespoke-marp-overview-card";
      card.dataset.index = String(index);
      const thumb = document.createElement("div");
      thumb.className = "bespoke-marp-overview-thumb";
      thumb.appendChild(slide.cloneNode(true));
      card.appendChild(thumb);
      card.insertAdjacentHTML("beforeend", `<span>${index + 1}</span>`);
      card.addEventListener("click", () => {
        show(index);
        closeOverview();
      });
      grid.appendChild(card);
    });
    createdOverview.querySelector(".bespoke-marp-overview-close").addEventListener("click", closeOverview);
    document.body.appendChild(createdOverview);
    return createdOverview;
  }

  function updateOverviewState() {
    overview?.querySelectorAll(".bespoke-marp-overview-card").forEach((card) => {
      card.classList.toggle("is-current", Number(card.dataset.index) === activeIndex);
    });
  }

  function updateOverviewScale() {
    overview?.querySelectorAll(".bespoke-marp-overview-thumb").forEach((thumb) => {
      thumb.style.setProperty("--internkim-thumb-scale", String(thumb.clientWidth / 1600));
    });
  }

  function openPresenterView() {
    const url = new URL(location.href);
    url.searchParams.set("view", "presenter");
    url.hash = `slide-${activeIndex + 1}`;
    presenterWindow = window.open(url.toString(), "internkim-presenter", "width=1280,height=720,menubar=no,toolbar=no");
  }

  function broadcastSlideChange() {
    if (isSyncingSlide) return;
    const message = { type: "internkim-slide", index: activeIndex };
    presenterWindow?.postMessage(message, "*");
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage(message, "*");
    }
  }

  function createPresenterPanel() {
    presenterPanel = document.createElement("aside");
    presenterPanel.className = "bespoke-marp-presenter-panel";
    presenterPanel.innerHTML = `<div class="bespoke-marp-presenter-next"></div><div class="bespoke-marp-presenter-note"></div><div class="bespoke-marp-presenter-info"><span data-role="presenter-status"></span><time data-role="presenter-clock"></time></div>`;
    document.body.appendChild(presenterPanel);
    setInterval(updatePresenterClock, 1000);
    updatePresenterClock();
  }

  function updatePresenterPanel() {
    if (!presenterPanel) return;
    const nextSlide = slides[Math.min(activeIndex + 1, slides.length - 1)];
    const nextContainer = presenterPanel.querySelector(".bespoke-marp-presenter-next");
    nextContainer.replaceChildren(nextSlide.cloneNode(true));
    presenterPanel.querySelector(".bespoke-marp-presenter-note").textContent = notesForSlide(slides[activeIndex]);
    presenterPanel.querySelector("[data-role='presenter-status']").textContent = `${activeIndex + 1} / ${slides.length}`;
    updatePresenterNextScale();
  }

  function updatePresenterNextScale() {
    const nextContainer = presenterPanel?.querySelector(".bespoke-marp-presenter-next");
    if (!nextContainer) return;
    const scale = Math.min(nextContainer.clientWidth / 1600, nextContainer.clientHeight / 900);
    nextContainer.style.setProperty("--internkim-presenter-next-scale", String(Math.max(0.1, scale)));
  }

  function updatePresenterClock() {
    const clock = presenterPanel?.querySelector("[data-role='presenter-clock']");
    if (clock) clock.textContent = new Date().toLocaleTimeString();
  }

  function notesForSlide(slide) {
    const note = slide.querySelector("aside.notes, aside[role='note'], [data-speaker-notes]");
    if (note?.textContent?.trim()) return note.textContent.trim();
    const heading = slide.querySelector("h1, h2, h3")?.textContent?.trim() || `Slide ${activeIndex + 1}`;
    return `현재 슬라이드: ${heading}`;
  }

  function showTooltip(button) {
    if (!tooltip) return;
    tooltip.textContent = button.dataset.tooltip || "";
    const bounds = button.getBoundingClientRect();
    tooltip.style.left = `${bounds.left + bounds.width / 2}px`;
    tooltip.style.top = `${bounds.top}px`;
    tooltip.dataset.open = "true";
  }

  function hideTooltip() {
    if (tooltip) tooltip.dataset.open = "false";
  }

  function lucideIcon(name) {
    const icons = {
      "chevron-left": `<svg data-lucide="chevron-left" viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>`,
      "chevron-right": `<svg data-lucide="chevron-right" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"></path></svg>`,
      "layout-grid": `<svg data-lucide="layout-grid" viewBox="0 0 24 24" aria-hidden="true"><rect width="7" height="7" x="3" y="3" rx="1"></rect><rect width="7" height="7" x="14" y="3" rx="1"></rect><rect width="7" height="7" x="14" y="14" rx="1"></rect><rect width="7" height="7" x="3" y="14" rx="1"></rect></svg>`,
      "maximize": `<svg data-lucide="maximize" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H5a2 2 0 0 0-2 2v3"></path><path d="M21 8V5a2 2 0 0 0-2-2h-3"></path><path d="M3 16v3a2 2 0 0 0 2 2h3"></path><path d="M16 21h3a2 2 0 0 0 2-2v-3"></path></svg>`,
      "minimize": `<svg data-lucide="minimize" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3v3a2 2 0 0 1-2 2H3"></path><path d="M21 8h-3a2 2 0 0 1-2-2V3"></path><path d="M3 16h3a2 2 0 0 1 2 2v3"></path><path d="M16 21v-3a2 2 0 0 1 2-2h3"></path></svg>`,
      "presentation": `<svg data-lucide="presentation" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 3h20"></path><path d="M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3"></path><path d="m7 21 5-5 5 5"></path></svg>`,
      "x": `<svg data-lucide="x" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>`,
    };
    return icons[name] || "";
  }
})();
