// ui.js — shared in-page dialogs for the app and the admin panel.
/* ---------- In-page dialogs (replace prompt / alert / confirm) ----------
   Native dialogs block the page, ignore the theme and can't be styled or
   read well on a phone. These return promises; Esc or the backdrop = cancel.
   While a dialog is open the rest of the page is inert, so neither the
   keyboard nor a screen reader can wander behind it. A destructive dialog
   starts on Cancel: a stray Enter must never delete anything. */
let _dlgSeq = 0;
function uiDialog({title, text, input, ok = "OK", cancel = "Cancel", danger = false, type = "text"}){
  return new Promise(res => {
    const n = ++_dlgSeq;
    const back = document.createElement("div"); back.className = "dlg-back";
    const d = document.createElement("div"); d.className = "dlg";
    d.setAttribute("role", danger ? "alertdialog" : "dialog"); d.setAttribute("aria-modal", "true");
    const h = document.createElement("h2"); h.id = "dlgT" + n; h.textContent = title || (input !== undefined ? "Enter a value" : "Confirm");
    d.setAttribute("aria-labelledby", h.id); d.appendChild(h);
    if (text){
      const p = document.createElement("p"); p.id = "dlgD" + n; p.textContent = text;
      d.setAttribute("aria-describedby", p.id); d.appendChild(p);
    }
    let inp = null;
    if (input !== undefined){
      inp = document.createElement("input"); inp.type = type; inp.value = input == null ? "" : String(input);
      inp.setAttribute("aria-labelledby", h.id);
      if (text) inp.setAttribute("aria-describedby", "dlgD" + n);
      if (type === "number"){ inp.min = "0"; inp.inputMode = "numeric"; }
      d.appendChild(inp);
    }
    const acts = document.createElement("div"); acts.className = "acts";
    const bc = document.createElement("button"); bc.type = "button"; bc.className = "dlg-btn"; bc.textContent = cancel;
    const bo = document.createElement("button"); bo.type = "button"; bo.className = "dlg-btn " + (danger ? "danger" : "primary"); bo.textContent = ok;
    acts.append(bc, bo); d.appendChild(acts); back.appendChild(d);

    // everything else on the page becomes inert while the dialog is open
    const others = [...document.body.children].filter(el => !el.inert && el.tagName !== "SCRIPT");
    others.forEach(el => { el.inert = true; });
    document.body.appendChild(back);

    const prev = document.activeElement;
    const close = v => {
      document.removeEventListener("keydown", key, true);
      back.remove();
      others.forEach(el => { el.inert = false; });
      if (prev && prev.focus) prev.focus();
      res(v);
    };
    const key = e => {
      if (e.key === "Escape"){ e.preventDefault(); e.stopImmediatePropagation(); close(inp ? null : false); }
      else if (e.key === "Enter" && inp && document.activeElement === inp){ e.preventDefault(); close(inp.value); }
      else if (e.key === "Tab"){
        const f = [...d.querySelectorAll("input,button")]; const i = f.indexOf(document.activeElement);
        if (e.shiftKey && i <= 0){ e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && i === f.length - 1){ e.preventDefault(); f[0].focus(); }
      }
    };
    document.addEventListener("keydown", key, true);
    bc.onclick = () => close(inp ? null : false);
    bo.onclick = () => close(inp ? inp.value : true);
    back.addEventListener("click", e => { if (e.target === back) close(inp ? null : false); });
    if (inp){ inp.focus(); inp.select(); } else (danger ? bc : bo).focus();
  });
}
function uiConfirm(text, o = {}){ return uiDialog({title: o.title || "Are you sure?", text, ok: o.ok || "Continue", danger: !!o.danger}); }
function uiPrompt(text, value, o = {}){ return uiDialog({title: o.title || "", text, input: value, ok: o.ok || "Save", type: o.type || "text"}); }
