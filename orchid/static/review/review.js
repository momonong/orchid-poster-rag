"use strict";
(() => {
  const base = new URL(".", document.currentScript.src);
  const $ = id => document.getElementById(id);
  let key = "", kind = "questions", offset = 0, total = 0, requestVersion = 0;
  let query = {q:"", language:"", status:""};
  const limit = 25;
  const sections = {overview:"完整海報",intro:"Introduction",methods:"Methods",clue1:"Clue 1",clue2:"Clue 2",clue3:"Clue 3",discussion:"Discussion",references:"References",supplementary:"Supplementary"};
  const statuses = {answered:"已回答",unknown:"未取得可確認回答",busy:"忙碌",unavailable:"服務無法使用",pending:"處理中",interrupted:"已中斷"};
  const clarity = {clear:"清楚",partly:"部分清楚",unclear:"不太清楚"};
  $("filter-panel").open = matchMedia("(min-width:641px)").matches;
  const date = value => {
    const parsed = new Date(value);
    return value && Number.isFinite(parsed.getTime()) ? new Intl.DateTimeFormat("zh-TW",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(parsed) : "—";
  };
  function element(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function logout() {
    key = ""; requestVersion++;
    $("items").replaceChildren(); $("workspace").hidden = true; $("logout").hidden = true;
    $("login-panel").hidden = false; $("password").value = ""; $("message").textContent = "";
    $("password").focus();
  }
  function render(items) {
    $("items").replaceChildren();
    if (!items.length) $("items").append(element("p", "目前沒有符合條件的紀錄。", "empty"));
    for (const item of items) {
      const row = element("article", undefined, "record");
      const meta = element("div", undefined, "record-meta");
      meta.append(element("time", date(item.created_at)), element("span", sections[item.section] || item.section || "未指定區塊"), element("span", item.language === "zh-TW" ? "繁體中文" : "English"));
      row.append(meta);
      if (kind === "questions") {
        const state = Object.hasOwn(statuses,item.status) ? item.status : "";
        meta.append(element("span", statuses[state] || "未標示狀態", "status " + state));
        row.append(element("h2", item.question, "question"));
        const details = element("details");
        details.append(element("summary", "查看已保存的回答"), element("div", item.answer || "尚未保存回答。", "answer"));
        if (item.citations.length) details.append(element("p", "引用來源：" + item.citations.join("、"), "citations"));
        if (item.latency_ms !== null) details.append(element("p", "處理時間 " + (item.latency_ms/1000).toFixed(1) + " 秒", "citations"));
        row.append(details);
      } else {
        meta.append(element("span", clarity[item.clarity] || "未評分", "status"));
        row.append(element("p", item.comment || "（只留下評分，沒有文字留言）", "comment"));
      }
      $("items").append(row);
    }
    $("range").textContent = total ? `${offset+1}–${Math.min(offset+limit,total)} 筆，共 ${total} 筆` : "0 筆紀錄";
    $("page").textContent = `第 ${Math.floor(offset/limit)+1} 頁`;
    $("previous").disabled = offset === 0;
    $("next").disabled = offset+limit >= total;
    $("updated").textContent = "更新時間 " + date(new Date().toISOString());
  }
  async function load() {
    const version = ++requestVersion;
    $("message").textContent = "";
    $("items").setAttribute("aria-busy", "true");
    $("range").textContent = "讀取紀錄中…";
    for (const id of ["previous","next","refresh"]) $(id).disabled = true;
    try {
      const url = new URL("api/records", base);
      url.search = new URLSearchParams({...query,kind,limit,offset,status:kind === "questions" ? query.status : ""});
      const response = await fetch(url, {headers:{Authorization:"Bearer "+key}, cache:"no-store", credentials:"omit"});
      if (version !== requestVersion) return;
      if (response.status === 401) {logout(); throw new Error("審閱密碼不正確或已更換，請重新輸入。");}
      if (!response.ok) throw new Error(response.status === 503 ? "審閱入口或紀錄目前無法使用，請聯絡管理者或稍後再試。" : "無法讀取紀錄，請稍後再試。");
      const data = await response.json();
      if (version !== requestVersion) return;
      total = data.total;
      $("questions-count").textContent = data.totals.questions;
      $("feedback-count").textContent = data.totals.feedback;
      $("login-panel").hidden = true; $("workspace").hidden = false; $("logout").hidden = false;
      $("password").value = "";
      render(data.items);
    } catch (error) {
      if (version === requestVersion || !key) {
        $("message").textContent = error.message;
        $("range").textContent = "讀取失敗；請重新載入。";
        $("items").replaceChildren();
      }
    } finally {
      if (version === requestVersion) {
        $("items").setAttribute("aria-busy", "false");
        $("refresh").disabled = false;
      }
    }
  }
  $("login-form").addEventListener("submit", event => {event.preventDefault();key=$("password").value.trim();offset=0;load();});
  $("logout").addEventListener("click", logout);
  $("filters").addEventListener("submit", event => {event.preventDefault();offset=0;query={q:$("search").value.trim(),language:$("language").value,status:$("status").value};load();});
  $("refresh").addEventListener("click", load);
  $("previous").addEventListener("click", () => {offset=Math.max(0,offset-limit);load();});
  $("next").addEventListener("click", () => {offset+=limit;load();});
  document.querySelectorAll("[data-kind]").forEach(button => button.addEventListener("click", () => {
    kind=button.dataset.kind; offset=0;
    document.querySelectorAll("[data-kind]").forEach(tab => tab.setAttribute("aria-pressed",String(tab===button)));
    $("status-filter").hidden=kind!=="questions";
    load();
  }));
})();
