const $ = (id) => document.getElementById(id);
const LEVEL = { ok: "🟢", warn: "🟡", risk: "🔴" };

// 服务导流链接:改成你的小红书主页/私域
const SERVICE_URL = "#";

$("file").addEventListener("change", (e) => {
  const f = e.target.files[0];
  $("fname").textContent = f ? f.name : "";
});

// 目标期刊/会议预设(定向检查是本工具的差异化能力)
fetch("/api/venues")
  .then((r) => r.json())
  .then((list) => {
    $("venue").innerHTML = list
      .map((v) => `<option value="${v.key}">目标:${v.name}</option>`)
      .join("");
  })
  .catch(() => {});

async function runCheck(unlock = "") {
  const text = $("text").value;
  const file = $("file").files[0];
  if (!text.trim() && !file) {
    alert("请粘贴论文文本或上传文件");
    return;
  }
  const fd = new FormData();
  fd.append("text", text);
  fd.append("target_words", $("tw").value || "");
  fd.append("venue", $("venue").value || "generic");
  fd.append("unlock", unlock);
  if (file) fd.append("file", file);

  const btn = unlock ? $("unlockBtn") : $("run");
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = "分析中…";
  try {
    const r = await fetch("/api/check", { method: "POST", body: fd });
    const data = await r.json();
    if (!r.ok) {
      alert(data.error || "分析失败");
      return;
    }
    render(data);
  } catch (err) {
    alert("网络错误,请重试");
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

function render(d) {
  $("result").classList.remove("hidden");

  // 总览计数
  $("counts").innerHTML =
    `<span style="color:var(--risk)">🔴 ${d.counts.risk} 项需重点处理</span>` +
    `<span style="color:var(--warn)">🟡 ${d.counts.warn} 项建议优化</span>` +
    `<span style="color:var(--ok)">🟢 ${d.counts.ok} 项通过</span>`;

  // 九宫格状态
  $("grid").innerHTML = d.summary
    .map((s) => `<div class="item"><span class="dot">${LEVEL[s.level]}</span>${s.title}</div>`)
    .join("");

  const detail = $("detail");
  const paywall = $("paywall");

  if (d.paid) {
    paywall.classList.add("hidden");
    detail.innerHTML =
      `<a class="dl-btn" id="dl">⬇ 下载完整报告 (Markdown)</a>` +
      d.detail
        .map(
          (b) =>
            `<div class="block"><h4>${LEVEL[b.level]} ${b.title}</h4><ul>` +
            b.findings.map((f) => `<li>${fmtFinding(f)}</li>`).join("") +
            `</ul></div>`
        )
        .join("");
    // 下载
    $("dl").onclick = () => {
      const blob = new Blob([d.report_md], { type: "text/markdown" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "投稿前自检报告.md";
      a.click();
    };
  } else {
    detail.innerHTML = "";
    paywall.classList.remove("hidden");
    $("teaser").textContent = d.teaser
      ? `⚠️ 检测到风险项:「${d.teaser}」等 —— 完整报告告诉你具体问题在哪、怎么改。`
      : "完整报告告诉你每一项的具体问题和改法。";
    $("priceText").textContent = d.price_text || "";
    const pay = $("payLink");
    if (d.pay_url) {
      pay.href = d.pay_url;
    } else {
      pay.textContent = "(店主还没配置收款方式)";
      pay.removeAttribute("href");
    }
  }
  $("serviceLink").href = SERVICE_URL;
  $("result").scrollIntoView({ behavior: "smooth" });
}

function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

// findings 文本是给 CLI 用的 Markdown:去掉行首"- ",把 **x** 转成 <b>x</b>
function fmtFinding(f) {
  return escapeHtml(f)
    .replace(/^\s*-\s*/, "")
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}

$("run").addEventListener("click", () => runCheck(""));
$("unlockBtn").addEventListener("click", () => runCheck($("unlock").value));
