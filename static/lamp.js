// lamp.js — the sign-in pages' lamp. Pull the cord to change the light:
// cyan → warm → violet → lights out → cyan. The choice is a per-device
// convenience kept in localStorage; the pages work the same without it.
(function(){
  const COLORS = ["cyan", "warm", "violet", "off"];
  const NAMES = {cyan: "Cyan", warm: "Warm glow", violet: "Violet", off: "Lights out"};
  const stage = document.getElementById("stage");
  if (!stage) return;

  stage.innerHTML =
    '<div class="cone"></div><div class="floor"></div>' +
    '<span class="fly"></span><span class="fly"></span><span class="fly"></span><span class="fly"></span><span class="fly"></span>' +
    '<button type="button" class="big-lamp" id="bigLamp">' +
      '<svg viewBox="0 0 240 640" aria-hidden="true">' +
        '<line class="pole" x1="120" y1="104" x2="120" y2="600"/>' +
        '<ellipse class="base" cx="120" cy="606" rx="46" ry="11"/>' +
        '<path class="shade" d="M70 108 Q120 40 170 108 Z"/>' +
        '<ellipse class="bulb" cx="120" cy="112" rx="13" ry="7"/>' +
        '<g class="pull"><line class="cord" x1="154" y1="104" x2="154" y2="188"/>' +
        '<rect class="knob" x="148" y="186" width="12" height="20" rx="6"/></g>' +
      '</svg>' +
    '</button>' +
    '<div class="lamp-hint">Pull the cord · <b id="lampName"></b></div>';

  const lamp = document.getElementById("bigLamp");
  const name = document.getElementById("lampName");

  function apply(c, animate){
    document.body.dataset.lamp = c;
    lamp.setAttribute("aria-label", "Lamp: " + NAMES[c] + ". Press to change the light.");
    if (name) name.textContent = NAMES[c];
    try { localStorage.setItem("lira_lamp", c); } catch (e) {}
    if (animate){ lamp.classList.remove("pulled"); void lamp.offsetWidth; lamp.classList.add("pulled"); }
  }

  let current = "cyan";
  try { const v = localStorage.getItem("lira_lamp"); if (COLORS.includes(v)) current = v; } catch (e) {}
  apply(current, false);

  lamp.addEventListener("click", () => {
    current = COLORS[(COLORS.indexOf(current) + 1) % COLORS.length];
    apply(current, true);
  });
})();
