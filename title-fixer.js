(function () {
  "use strict";

  const STYLE_ID = "title-fixer-style";
  const CONTROL_ATTR = "data-title-fixer-added";
  const WRAP_CLASS = "title-fixer-wrap";
  const BUTTON_CLASS = "title-fixer-btn";
  const AUTO_FIX_DELAY_MS = 1500;
  const MIN_TEXT_LENGTH = 5;
  const autoFixTimers = new WeakMap();
  const QUESTION_STARTERS = [
    "who",
    "what",
    "when",
    "where",
    "why",
    "how",
    "which",
    "whom",
    "whose",
    "is",
    "are",
    "am",
    "was",
    "were",
    "do",
    "does",
    "did",
    "can",
    "could",
    "will",
    "would",
    "shall",
    "should",
    "may",
    "might",
    "have",
    "has",
    "had"
  ];

  function unique(values) {
    return Array.from(new Set(values.filter(Boolean)));
  }

  function getApiBaseCandidates() {
    const candidates = [];
    const protocol = (window.location && window.location.protocol) || "";
    const host = (window.location && window.location.host) || "";

    if (protocol.startsWith("http") && host) {
      candidates.push(window.location.origin);
    }

    candidates.push("http://127.0.0.1:5000");
    candidates.push("http://localhost:5000");

    return unique(candidates);
  }

  async function applyAIPunctuation(text) {
    const trimmed = (text || "").trim();
    if (!trimmed) return text;

    const candidates = getApiBaseCandidates();
    for (let i = 0; i < candidates.length; i += 1) {
      const base = candidates[i];
      try {
        const response = await fetch(base + "/api/ai/punctuate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: trimmed })
        });

        if (!response.ok) {
          continue;
        }

        const data = await response.json();
        const punctuated =
          (data && typeof data.punctuatedText === "string" && data.punctuatedText) ||
          (data && typeof data.text === "string" && data.text) ||
          "";
        if (punctuated) {
          return punctuated;
        }
      } catch (error) {
        // Try next candidate base URL.
      }
    }

    return text;
  }

  function isLikelyQuestionSentence(content) {
    const cleaned = (content || "")
      .replace(/["'()\[\]{}]+/g, "")
      .trim()
      .toLowerCase();
    if (!cleaned) return false;

    const firstWord = cleaned.split(/\s+/)[0] || "";
    if (QUESTION_STARTERS.includes(firstWord)) {
      return true;
    }

    if (cleaned.includes(" or ")) {
      return true;
    }

    return /\b(anyone|somebody|please\s+(help|confirm|share)|tell\s+me)\b/.test(cleaned);
  }

  function normalizeQuestionPunctuation(text) {
    if (!text || typeof text !== "string") return text;

    return text.replace(/[^.!?\n]+[.!?]?/g, function (segment) {
      const trimmed = segment.trim();
      if (!trimmed) return segment;

      const trailing = /[.!?]$/.test(trimmed) ? trimmed.slice(-1) : "";
      const core = trailing ? trimmed.slice(0, -1).trim() : trimmed;
      if (!core) return segment;

      if (isLikelyQuestionSentence(core)) {
        return core + "?";
      }

      if (!trailing) {
        return core + ".";
      }

      return core + trailing;
    });
  }

  function normalizeCapitalization(text) {
    if (!text || typeof text !== "string") return text;

    return text.replace(/(^|[.!?]\s+|\n\s*)([a-z])/g, function (_, prefix, letter) {
      return prefix + letter.toUpperCase();
    });
  }

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent =
      "." + WRAP_CLASS + "{position:relative;display:block;width:100%}" +
      ".title-fixer-input-pad{padding-right:40px !important}" +
      ".title-fixer-btn{position:absolute;top:50%;right:8px;transform:translateY(-50%);display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border:1px solid rgba(125,211,252,0.95);background:linear-gradient(135deg,#effcff 0%,#d7f2ff 45%,#bde9ff 100%);color:#075985;border-radius:999px;cursor:pointer;padding:0;z-index:2;box-shadow:0 0 0 1px rgba(255,255,255,0.75) inset,0 4px 10px rgba(14,165,233,0.28),0 0 14px rgba(56,189,248,0.22);transition:transform .2s ease,box-shadow .2s ease,filter .2s ease;overflow:hidden}" +
      ".title-fixer-btn::after{content:'';position:absolute;inset:-40% -70%;background:linear-gradient(120deg,rgba(255,255,255,0) 30%,rgba(255,255,255,0.85) 50%,rgba(255,255,255,0) 70%);transform:translateX(-120%) rotate(10deg);animation:titleFixerShimmer 2.4s ease-in-out infinite}" +
      ".title-fixer-btn-textarea{top:8px;transform:none}" +
      ".title-fixer-ai{display:inline-flex;align-items:center;justify-content:center;font-size:12px;line-height:1;filter:drop-shadow(0 0 4px rgba(255,255,255,0.9));position:relative;z-index:1}" +
      ".title-fixer-btn:hover{transform:translateY(-50%) scale(1.06);box-shadow:0 0 0 1px rgba(255,255,255,0.9) inset,0 8px 16px rgba(14,165,233,0.32),0 0 18px rgba(56,189,248,0.34);filter:saturate(1.1)}" +
      ".title-fixer-btn:disabled{opacity:.65;cursor:not-allowed}";
    style.textContent += "@keyframes titleFixerShimmer{0%{transform:translateX(-120%) rotate(10deg)}45%{transform:translateX(10%) rotate(10deg)}100%{transform:translateX(140%) rotate(10deg)}}";
    document.head.appendChild(style);
  }

  function setButtonLabel(button, label) {
    button.innerHTML = '<span class="title-fixer-ai" aria-hidden="true">✨</span>';
    button.setAttribute("aria-label", label);
    button.title = label;
  }

  function getFixableFieldType(el) {
    if (!el) return null;
    if (el.dataset.titleFixerIgnore === "true") return false;

    const tag = (el.tagName || "").toUpperCase();
    const id = (el.id || "").toLowerCase();
    const name = (el.name || "").toLowerCase();
    const placeholder = (el.placeholder || "").toLowerCase();

    if (tag === "INPUT") {
      if (el.type && el.type !== "text" && el.type !== "search") return null;
      if (
        id.includes("title") ||
        name.includes("title") ||
        placeholder.includes("title") ||
        id.includes("productname") ||
        name.includes("productname") ||
        placeholder.includes("product name")
      ) {
        return "title";
      }
    }

    if (tag === "TEXTAREA") {
      if (
        placeholder.includes("on your mind") ||
        id.includes("postfromfeedcontent") ||
        id.includes("create-post-textarea")
      ) {
        return "mind";
      }
    }

    return null;
  }

  function applyCorrections(text, matches) {
    let result = text;
    const sorted = (matches || [])
      .filter(function (m) {
        return (
          typeof m.offset === "number" &&
          typeof m.length === "number" &&
          m.replacements &&
          m.replacements.length > 0
        );
      })
      .sort(function (a, b) {
        return b.offset - a.offset;
      });

    sorted.forEach(function (m) {
      const replacement = m.replacements[0].value;
      result = result.slice(0, m.offset) + replacement + result.slice(m.offset + m.length);
    });

    return result;
  }

  async function fixTitle(input, button, baseLabel) {
    const original = (input.value || "").trim();
    if (!original || button.disabled) return;

    const initialText = baseLabel;
    button.disabled = true;
    setButtonLabel(button, "Fixing...");

    try {
      let preparedText = original;

      preparedText = await applyAIPunctuation(preparedText);
      preparedText = normalizeQuestionPunctuation(preparedText);
      preparedText = normalizeCapitalization(preparedText);

      const response = await fetch("https://api.languagetool.org/v2/check", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ text: preparedText, language: "en-US" })
      });

      if (!response.ok) {
        throw new Error("Grammar service unavailable");
      }

      const data = await response.json();
      const fixed = applyCorrections(preparedText, data.matches || []);
      input.value = fixed;

      const changed = fixed !== original;
      setButtonLabel(button, changed ? "Fixed" : "No changes");
      setTimeout(function () {
        setButtonLabel(button, baseLabel);
      }, 1200);
    } catch (err) {
      console.error("Title fixer error:", err);
      setButtonLabel(button, "Try again");
      setTimeout(function () {
        setButtonLabel(button, initialText);
      }, 1200);
    } finally {
      button.disabled = false;
    }
  }

  function scheduleAutoFix(input, button, baseLabel) {
    const value = (input.value || "").trim();
    if (value.length < MIN_TEXT_LENGTH) return;

    const existingTimer = autoFixTimers.get(input);
    if (existingTimer) {
      clearTimeout(existingTimer);
    }

    const timerId = setTimeout(function () {
      fixTitle(input, button, baseLabel);
      autoFixTimers.delete(input);
    }, AUTO_FIX_DELAY_MS);

    autoFixTimers.set(input, timerId);
  }

  function attachButton(input) {
    const fieldType = getFixableFieldType(input);
    if (!fieldType || input.getAttribute(CONTROL_ATTR) === "true") return;

    const buttonLabel = fieldType === "title" ? "Fix Title" : "Fix Text";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = BUTTON_CLASS;
    if ((input.tagName || "").toUpperCase() === "TEXTAREA") {
      btn.classList.add("title-fixer-btn-textarea");
    }
    setButtonLabel(btn, buttonLabel);
    btn.addEventListener("click", function () {
      fixTitle(input, btn, buttonLabel);
    });
    input.addEventListener("input", function () {
      scheduleAutoFix(input, btn, buttonLabel);
    });

    if (!input.classList.contains("title-fixer-input-pad")) {
      input.classList.add("title-fixer-input-pad");
    }

    const parent = input.parentNode;
    if (!parent) return;

    if (parent.classList && parent.classList.contains(WRAP_CLASS)) {
      parent.appendChild(btn);
    } else {
      const wrapper = document.createElement("div");
      wrapper.className = WRAP_CLASS;
      parent.insertBefore(wrapper, input);
      wrapper.appendChild(input);
      wrapper.appendChild(btn);
    }

    input.setAttribute(CONTROL_ATTR, "true");
  }

  function scan(root) {
    const scope = root || document;
    const inputs = scope.querySelectorAll("input, textarea");
    inputs.forEach(attachButton);
  }

  function init() {
    injectStyles();
    scan(document);

    const observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        mutation.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          if (node.matches && node.matches("input, textarea")) {
            attachButton(node);
          }
          if (node.querySelectorAll) {
            scan(node);
          }
        });
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();