/* Paradigme — first-run setup (LLM and optional email) */
(function () {
  const PROV = {
    groq:      { name: "Groq Cloud", tag: "Cloud provider", key: true,  url: "https://api.groq.com/openai/v1", model: "llama-3.3-70b-versatile",
                 help: 'Create an API key at <a href="https://console.groq.com/keys" target="_blank">console.groq.com/keys</a> → « Create API Key » → copy the key (starts with <code>gsk_</code>).' },
    openai:    { name: "OpenAI", tag: "Cloud provider", key: true, url: "https://api.openai.com/v1", model: "gpt-4o-mini",
                 help: 'Get a key at <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com/api-keys</a> (starts with <code>sk-</code>).' },
    anthropic: { name: "Claude (Anthropic)", tag: "Cloud provider", key: true, url: "https://api.anthropic.com/v1", model: "claude-sonnet-4-5",
                 help: 'Get a key at <a href="https://console.anthropic.com/settings/keys" target="_blank">console.anthropic.com</a> (starts with <code>sk-ant-</code>).' },
    ollama:    { name: "Ollama", tag: "Local inference", key: false, url: "http://127.0.0.1:11434", model: "llama3",
                 help: 'Install <a href="https://ollama.com/download" target="_blank">Ollama</a>, then run in a terminal : <code>ollama pull llama3</code>. Keep Ollama running.' },
    llamacpp:  { name: "llama.cpp", tag: "Local inference", key: false, url: "http://127.0.0.1:8090", model: "qwen2.5-3b-instruct",
                 help: 'Run <code>llama-server -m model.gguf --port 8090</code> then test the connection.' },
  };
  const st = { step: 1, prov: "groq", tested: false };
  const q = (s, r = document) => r.querySelector(s);

  function build() {
    const ov = document.createElement("div");
    ov.id = "setup-ov";
    ov.innerHTML = `
    <div class="setup-box" role="dialog" aria-modal="true">
      <div class="setup-head">
        <span class="logo">P</span>
        <div><h2>Welcome to Paradigme</h2><p>Configure your provider in three steps.</p></div>
        <button class="setup-x" title="Later">×</button>
      </div>
      <div class="setup-steps"><span data-s="1">1. AI engine</span><span data-s="2">2. Connection</span><span data-s="3">3. Email (optional)</span></div>

      <section data-p="1">
        <p class="setup-lead">Which AI engine should analyze your subjects?</p>
        <div class="setup-cards">${Object.entries(PROV).map(([k, p]) =>
          `<label class="setup-card"><input type="radio" name="sp" value="${k}" ${k === "groq" ? "checked" : ""}>
             <b>${p.name}</b><small>${p.tag}</small></label>`).join("")}</div>
      </section>

      <section data-p="2" hidden>
        <p class="setup-help" id="sp-help"></p>
        <label id="sp-key-row">API key <input id="sp-key" type="password" autocomplete="off" placeholder="Paste your API key"></label>
        <details id="sp-adv"><summary>Advanced settings</summary>
          <label>Server URL <input id="sp-url" type="text"></label>
          <label>Model <input id="sp-model" type="text"></label>
        </details>
        <div class="setup-test"><button id="sp-test" class="btn-secondary">Test connection</button><span id="sp-res"></span></div>
      </section>

      <section data-p="3" hidden>
        <p class="setup-lead">Receive PDF reports by email? <small>(optional — editable later in Settings)</small></p>
        <label class="setup-inline"><input type="checkbox" id="se-on"> Enable email delivery</label>
        <div id="se-fields" hidden>
          <label>Sender email address <input id="se-user" type="email" placeholder="user@example.com"></label>
          <label>Application password <input id="se-pwd" type="password" placeholder="Application password"></label>
          <p class="setup-help">For Gmail, use an <a href="https://myaccount.google.com/apppasswords" target="_blank">application password</a> with two-step verification enabled.</p>
          <label>Recipient <input id="se-to" type="email" placeholder="(defaults to the sender address)"></label>
          <label>SMTP server <input id="se-host" type="text" value="smtp.gmail.com"></label>
        </div>
      </section>

      <div class="setup-foot">
        <button id="sp-back" class="btn-secondary">Back</button>
        <span class="setup-grow"></span>
        <button id="sp-next" class="primary">Next</button>
      </div>
    </div>`;
    document.body.appendChild(ov);

    q(".setup-x", ov).onclick = close;
    q("#sp-back", ov).onclick = () => go(st.step - 1);
    q("#sp-next", ov).onclick = next;
    q("#sp-test", ov).onclick = test;
    q("#se-on", ov).onchange = e => (q("#se-fields").hidden = !e.target.checked);
    ov.querySelectorAll('input[name="sp"]').forEach(r => r.onchange = () => { st.prov = r.value; st.tested = false; });
    q("#sp-key", ov).oninput = () => { st.tested = false; q("#sp-res").textContent = ""; };
    go(1);
  }

  function go(n) {
    st.step = Math.max(1, Math.min(3, n));
    document.querySelectorAll("#setup-ov section").forEach(s => s.hidden = +s.dataset.p !== st.step);
    document.querySelectorAll(".setup-steps span").forEach(s => s.classList.toggle("on", +s.dataset.s <= st.step));
    q("#sp-back").style.visibility = st.step === 1 ? "hidden" : "visible";
    q("#sp-next").textContent = st.step === 3 ? "Finish" : "Next";
    if (st.step === 2) {
      const p = PROV[st.prov];
      q("#sp-help").innerHTML = p.help;
      q("#sp-key-row").hidden = !p.key;
      q("#sp-url").value = p.url; q("#sp-model").value = p.model;
      q("#sp-adv").open = !p.key;
      q("#sp-res").textContent = "";
    }
  }

  function payload() {
    return { provider: st.prov, api_key: q("#sp-key").value.trim(),
             base_url: q("#sp-url").value.trim(), model: q("#sp-model").value.trim() };
  }

  async function test() {
    const res = q("#sp-res");
    res.style.color = "var(--muted)"; res.textContent = "Testing...";
    try {
      const r = await (await fetch("/api/setup/test", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) })).json();
      st.tested = r.ok;
      res.style.color = r.ok ? "var(--positive)" : "var(--negative)";
      res.textContent = (r.ok ? "✔ " : "✖ ") + r.message;
      return r.ok;
    } catch (e) { res.style.color = "var(--negative)"; res.textContent = "✖ Error"; return false; }
  }

  async function next() {
    if (st.step === 2) {
      if (PROV[st.prov].key && !q("#sp-key").value.trim()) {
        q("#sp-res").style.color = "var(--negative)"; q("#sp-res").textContent = "API key required"; return;
      }
      if (!st.tested && !(await test())) {
        if (!confirm("Connection failed. Continue anyway?")) return;
      }
    }
    if (st.step < 3) return go(st.step + 1);
    const body = payload();
    if (q("#se-on").checked) body.email = { enabled: true, smtp_user: q("#se-user").value,
      smtp_password: q("#se-pwd").value, to_addr: q("#se-to").value, smtp_host: q("#se-host").value, smtp_port: 465 };
    const r = await fetch("/api/setup/save", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (r.ok) { close(); try { loadConfig(); refreshLLMStatus(); } catch (e) {} }
    else alert("Could not save settings");
  }

  function close() { const o = q("#setup-ov"); if (o) o.remove(); }

  window.openSetupWizard = () => { close(); st.step = 1; st.tested = false; build(); };

  // Setup wizard button in Settings
  const save = document.getElementById("btn-save-cfg");
  if (save) {
    const b = document.createElement("button");
    b.className = "btn-secondary"; b.textContent = "Setup wizard";
    b.style.marginLeft = "8px"; b.onclick = window.openSetupWizard;
    save.insertAdjacentElement("afterend", b);
  }

  fetch("/api/setup/status").then(r => r.json()).then(s => { if (s.needs_setup) window.openSetupWizard(); }).catch(() => {});
})();
