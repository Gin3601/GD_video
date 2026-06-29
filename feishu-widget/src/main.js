import "./styles.css";

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const API_BASE_KEY = "aiVideoFactory.apiBaseUrl";
const FIELD_NAMES = {
  type: ["视频类型", "type"],
  style: ["风格", "style"],
  duration: ["时长", "duration"],
  status: ["状态", "status"],
  backgroundMode: ["背景生成方式", "background_mode"],
  backgroundUrl: ["指定背景视频", "background_url"],
  backgroundPrompt: ["AI背景提示词", "背景提示词", "video_prompt"],
  model: ["模型", "model"],
  provider: ["视频来源", "provider"]
};

const state = {
  apiBaseUrl: localStorage.getItem(API_BASE_KEY) || DEFAULT_API_BASE_URL,
  records: [],
  loading: false,
  notice: "",
  noticeType: "",
  generatedBackgroundUrl: "",
  settingsOpen: false,
  form: {
    type: "morning",
    style: "healing",
    duration: 30,
    provider: "local",
    model: "",
    backgroundPrompt: ""
  }
};

const app = document.querySelector("#app");

function apiUrl(path) {
  return `${state.apiBaseUrl.replace(/\/$/, "")}${path}`;
}

async function request(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.message || `HTTP ${response.status}`);
  }
  return data;
}

function fieldText(value, fallback = "") {
  if (value === null || value === undefined) {
    return fallback;
  }
  if (Array.isArray(value)) {
    return fieldText(value[0], fallback);
  }
  if (typeof value === "object") {
    return value.text || value.name || value.value || fallback;
  }
  return String(value) || fallback;
}

function fieldByNames(fields, names, fallback = "") {
  for (const name of names) {
    if (Object.prototype.hasOwnProperty.call(fields, name)) {
      return fieldText(fields[name], fallback);
    }
  }
  return fallback;
}

function fieldUrl(value) {
  if (!value) {
    return "";
  }
  if (typeof value === "string") {
    return value.startsWith("http") ? value : "";
  }
  if (Array.isArray(value)) {
    return value.map(fieldUrl).find(Boolean) || "";
  }
  if (typeof value === "object") {
    return fieldUrl(value.link || value.url || value.text || value.value);
  }
  return "";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setNotice(message, type = "") {
  state.notice = message;
  state.noticeType = type;
  render();
}

async function loadRecords() {
  state.loading = true;
  render();
  try {
    const data = await request("/api/feishu/records?page_size=100");
    state.records = data.items || [];
    setNotice(`已加载 ${state.records.length} 条记录`, "success");
  } catch (error) {
    setNotice(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

async function createRecord() {
  state.loading = true;
  render();
  try {
    await request("/api/feishu/records", {
      method: "POST",
      body: JSON.stringify({
        fields: {
          视频类型: state.form.type,
          风格: state.form.style,
          时长: Number(state.form.duration),
          状态: "pending",
          视频来源: state.form.provider,
          模型: state.form.model.trim(),
          AI背景提示词: state.form.backgroundPrompt.trim()
        }
      })
    });
    await loadRecords();
    setNotice("记录已创建", "success");
  } catch (error) {
    setNotice(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

async function createVideo() {
  // Direct video creation uses the same backend API as non-Feishu clients.
  state.loading = true;
  render();
  try {
    const provider = state.form.provider || "local";
    const model = state.form.model.trim();
    const backgroundPrompt = state.form.backgroundPrompt.trim();
    const hasBackgroundUrl = Boolean(state.generatedBackgroundUrl);
    // Reuse a generated background when available; otherwise SiliconFlow creates one during full video generation.
    const data = await request("/api/video/create", {
      method: "POST",
      body: JSON.stringify({
        type: state.form.type,
        style: state.form.style,
        duration: Number(state.form.duration),
        provider,
        model: model || undefined,
        background_mode: hasBackgroundUrl ? "url" : provider === "siliconflow" ? "ai" : "random",
        background_url: hasBackgroundUrl ? state.generatedBackgroundUrl : undefined,
        video_prompt: backgroundPrompt || undefined
      })
    });
    setNotice(`任务已创建：${data.task_id}`, "success");
  } catch (error) {
    setNotice(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

async function createBackground() {
  // Standalone background generation previews provider output before a full video task is created.
  if (state.form.provider !== "siliconflow") {
    setNotice("请选择 SiliconFlow 后生成背景", "error");
    return;
  }

  const prompt = state.form.backgroundPrompt.trim() || buildDefaultBackgroundPrompt();
  state.loading = true;
  render();
  try {
    const data = await request("/api/video/background/create", {
      method: "POST",
      body: JSON.stringify({
        provider: state.form.provider,
        model: state.form.model.trim() || undefined,
        prompt
      })
    });
    state.generatedBackgroundUrl = data.download_url || "";
    setNotice(`背景已生成：${data.download_url || data.remote_task_id}`, "success");
  } catch (error) {
    setNotice(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

function buildDefaultBackgroundPrompt() {
  // The default prompt keeps generated backgrounds vertical, clean, and reusable for final composition.
  return `Vertical 9:16 morning short-video background, ${state.form.style}, realistic, soft light, smooth camera movement, no text, no subtitles, no watermark`;
}

function recordParams(record) {
  // Record parameters support both Chinese Bitable field names and legacy English names.
  const fields = record.fields || {};
  const style = fieldByNames(fields, FIELD_NAMES.style, state.form.style);
  const type = fieldByNames(fields, FIELD_NAMES.type, state.form.type);
  const duration = fieldByNames(fields, FIELD_NAMES.duration, String(state.form.duration));
  const provider = fieldByNames(fields, FIELD_NAMES.provider, "siliconflow").toLowerCase();
  const model = fieldByNames(fields, FIELD_NAMES.model, state.form.model);
  const prompt = fieldByNames(fields, FIELD_NAMES.backgroundPrompt, "");
  return {
    type,
    style,
    duration,
    provider: provider || "siliconflow",
    model,
    prompt: prompt || buildRecordBackgroundPrompt({ type, style })
  };
}

function buildRecordBackgroundPrompt({ type, style }) {
  // Row background generation keeps the asset suitable for later URL-based video composition.
  return `Vertical 9:16 ${type} short-video background, ${style}, realistic, soft morning light, smooth camera movement, no text, no subtitles, no watermark`;
}

async function createRecordBackground(recordId) {
  // A row background is generated first, then written back as the row's specified background video.
  const record = state.records.find((item) => item.record_id === recordId);
  if (!record) {
    setNotice("未找到记录", "error");
    return;
  }

  const params = recordParams(record);
  if (params.provider !== "siliconflow") {
    params.provider = "siliconflow";
  }

  state.loading = true;
  render();
  try {
    const data = await request("/api/video/background/create", {
      method: "POST",
      body: JSON.stringify({
        provider: params.provider,
        model: params.model || undefined,
        prompt: params.prompt
      })
    });
    const downloadUrl = data.download_url;
    if (!downloadUrl) {
      throw new Error("背景生成成功，但没有返回本地下载地址");
    }

    await request(`/api/feishu/records/${encodeURIComponent(recordId)}`, {
      method: "PATCH",
      body: JSON.stringify({
        fields: {
          指定背景视频: {
            link: downloadUrl,
            text: "生成背景"
          },
          背景生成方式: "指定视频",
          状态: "background_ready"
        }
      })
    });
    await loadRecords();
    setNotice(`背景已写回记录：${downloadUrl}`, "success");
  } catch (error) {
    setNotice(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

async function createTask(recordId) {
  state.loading = true;
  render();
  try {
    const data = await request(`/api/feishu/create-from-record/${encodeURIComponent(recordId)}`, {
      method: "POST"
    });
    await loadRecords();
    setNotice(`任务已创建：${data.task_id}`, "success");
  } catch (error) {
    setNotice(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

function saveApiBaseUrl() {
  const input = document.querySelector("#apiBaseUrl");
  state.apiBaseUrl = input.value.trim() || DEFAULT_API_BASE_URL;
  localStorage.setItem(API_BASE_KEY, state.apiBaseUrl);
  setNotice("接口地址已保存", "success");
}

function updateForm(event) {
  const { name, value } = event.target;
  state.form[name] = value;
}

function renderRecords() {
  if (!state.records.length) {
    return '<div class="empty">暂无记录</div>';
  }

  return state.records
    .map((record) => {
      const fields = record.fields || {};
      const style = fieldByNames(fields, FIELD_NAMES.style, "healing");
      const type = fieldByNames(fields, FIELD_NAMES.type, "morning");
      const duration = fieldByNames(fields, FIELD_NAMES.duration, "30");
      const status = fieldByNames(fields, FIELD_NAMES.status, "pending");
      const backgroundUrl = fieldUrl(fields["指定背景视频"] || fields.background_url);
      const title = `${type} / ${style}`;
      const safeRecordId = escapeHtml(record.record_id);
      const safeTitle = escapeHtml(title);
      const safeStatus = escapeHtml(status);
      const safeDuration = escapeHtml(duration);
      const safeBackground = escapeHtml(backgroundUrl ? "已生成背景" : "无背景");
      return `
        <article class="record-card">
          <div class="record-main">
            <div class="record-title">
              <strong title="${safeTitle}">${safeTitle}</strong>
              <span class="badge" title="${safeStatus}">${safeStatus}</span>
            </div>
            <div class="record-meta" title="${safeRecordId}">
              ${safeDuration}s · ${safeBackground} · ${safeRecordId}
            </div>
          </div>
          <div class="record-actions">
            <button class="ghost-button" data-action="create-record-background" data-record-id="${safeRecordId}" ${state.loading ? "disabled" : ""}>
              生成背景
            </button>
            <button class="ghost-button" data-action="create-task" data-record-id="${safeRecordId}" ${state.loading ? "disabled" : ""}>
              生成视频
            </button>
          </div>
        </article>
      `;
    })
    .join("");
}

function render() {
  app.innerHTML = `
    <section class="toolbar">
      <div class="title">
        <strong>AI Video Factory</strong>
        <span>${escapeHtml(state.apiBaseUrl)}</span>
      </div>
      <button class="icon-button" data-action="toggle-settings" title="设置">⚙</button>
      <button class="primary-button" data-action="refresh" ${state.loading ? "disabled" : ""}>刷新</button>
    </section>

    <section class="settings ${state.settingsOpen ? "open" : ""}">
      <input id="apiBaseUrl" class="input" value="${escapeHtml(state.apiBaseUrl)}" placeholder="https://your-api.example.com" />
      <button class="ghost-button" data-action="save-api">保存</button>
    </section>

    <section class="panel">
      <div class="form-grid">
        <div class="field">
          <label for="type">类型</label>
          <select id="type" name="type" class="select" data-action="form-input">
            <option value="morning" ${state.form.type === "morning" ? "selected" : ""}>morning</option>
          </select>
        </div>
        <div class="field">
          <label for="style">风格</label>
          <input id="style" name="style" class="input" value="${escapeHtml(state.form.style)}" data-action="form-input" />
        </div>
        <div class="field">
          <label for="duration">秒数</label>
          <input id="duration" name="duration" class="input" type="number" min="5" max="180" value="${escapeHtml(state.form.duration)}" data-action="form-input" />
        </div>
      </div>

      <div class="source-row">
        <span>视频来源</span>
        <label class="radio-option">
          <input type="radio" name="provider" value="local" data-action="form-input" ${state.form.provider === "local" ? "checked" : ""} />
          Local GPU
        </label>
        <label class="radio-option">
          <input type="radio" name="provider" value="siliconflow" data-action="form-input" ${state.form.provider === "siliconflow" ? "checked" : ""} />
          SiliconFlow
        </label>
      </div>

      <div class="model-row ${state.form.provider === "siliconflow" ? "open" : ""}">
        <label for="model">模型</label>
        <input id="model" name="model" class="input" value="${escapeHtml(state.form.model)}" data-action="form-input" placeholder="Wan-AI/Wan2.2-T2V-A14B" />
      </div>

      <div class="prompt-row ${state.form.provider === "siliconflow" ? "open" : ""}">
        <label for="backgroundPrompt">背景提示词</label>
        <textarea id="backgroundPrompt" name="backgroundPrompt" class="textarea" data-action="form-input" rows="3" placeholder="清晨阳光，治愈，真实摄影风格，竖屏9:16，无文字，无水印">${escapeHtml(state.form.backgroundPrompt)}</textarea>
      </div>

      <div class="actions">
        <button class="ghost-button" data-action="create-background" ${state.loading ? "disabled" : ""}>生成背景</button>
        <button class="ghost-button" data-action="create-video" ${state.loading ? "disabled" : ""}>生成视频</button>
        <button class="primary-button" data-action="create-record" ${state.loading ? "disabled" : ""}>新增记录</button>
      </div>

      <div class="notice ${state.noticeType}">${escapeHtml(state.notice || "等待操作")}</div>

      <div class="record-list">
        ${state.loading ? '<div class="empty">加载中</div>' : renderRecords()}
      </div>
    </section>
  `;
}

app.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) {
    return;
  }

  const action = target.dataset.action;
  if (action === "refresh") {
    loadRecords();
  }
  if (action === "toggle-settings") {
    state.settingsOpen = !state.settingsOpen;
    render();
  }
  if (action === "save-api") {
    saveApiBaseUrl();
  }
  if (action === "create-record") {
    createRecord();
  }
  if (action === "create-video") {
    createVideo();
  }
  if (action === "create-background") {
    createBackground();
  }
  if (action === "create-record-background") {
    createRecordBackground(target.dataset.recordId);
  }
  if (action === "create-task") {
    createTask(target.dataset.recordId);
  }
});

app.addEventListener("input", (event) => {
  const target = event.target;
  if (target.dataset.action === "form-input") {
    updateForm(event);
  }
});

render();
loadRecords();
