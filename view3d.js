'use strict';
// 3D presentation view: the market as a planet.
//   continents = sectors (related sectors sit next to each other), towers = companies, tower height = market value,
//   arcs = who sells to whom (light flows the way the money flows, buyer to seller).
// A scenario plays as a choreographed shock: the planet turns to the starting company, a blast wave crosses the surface,
// the shock flies along the links hop by hop, hit towers turn red and lose height, and the counters add up the damage.
// Needs vendor/three.min.js (r147); vendor/three-post.js adds the glow and is optional.
const G3 = (() => {
  const RAD = 100, T0 = 1.6, HOP = 1.8, FLY = 1.05, SLATE = [0.085, 0.1, 0.15], CS = 0.052;
  let box, renderer, composer, scene, camera, globe, planet, planetMat, towers, lossMesh, glow, lineMat, hotGroup, comets, beam, rings, hud, labelBox, ro, raf = 0;
  let ids = [], ix = {}, P = {}, H = {}, WD = {}, baseCol = {}, cont = [], arcs = {}, labels = [];
  let res = null, tl = null, lookT = 0, lookNow = 0, dist = 430, distTo = 430, targetQ = null, drag = null, moved = false, shake = 0, shown = 0, shownMine = 0, hoverId = null, lastT = 0;
  const waves = [];
  const v3 = (x, y, z) => new THREE.Vector3(x, y, z), rgb = h => { const c = new THREE.Color(h); return [c.r, c.g, c.b]; };
  const ease = t => t < 0 ? 0 : t > 1 ? 1 : t * t * (3 - 2 * t), FACE = v3(0.1, 0.46, 0.88).normalize(), FRONT = v3(0, 0.1, 1).normalize();
  const money = x => (x >= 0 ? '+' : '-') + fB(Math.abs(x));

  // ---------- layout: one continent per sector, biggest companies in the middle ----------
  function prep() {
    ids = OV_IDS.slice(); ids.forEach((id, i) => { ix[id] = i; });
    const names = LAY.sectors.map(s => s.name), sec = {};
    for (const id of ids) if (names.includes(N[id].sector)) sec[id] = N[id].sector;
    // private, overseas and government names settle on the continent of the company they trade with most
    for (let pass = 0; pass < 5; pass++) for (const id of ids) {
      if (sec[id]) continue;
      const vote = {}; for (const l of [...(bySeller[id] || []), ...(byBuyer[id] || [])]) { const o = l.from === id ? l.to : l.from; if (sec[o]) vote[sec[o]] = (vote[sec[o]] || 0) + 0.3 + W.demand[l.id].p; }
      const best = Object.keys(vote).sort((a, b) => vote[b] - vote[a])[0]; if (best) sec[id] = best;
    }
    for (const id of ids) if (!sec[id]) sec[id] = 'Information Technology';
    const n = names.length, pts = names.map((_, i) => { const y = 1 - 2 * (i + 0.5) / n, r = Math.sqrt(1 - y * y), a = i * 2.39996; return v3(r * Math.cos(a), y, r * Math.sin(a)); });
    // put sectors that trade with each other on neighbouring continents
    const cross = {}, key = (a, b) => a < b ? a + '|' + b : b + '|' + a;
    for (const l of OV_LINKS) { const a = sec[l.from], b = sec[l.to]; if (a !== b) cross[key(a, b)] = (cross[key(a, b)] || 0) + 1; }
    let order = names.slice();
    const cost = o => { let c = 0; for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) { const k = cross[key(o[i], o[j])]; if (k) c += k * pts[i].angleTo(pts[j]); } return c; };
    for (let best = cost(order), again = true; again;) { again = false; for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) { const o = order.slice(); [o[i], o[j]] = [o[j], o[i]]; const c = cost(o); if (c < best - 1e-9) { best = c; order = o; again = true; } } }
    const C = CS, groups = order.map(name => ids.filter(id => sec[id] === name).sort((a, b) => (N[b].cap || 0) - (N[a].cap || 0))), rad = groups.map(m => C * Math.sqrt(m.length));
    // let the continents settle: big sectors take more room, none sit on top of each other, and the gaps between them even out
    const cen = pts.map(p => p.clone()), away = (a, b, d) => { const t = a.clone().multiplyScalar(a.dot(b)).sub(b); if (t.length() < 1e-6) return; t.normalize(); a.multiplyScalar(Math.cos(d)).addScaledVector(t, Math.sin(d)).normalize(); };
    for (let it = 0; it < 400; it++) for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const ang = cen[i].angleTo(cen[j]), want = (rad[i] + rad[j]) * 0.97, d = 0.0009 * (rad[i] + rad[j]) / (ang * ang) + (ang < want ? (want - ang) * 0.25 : 0);
      const wi = rad[j] / (rad[i] + rad[j]), a0 = cen[i].clone(); away(cen[i], cen[j], d * wi); away(cen[j], a0, d * (1 - wi));
    }
    let sd = 4321; const rnd = () => { sd = (sd * 16807) % 2147483647; return sd / 2147483647; };
    order.forEach((name, i) => {
      const c = cen[i], members = groups[i], ph = [rnd() * 6.283, rnd() * 6.283, rnd() * 6.283];
      const e1 = v3().crossVectors(c, Math.abs(c.y) > 0.9 ? v3(1, 0, 0) : v3(0, 1, 0)).normalize(), e2 = v3().crossVectors(c, e1).normalize();
      members.forEach((id, k) => {
        // a loose spiral: tidy in the middle, ragged at the coast, with an uneven outline so no continent is a perfect circle
        const frac = Math.sqrt((k + 0.55) / members.length), th = k * 2.39996 + (rnd() - 0.5) * 0.6 * frac;
        const shape = 1 + frac * (0.2 * Math.sin(2 * th + ph[0]) + 0.13 * Math.sin(3 * th + ph[1]) + 0.07 * Math.sin(5 * th + ph[2]));
        const rho = C * Math.sqrt(k + 0.55) * shape * (1 + (rnd() - 0.5) * 0.3 * (0.35 + frac));
        P[id] = c.clone().multiplyScalar(Math.cos(rho)).addScaledVector(e1, Math.cos(th) * Math.sin(rho)).addScaledVector(e2, Math.sin(th) * Math.sin(rho)).normalize();
      });
      const r = rad[i] * 1.1, up = v3(0, 1, 0).addScaledVector(c, -c.y); if (up.length() < 0.2) up.set(0, 0, -1).addScaledVector(c, c.z); up.normalize();
      cont.push({ name, c, r, col: rgb((FAM_OF[name] || FAMILY[5]).color), at: c.clone().multiplyScalar(Math.cos(r * 1.08)).addScaledVector(up, Math.sin(r * 1.08)).multiplyScalar(RAD * 1.012), cap: members.reduce((s, id) => s + (N[id].cap || 0), 0), n: members.filter(id => N[id].sp).length });
    });
    for (const id of ids) { const cap = N[id].cap || 0; H[id] = 1.6 + 0.5 * Math.sqrt(cap); WD[id] = cap ? Math.min(2.9, 1.0 + 0.027 * Math.sqrt(cap)) : 0.9; baseCol[id] = rgb(famOf(id).color); }
    for (const l of OV_LINKS) arcs[l.id] = arc(P[l.from], P[l.to]);
  }
  function arc(a, b) {
    const om = a.angleTo(b), n = 12 + Math.floor(om * 14), lift = 0.05 + 0.4 * om / Math.PI, s = Math.sin(om) || 1e-6, out = [];
    for (let i = 0; i <= n; i++) { const t = i / n, p = a.clone().multiplyScalar(Math.sin((1 - t) * om) / s).addScaledVector(b, Math.sin(t * om) / s).normalize(); out.push(p.multiplyScalar(RAD * (1.006 + lift * Math.sin(Math.PI * t)))); }
    return out;
  }

  // ---------- scene ----------
  const spriteMat = () => new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { scale: { value: 1 } },
    vertexShader: `attribute float size; attribute vec3 color; varying vec3 vC; uniform float scale;
      void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); vC = color; gl_PointSize = size * scale * (360.0 / -mv.z); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `varying vec3 vC; void main(){ float d = length(gl_PointCoord - 0.5); if (d > 0.5) discard; float core = smoothstep(0.2, 0.05, d), halo = smoothstep(0.5, 0.0, d); gl_FragColor = vec4(vC * (core * 0.9 + halo * halo * 0.6), 1.0); }` });
  function build() {
    scene = new THREE.Scene(); scene.background = new THREE.Color(0x03040a);
    camera = new THREE.PerspectiveCamera(36, 1, 1, 4000); globe = new THREE.Group(); scene.add(globe);
    // stars
    const sp = [], sc = [], ss = []; let seed = 11; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (let i = 0; i < 1500; i++) { const y = rnd() * 2 - 1, a = rnd() * 6.283, r = Math.sqrt(1 - y * y), k = 0.25 + rnd() * 0.6; sp.push(r * Math.cos(a) * 1500, y * 1500, r * Math.sin(a) * 1500); sc.push(k * 0.8, k * 0.88, k); ss.push(1.5 + rnd() * 4); }
    const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.Float32BufferAttribute(sp, 3)); sg.setAttribute('color', new THREE.Float32BufferAttribute(sc, 3)); sg.setAttribute('size', new THREE.Float32BufferAttribute(ss, 1));
    const stars = new THREE.Points(sg, spriteMat()); stars.material.uniforms.scale.value = 4; scene.add(stars);
    // planet: dark ocean, grid, glowing sector continents, shock waves
    // night-lights map: every company lights the ground around it, so each continent takes the shape of its companies
    const TW = 2048, TH = 1024, cv = document.createElement('canvas'); cv.width = TW; cv.height = TH; const g2 = cv.getContext('2d');
    g2.fillStyle = '#000'; g2.fillRect(0, 0, TW, TH); g2.globalCompositeOperation = 'lighter';
    for (const id of ids) {
      const p = P[id], lat = Math.asin(Math.max(-1, Math.min(1, p.y))), x = (Math.atan2(p.x, p.z) / (2 * Math.PI) + 0.5) * TW, y = (0.5 - lat / Math.PI) * TH, rr = CS * 3.2 / Math.PI * TH, sx = 1 / Math.max(0.22, Math.cos(lat)), c = baseCol[id].map(v => Math.round(v * 255));
      for (const dx of [0, -TW, TW]) { g2.save(); g2.translate(x + dx, y); g2.scale(sx, 1); const gr = g2.createRadialGradient(0, 0, 0, 0, 0, rr); gr.addColorStop(0, `rgba(${c[0]},${c[1]},${c[2]},0.2)`); gr.addColorStop(0.5, `rgba(${c[0]},${c[1]},${c[2]},0.09)`); gr.addColorStop(1, `rgba(${c[0]},${c[1]},${c[2]},0)`); g2.fillStyle = gr; g2.beginPath(); g2.arc(0, 0, rr, 0, 6.2832); g2.fill(); g2.restore(); }
    }
    const lights = new THREE.CanvasTexture(cv); lights.minFilter = lights.magFilter = THREE.LinearFilter; lights.generateMipmaps = false; lights.wrapS = THREE.RepeatWrapping;
    planetMat = new THREE.ShaderMaterial({
      uniforms: { uMap: { value: lights }, uLit: { value: 1 },
        wDir: { value: Array.from({ length: 6 }, () => v3(0, 1, 0)) }, wAng: { value: [0, 0, 0, 0, 0, 0] }, wAmp: { value: [0, 0, 0, 0, 0, 0] }, wCol: { value: Array.from({ length: 6 }, () => v3(1, 0.2, 0.3)) } },
      vertexShader: `varying vec3 vN; varying vec3 vNv; varying vec3 vV; void main(){ vN = normalize(position); vNv = normalize(normalMatrix * normal); vec4 mv = modelViewMatrix * vec4(position, 1.0); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `varying vec3 vN; varying vec3 vNv; varying vec3 vV; uniform sampler2D uMap; uniform float uLit;
        uniform vec3 wDir[6]; uniform float wAng[6]; uniform float wAmp[6]; uniform vec3 wCol[6];
        float gl(float x, float st){ float d = abs(fract(x / st + 0.5) - 0.5) * st; return smoothstep(0.0035, 0.0, d); }
        void main(){ vec3 col = vec3(0.012, 0.017, 0.034);
          float lat = asin(clamp(vN.y, -1.0, 1.0)), lon = atan(vN.x, vN.z);
          col += vec3(0.03, 0.055, 0.105) * max(gl(lat, 0.2618), gl(lon, 0.2618) * step(abs(lat), 1.35));
          col += texture2D(uMap, vec2(lon / 6.2831853 + 0.5, 0.5 + lat / 3.14159265)).rgb * 0.34 * uLit;
          for (int j = 0; j < 6; j++) { float a = acos(clamp(dot(vN, wDir[j]), -1.0, 1.0));
            col += wCol[j] * wAmp[j] * (smoothstep(0.05, 0.0, abs(a - wAng[j])) + 0.06 * smoothstep(wAng[j], wAng[j] - 0.55, a) * step(a, wAng[j])); }
          col += vec3(0.07, 0.17, 0.42) * pow(1.0 - max(dot(vV, vNv), 0.0), 2.4);
          gl_FragColor = vec4(col, 1.0); }` });
    planet = new THREE.Mesh(new THREE.SphereGeometry(RAD, 128, 80), planetMat); globe.add(planet);
    // atmosphere halo
    scene.add(new THREE.Mesh(new THREE.SphereGeometry(RAD * 1.07, 64, 48), new THREE.ShaderMaterial({ side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `varying vec3 vNv; void main(){ vNv = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `varying vec3 vNv; void main(){ float i = pow(clamp(-vNv.z / 0.36, 0.0, 1.0), 2.2); gl_FragColor = vec4(vec3(0.14, 0.34, 0.95) * i * 0.85, 1.0); }` })));
    // towers: one per company
    const geo = new THREE.CylinderGeometry(1, 1, 1, 6, 1); geo.translate(0, 0.5, 0);
    const tm = new THREE.MeshBasicMaterial();
    tm.onBeforeCompile = sh => {
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying float vH;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvH = position.y;');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying float vH;').replace('#include <dithering_fragment>', '#include <dithering_fragment>\ngl_FragColor.rgb *= 0.16 + 1.0 * vH * vH;');
    };
    towers = new THREE.InstancedMesh(geo, tm, ids.length); towers.frustumCulled = false; globe.add(towers);
    lossMesh = new THREE.InstancedMesh(geo, new THREE.MeshBasicMaterial({ transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }), ids.length); lossMesh.frustumCulled = false; globe.add(lossMesh);
    const c0 = new THREE.Color(0, 0, 0); ids.forEach((id, i) => { setBox(towers, i, P[id], 0, H[id], WD[id]); setBox(lossMesh, i, P[id], 0, 0, 0); towers.setColorAt(i, c0); lossMesh.setColorAt(i, c0); });
    // a light at the top of every tower
    const gg = new THREE.BufferGeometry(); gg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(ids.length * 3), 3)); gg.setAttribute('color', new THREE.BufferAttribute(new Float32Array(ids.length * 3), 3)); gg.setAttribute('size', new THREE.BufferAttribute(new Float32Array(ids.length), 1));
    glow = new THREE.Points(gg, spriteMat()); glow.frustumCulled = false; globe.add(glow);
    // every supply link, with light moving the way the money moves (buyer to seller)
    const pos = [], au = [], ap = [], ac = []; let li = 0;
    for (const l of OV_LINKS) { const pts = arcs[l.id], c = baseCol[l.from], ph = (li++ * 0.6180339) % 1;
      for (let i = 0; i < pts.length - 1; i++) { pos.push(pts[i].x, pts[i].y, pts[i].z, pts[i + 1].x, pts[i + 1].y, pts[i + 1].z); au.push(i / (pts.length - 1), (i + 1) / (pts.length - 1)); ap.push(ph, ph); ac.push(...c, ...c); } }
    const lg = new THREE.BufferGeometry(); lg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); lg.setAttribute('aU', new THREE.Float32BufferAttribute(au, 1)); lg.setAttribute('aP', new THREE.Float32BufferAttribute(ap, 1)); lg.setAttribute('aC', new THREE.Float32BufferAttribute(ac, 3));
    lineMat = new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uT: { value: 0 }, uBase: { value: 0.3 }, uFlow: { value: 1.5 } },
      vertexShader: `attribute float aU; attribute float aP; attribute vec3 aC; varying float vU; varying float vP; varying vec3 vC; void main(){ vU = aU; vP = aP; vC = aC; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `varying float vU; varying float vP; varying vec3 vC; uniform float uT; uniform float uBase; uniform float uFlow; void main(){ float p = fract(vU + uT * 0.16 + vP); gl_FragColor = vec4(vC * (uBase + uFlow * smoothstep(0.1, 0.0, p)), 1.0); }` });
    globe.add(new THREE.LineSegments(lg, lineMat));
    hotGroup = new THREE.Group(); globe.add(hotGroup);
    const cg = new THREE.BufferGeometry(); cg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(300 * 3), 3)); cg.setAttribute('color', new THREE.BufferAttribute(new Float32Array(300 * 3), 3)); cg.setAttribute('size', new THREE.BufferAttribute(new Float32Array(300), 1));
    comets = new THREE.Points(cg, spriteMat()); comets.frustumCulled = false; globe.add(comets);
    beam = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 2.4, 1, 14, 1, true).translate(0, 0.5, 0), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide })); globe.add(beam);
    rings = new THREE.Group(); globe.add(rings);
    globe.quaternion.setFromUnitVectors(cont.find(c => c.name === 'Information Technology').c, FACE);
  }
  const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _p = new THREE.Vector3(), UP = new THREE.Vector3(0, 1, 0), _c = new THREE.Color();
  function setBox(mesh, i, p, y0, h, w) { _q.setFromUnitVectors(UP, p); _p.copy(p).multiplyScalar(RAD + y0); _m.compose(_p, _q, _s.set(w, Math.max(h, 0.0001), w)); mesh.setMatrixAt(i, _m); }

  // ---------- HUD + labels ----------
  function buildHud() {
    hud = document.createElement('div'); hud.className = 'hud';
    hud.innerHTML = `<div class="h-tl"><div class="h-k"></div><div class="h-t"></div><div class="h-n"><b></b><span></span></div><div class="h-s"></div></div>
      <div class="h-tr"><div class="h-k">Hardest hit</div><div class="h-rows"></div></div>
      <div class="h-bl"><div class="h-k">Run a scenario</div><div class="h-chips"></div></div>
      <div class="h-br"><button data-a="replay">Replay</button><button data-a="clear">Clear</button><button data-a="full">Full screen</button></div>`;
    box.appendChild(hud);
    hud.querySelector('.h-chips').innerHTML = PRESETS.map((p, i) => `<button data-i="${i}">${esc(p.t)}</button>`).join('');
    hud.querySelectorAll('.h-chips button').forEach(b => b.onclick = () => { const p = PRESETS[+b.dataset.i]; runFromText(p.t, p.sc); });
    hud.querySelector('[data-a=replay]').onclick = () => replay();
    hud.querySelector('[data-a=clear]').onclick = () => clearScenario();
    hud.querySelector('[data-a=full]').onclick = () => cinema();
  }
  function setHud() {
    const q = s => hud.querySelector(s); hud.classList.toggle('live', !!res); hud.classList.remove('done');
    if (!res) {
      const cap = ids.reduce((s, id) => s + (N[id].cap || 0), 0);
      q('.h-tl .h-k').textContent = 'The S&P 500 and its supply chain'; q('.h-t').textContent = 'One connected market';
      q('.h-n b').textContent = fB(cap); q('.h-n b').style.color = ''; q('.h-n span').textContent = 'of market value mapped';
      q('.h-s').innerHTML = `<b>${ids.length}</b> companies · <b>${OV_LINKS.length}</b> supply links · <b>${cont.length}</b> sectors<br>Each tower is a company. Its height is its market value.`;
      q('.h-rows').innerHTML = ''; return;
    }
    q('.h-tl .h-k').textContent = `Scenario · ${res.runs.toLocaleString()} simulated runs`; q('.h-t').textContent = describe(res.sc);
    q('.h-n span').textContent = res.sc.dir === 0 ? 'net change in market value' : res.sc.dir > 0 ? 'of market value gained' : 'of market value at risk';
    const top = res.rows.filter(r => r.mcar && P[r.id]).slice(0, 7), mx = top[0]?.mcar || 1;
    q('.h-tr .h-k').textContent = res.sc.dir > 0 ? 'Biggest gains' : res.sc.dir === 0 ? 'Biggest moves' : 'Hardest hit';
    q('.h-rows').innerHTML = top.map(r => `<div class="h-row" data-id="${esc(r.id)}"><b>${esc(tick(r.id))}</b><i><u style="width:${Math.max(4, r.mcar / mx * 100)}%;background:${colOf(r.sgn)}"></u></i><em style="color:${r.sgn > 0 ? '#6BE08F' : '#FF7A8C'}">${r.sgn > 0 ? '+' : '-'}${fB(r.mcar)}</em><small>${fP(r.p, 0)}</small></div>`).join('');
  }
  function setLabels() {
    labelBox.innerHTML = ''; labels = [];
    const add = (id, cls, pri, row) => { if (!P[id] || labels.some(x => x.id === id)) return; const e = document.createElement('span'); e.className = 'l3 ' + (cls || ''); e.textContent = tick(id); labelBox.appendChild(e); labels.push({ id, e, pri, row, w: 0 }); };
    if (res) {
      tl.org.forEach(id => add(id, 'o', 0));
      res.rows.filter(r => P[r.id] && r.mcar != null).slice(0, 24).forEach((r, k) => add(r.id, r.sgn > 0 ? 'up' : 'dn', 1 + k, k < 12 ? r : null));
      [...S.pf].forEach(id => { if (res.byId[id]) add(id, res.byId[id].sgn > 0 ? 'up' : 'dn', 40); });
    } else {
      [...S.pf].forEach((id, k) => add(id, 'h', k));
      [...ids].sort((a, b) => (N[b].cap || 0) - (N[a].cap || 0)).slice(0, 22).forEach((id, k) => add(id, '', 10 + k));
      HUBS.forEach(id => add(id, '', 5));
    }
    for (const c of cont) { const e = document.createElement('span'); e.className = 'l3 sec'; e.textContent = c.name; labelBox.appendChild(e); labels.push({ id: null, e, pri: 200, at: c.at, w: 0 }); }
    labels.sort((a, b) => a.pri - b.pri);
  }

  // ---------- scenario timeline ----------
  function setScenario(r) {
    res = r; tl = null; waves.length = 0;
    while (hotGroup.children.length) { const m = hotGroup.children.pop(); m.geometry.dispose(); m.material.dispose(); }
    if (res) {
      const org = res.sc.origins.filter(id => P[id]), direct = id => res.byId[id] && res.byId[id].hop === 0;
      const hopOf = id => org.includes(id) && !(res.byId[id]?.hop > 0) ? 0 : res.byId[id]?.hop ?? 99, rev = {};
      for (const id of org) if (direct(id)) rev[id] = T0;
      const hot = [], per = {};
      for (const l of OV_LINKS) {
        if (!res.pass[l.id]) continue; const a = hopOf(l.from), b = hopOf(l.to); if (a > 90 || b > 90 || a === b) continue;
        const to = a < b ? l.to : l.from, k = Math.max(a, b), n = per[k] = (per[k] || 0) + 1, start = T0 + 0.25 + (k - 1) * HOP + Math.min(0.5, (n - 1) * 0.045);
        const pts = a < b ? arcs[l.id] : arcs[l.id].slice().reverse(), w = Math.sqrt(res.pass[l.id] / res.runs), seg = pts.length * 2;
        const mesh = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), seg, 0.16 + 0.58 * w, 5, false), new THREE.MeshBasicMaterial({ color: new THREE.Color(linkCol(l.id)), transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false }));
        mesh.geometry.setDrawRange(0, 0); mesh.frustumCulled = false; hotGroup.add(mesh);
        hot.push({ mesh, pts, start, w, to, seg, col: rgb(linkCol(l.id)) });
        rev[to] = Math.min(rev[to] ?? 1e9, start + FLY);
      }
      const rows = res.rows.filter(x => P[x.id]); for (const x of rows) if (rev[x.id] == null) rev[x.id] = T0 + 0.25 + Math.max(0, x.hop - 1) * HOP + FLY;
      const K = Math.max(1, ...rows.map(x => x.hop)), end = T0 + 0.25 + (K - 1) * HOP + FLY + 0.9;
      // where to look: first the start, then the centre of everything that was hit
      const o = v3(); org.forEach(id => o.add(P[id])); o.normalize();
      const frames = []; for (let k = 1; k <= K; k++) frames.push({ at: T0 + 0.05 + (k - 1) * HOP, set: rows.filter(x => x.hop <= k && x.p >= 0.03).slice(0, 30) });
      frames.push({ at: end - 0.3, set: rows.filter(x => x.p >= 0.03).slice(0, 36) });
      tl = { t0: performance.now(), org, rev, hot, rows, K, end, o, frames, fired: new Set(), blast: false, done: false };
      lookAt(org.map(id => [id, 1]), 290); shown = 0; shownMine = 0;
    } else { distTo = 430; shown = 0; lookT = 0; }
    setHud(); setLabels();
  }
  // turn the planet so a set of companies faces the viewer, and pull back far enough to see all of them
  function lookAt(list, minDist) {
    const c = v3(); list.forEach(([id, w]) => c.addScaledVector(P[id], w)); if (c.length() < 1e-6) return; c.normalize();
    const spread = Math.max(0.2, ...list.map(([id]) => c.angleTo(P[id])));
    targetQ = new THREE.Quaternion().setFromUnitVectors(c, spread > 1.15 ? FRONT : FACE); distTo = Math.max(minDist, Math.min(500, 190 + 400 * spread));
    lookT = spread < 0.7 ? Math.min(1, (0.7 - spread) / 0.4) : 0;   // a tight cluster gets centred and seen from closer
  }
  function replay() { if (res) setScenario(res); }
  function wave(dir, col, amp, speed, reach) { waves.push({ dir: dir.clone(), col, amp, speed, reach, born: performance.now() }); if (waves.length > 6) waves.shift(); }
  function ringAt(p, col, big) {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.86, 1, 40), new THREE.MeshBasicMaterial({ color: new THREE.Color(...col), transparent: true, opacity: 1, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    m.position.copy(p).multiplyScalar(RAD * 1.004); m.quaternion.setFromUnitVectors(v3(0, 0, 1), p); m.userData = { born: performance.now(), big }; rings.add(m);
  }

  // ---------- frame ----------
  function frame(now) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min(0.05, (now - lastT) / 1000 || 0.016); lastT = now;
    const t = tl ? (now - tl.t0) / 1000 : 0, tw = now / 1000;
    const col = towers.instanceColor.array, lc = lossMesh.instanceColor.array, gp = glow.geometry.attributes.position.array, gc = glow.geometry.attributes.color.array, gs = glow.geometry.attributes.size.array;
    const dim = tl ? ease(t / 1.1) : 0; let risk = 0, hit = 0, mine = 0, hopNow = 0;
    for (let i = 0; i < ids.length; i++) {
      const id = ids[i], b = baseCol[id]; let r = b[0], g = b[1], bl = b[2], k = OVDEG[id] ? 0.92 : 0.34, h = H[id], lh = 0, lf = 0, top = 0.75;
      if (!tl) { if (S.pf.has(id)) { k = 1.5; top = 1.5; } if (id === hoverId) k = 2; k *= 0.94 + 0.06 * Math.sin(tw * 1.3 + i * 1.7); }
      else {
        const row = res.byId[id], isO = tl.org.includes(id), at = tl.rev[id];
        r += (SLATE[0] + 0.1 * r - r) * dim; g += (SLATE[1] + 0.1 * g - g) * dim; bl += (SLATE[2] + 0.1 * bl - bl) * dim; k = k * (1 - dim) + 0.85 * dim; top = 0.75 * (1 - dim) + 0.1 * dim;
        if (isO && !(row && row.hop === 0)) { const ch = Math.min(1, t / T0), pulse = 0.5 + 0.5 * Math.sin(tw * 7); r = 1; g = 0.86 - 0.3 * ch; bl = 0.8 - 0.45 * ch; k = 1.0 + 0.5 * ch + 0.2 * pulse; top = 1.1 + 0.3 * pulse; }
        else if (row && at != null && t >= at) {
          const a = t - at, kk = ease(a / 0.5), fl = Math.max(0, 1 - a / 0.9), c = row.sgn > 0 ? [0.1, 0.92, 0.42] : [1, 0.16, 0.24], str = 0.45 + 0.65 * Math.sqrt(row.p);
          r = c[0] + fl * (1 - c[0]); g = c[1] + fl * (1 - c[1]); bl = c[2] + fl * (1 - c[2]); k = str + 0.75 * fl; top = 0.9 + 0.95 * Math.sqrt(row.p) + 1.1 * fl;
          const d = Math.min(0.9, row.drop); h = H[id] * (1 - (row.sgn < 0 ? d : -d) * kk);
          if (row.sgn < 0) { const life = Math.max(0, 1 - a / 2.6); lh = Math.max(H[id] * d, 1.1) * (0.4 + 0.6 * life); lf = life; }
          risk += row.sgn * (row.mcar || 0); hit++; if (S.pf.has(id)) mine += row.sgn * (row.mcar || 0); hopNow = Math.max(hopNow, row.hop);
          if (!tl.fired.has(id)) { tl.fired.add(id); const big = (row.mcar || 0) > 40; ringAt(P[id], row.sgn > 0 ? [0.3, 1, 0.55] : [1, 0.3, 0.38], big); if (big) { wave(P[id], row.sgn > 0 ? v3(0.1, 0.8, 0.35) : v3(1, 0.14, 0.22), 0.28, 0.5, 0.42); shake = Math.max(shake, 0.28); } }
        }
      }
      setBox(towers, i, P[id], 0, h, WD[id]); setBox(lossMesh, i, P[id], h + (lf ? (1 - lf) * 3 : 0), lh, WD[id] * 1.04);
      col[i * 3] = r * k; col[i * 3 + 1] = g * k; col[i * 3 + 2] = bl * k; lc[i * 3] = lf * 0.78; lc[i * 3 + 1] = lf * 0.19; lc[i * 3 + 2] = lf * 0.16;
      const tp = P[id]; gp[i * 3] = tp.x * (RAD + h + 0.4); gp[i * 3 + 1] = tp.y * (RAD + h + 0.4); gp[i * 3 + 2] = tp.z * (RAD + h + 0.4);
      gc[i * 3] = r * top; gc[i * 3 + 1] = g * top; gc[i * 3 + 2] = bl * top; gs[i] = (2.2 + WD[id] * 2.2) * (top > 1 ? 1 + 0.35 * (top - 1) : 1);
    }
    towers.instanceMatrix.needsUpdate = lossMesh.instanceMatrix.needsUpdate = towers.instanceColor.needsUpdate = lossMesh.instanceColor.needsUpdate = true;
    glow.geometry.attributes.position.needsUpdate = glow.geometry.attributes.color.needsUpdate = glow.geometry.attributes.size.needsUpdate = true;
    // links, comets, beam
    lineMat.uniforms.uT.value = tw; lineMat.uniforms.uBase.value = 0.3 * (1 - dim) + 0.035 * dim; lineMat.uniforms.uFlow.value = 1.5 * (1 - dim) + 0.12 * dim; planetMat.uniforms.uLit.value = 1 - 0.72 * dim;
    const cp = comets.geometry.attributes.position.array, cc = comets.geometry.attributes.color.array, cs = comets.geometry.attributes.size.array; let nc = 0;
    if (tl) {
      for (const hl of tl.hot) {
        const k = (t - hl.start) / FLY, kk = Math.max(0, Math.min(1, k)), e = kk * kk * (3 - 2 * kk);
        hl.mesh.geometry.setDrawRange(0, Math.floor(e * hl.seg) * 30);
        hl.mesh.material.opacity = k < 1 ? 0.82 : 0.3 + 0.25 * hl.w + 0.09 * Math.sin(tw * 3 + hl.start * 5);
        if (k > 0 && k < 1 && nc < 300) { const f = e * (hl.pts.length - 1), i = Math.min(hl.pts.length - 2, Math.floor(f)), p = _p.copy(hl.pts[i]).lerp(hl.pts[i + 1], f - i); cp[nc * 3] = p.x; cp[nc * 3 + 1] = p.y; cp[nc * 3 + 2] = p.z; cc[nc * 3] = 0.65 + hl.col[0]; cc[nc * 3 + 1] = 0.5 + hl.col[1]; cc[nc * 3 + 2] = 0.5 + hl.col[2]; cs[nc] = 6.5 + 8 * hl.w; nc++; }
      }
      const o = tl.o, bh = t < T0 ? 12 + 46 * ease(t / T0) : 58, bo = t < T0 ? 0.28 * ease(t / 0.5) : Math.max(0, 0.45 - (t - T0) / 1.6);
      beam.visible = bo > 0.01; beam.material.opacity = bo; _q.setFromUnitVectors(UP, o); beam.quaternion.copy(_q); beam.position.copy(o).multiplyScalar(RAD); beam.scale.set(1 + (t > T0 ? (t - T0) * 1.1 : 0), bh, 1 + (t > T0 ? (t - T0) * 1.1 : 0));
      const neg = res.sc.dir >= 0 && res.groups.every(g => g.dir > 0) ? v3(0.1, 0.85, 0.4) : v3(1, 0.13, 0.22);
      if (!tl.blast && t >= T0) { tl.blast = true; wave(o, neg, 0.5, 0.95, 3.3); ringAt(o, [1, 0.7, 0.7], true); shake = 0.55; }
      while (tl.frames.length && t >= tl.frames[0].at) { const f = tl.frames.shift(); if (!drag) lookAt([...tl.org.map(id => [id, 2]), ...f.set.map(x => [x.id, 0.3 + Math.sqrt(x.p)])], 270); }
      if (!tl.done && t >= tl.end) { tl.done = true; hud.classList.add('done'); }
    } else beam.visible = false;
    comets.geometry.setDrawRange(0, nc); comets.geometry.attributes.position.needsUpdate = comets.geometry.attributes.color.needsUpdate = comets.geometry.attributes.size.needsUpdate = true;
    // surface waves and impact rings
    const U = planetMat.uniforms;
    for (let j = 0; j < 6; j++) { const w = waves[j]; if (!w) { U.wAmp.value[j] = 0; continue; } const a = (now - w.born) / 1000 * w.speed; U.wDir.value[j].copy(w.dir); U.wAng.value[j] = a; U.wCol.value[j].copy(w.col); U.wAmp.value[j] = a > w.reach ? 0 : w.amp * (1 - a / w.reach); }
    for (let i = rings.children.length - 1; i >= 0; i--) { const m = rings.children[i], a = (now - m.userData.born) / 1000, life = m.userData.big ? 1.5 : 1; if (a > life) { rings.remove(m); m.geometry.dispose(); m.material.dispose(); continue; } const s = 2 + (m.userData.big ? 21 : 11) * ease(a / life); m.scale.set(s, s, s); m.material.opacity = 0.7 * (1 - a / life); }
    // motion
    if (!drag) {
      if (targetQ) { globe.quaternion.slerp(targetQ, 1 - Math.pow(0.03, dt)); if (globe.quaternion.angleTo(targetQ) < 0.004) targetQ = null; }
      else { _q.setFromAxisAngle(UP, (tl ? 0.035 : 0.075) * dt); globe.quaternion.premultiply(_q); }
    }
    dist += (distTo - dist) * (1 - Math.pow(0.08, dt)); shake *= Math.pow(0.012, dt);
    lookNow += (lookT - lookNow) * (1 - Math.pow(0.06, dt)); const fx = FACE.x * RAD * 0.8 * lookNow, fy = FACE.y * RAD * 0.8 * lookNow;
    camera.position.set(fx * 0.4 + Math.sin(tw * 61) * shake, fy * 0.5 + Math.cos(tw * 47) * shake, dist); camera.lookAt(fx, fy, 0);
    if (composer) composer.render(); else renderer.render(scene, camera);
    // HUD numbers
    if (tl) {
      shown += (risk - shown) * (1 - Math.pow(0.0015, dt)); shownMine += (mine - shownMine) * (1 - Math.pow(0.0015, dt)); mine = Math.abs(mine - shownMine) < 0.05 ? mine : shownMine; const q = s => hud.querySelector(s), mixed = res.sc.dir === 0, v = Math.abs(shown) < 0.005 ? 0 : shown;
      q('.h-n b').textContent = (mixed ? (v >= 0 ? '+' : '-') : res.sc.dir > 0 ? '+' : '-') + fB(Math.abs(v)); q('.h-n b').style.color = (mixed ? v >= 0 : res.sc.dir > 0) ? '#6BE08F' : '#FF5C72';
      const stage = t < T0 ? 'shock building' : hopNow ? `hop <b>${hopNow}</b> of ${tl.K}` : 'shock released';
      q('.h-s').innerHTML = `<b>${hit}</b> compan${hit === 1 ? 'y' : 'ies'} ${res.sc.dir > 0 ? 'lifted' : res.sc.dir === 0 ? 'affected' : 'hit'} · ${tl.done ? 'settled after ' + tl.K + ' hop' + (tl.K === 1 ? '' : 's') : stage}${S.pf.size ? `<br>Your ${S.pf.size} holdings: ${Math.abs(mine) < 0.005 ? '<b>not affected' + (tl.done ? '' : ' so far') + '</b>' : `<b style="color:${mine > 0 ? '#6BE08F' : '#FF7A8C'}">${money(mine)}</b>`}` : ''}`;
      hud.querySelectorAll('.h-row').forEach(e => e.classList.toggle('on', t >= (tl.rev[e.dataset.id] ?? 1e9)));
    }
    drawLabels(t);
  }
  const _w = new THREE.Vector3(), _n = new THREE.Vector3(), _cam = new THREE.Vector3();
  function drawLabels(t) {
    const w = box.clientWidth, h = box.clientHeight, placed = [];
    for (const L of labels) {
      let show = true, txt = null;
      if (L.id) {
        const row = res && res.byId[L.id], hh = tl && row && t >= (tl.rev[L.id] ?? 1e9) ? H[L.id] * (1 - (row.sgn < 0 ? Math.min(0.9, row.drop) : 0)) : H[L.id];
        _w.copy(P[L.id]).multiplyScalar(RAD + hh + 1.2);
        if (tl && !tl.org.includes(L.id)) { show = t >= (tl.rev[L.id] ?? 1e9); if (show && L.row && L.row.mcar != null) txt = `${tick(L.id)} ${L.row.sgn > 0 ? '+' : '-'}${fB(L.row.mcar)}`; }
        if (txt == null) txt = tick(L.id); if (L.txt !== txt) { L.e.textContent = L.txt = txt; L.w = 0; }
      } else _w.copy(L.at);
      _w.applyMatrix4(globe.matrixWorld); _n.copy(_w).normalize(); _cam.copy(camera.position).sub(_w).normalize(); const facing = _n.dot(_cam);
      if (!show || facing < 0.2) { L.e.style.opacity = 0; continue; }
      _w.project(camera); const x = (_w.x + 1) / 2 * w, y = (1 - _w.y) / 2 * h; if (!L.w) L.w = L.e.offsetWidth || 40;
      const bx = [x - L.w / 2 - 2, y - 24, x + L.w / 2 + 2, y - 6];
      if (placed.some(b => bx[0] < b[2] && bx[2] > b[0] && bx[1] < b[3] && bx[3] > b[1]) || x < 4 || x > w - 4 || y < 14 || y > h) { L.e.style.opacity = 0; continue; }
      placed.push(bx); L.e.style.opacity = Math.min(1, (facing - 0.2) * 5).toFixed(2); L.e.style.transform = `translate(-50%,-100%) translate(${x.toFixed(1)}px,${(y - 6).toFixed(1)}px)`;
    }
  }
  function resize() {
    const w = box.clientWidth, h = box.clientHeight; if (!w || !h) return;
    const pr = Math.min(1.75, window.devicePixelRatio || 1); renderer.setPixelRatio(pr); renderer.setSize(w, h, false); if (composer) composer.setSize(w, h);
    camera.aspect = w / h; camera.fov = w / h < 1.15 ? 46 : 36; camera.updateProjectionMatrix();
    const s = h / 640 * pr; glow.material.uniforms.scale.value = comets.material.uniforms.scale.value = s;
  }
  function cinema(on) {
    const want = on ?? !document.body.classList.contains('cinema'); document.body.classList.toggle('cinema', want);
    try { if (want && !document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => {}); else if (!want && document.fullscreenElement) document.exitFullscreen?.(); } catch (e) { /* stays in-window */ }
    hud.querySelector('[data-a=full]').textContent = want ? 'Exit full screen' : 'Full screen'; setTimeout(resize, 60);
  }
  const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
  function pick(e) { const r = renderer.domElement.getBoundingClientRect(); mouse.set((e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(mouse, camera); const hit = ray.intersectObjects([planet, towers])[0]; return hit && hit.object === towers ? ids[hit.instanceId] : null; }
  function show(container) {
    if (!window.THREE) { container.innerHTML = '<p class="g3err">The 3D library did not load (vendor/three.min.js).</p>'; return false; }
    if (!renderer) {
      box = container; renderer = new THREE.WebGLRenderer({ antialias: true }); box.appendChild(renderer.domElement);
      labelBox = document.createElement('div'); labelBox.className = 'l3box'; box.appendChild(labelBox);
      prep(); build(); buildHud();
      if (THREE.EffectComposer && THREE.UnrealBloomPass) { composer = new THREE.EffectComposer(renderer); composer.addPass(new THREE.RenderPass(scene, camera)); composer.addPass(new THREE.UnrealBloomPass(new THREE.Vector2(512, 512), 0.58, 0.5, 0.22)); }
      ro = new ResizeObserver(resize); ro.observe(box);
      const el = renderer.domElement;
      el.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY }; moved = false; el.setPointerCapture(e.pointerId); });
      el.addEventListener('pointermove', e => {
        if (drag) { const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (!moved && Math.hypot(dx, dy) < 4) return; moved = true; targetQ = null; hideTip();
          _q.setFromAxisAngle(UP, dx * 0.0055); globe.quaternion.premultiply(_q); _q.setFromAxisAngle(v3(1, 0, 0), dy * 0.0055); globe.quaternion.premultiply(_q); drag.x = e.clientX; drag.y = e.clientY; return; }
        const id = pick(e); hoverId = id; el.style.cursor = id ? 'pointer' : 'grab'; if (id) showTip(e, ovTip(id)); else hideTip();
      });
      el.addEventListener('pointerup', e => { const was = moved; drag = null; if (!was) { const id = pick(e); if (id && !document.body.classList.contains('cinema')) select('node', id); } });
      el.addEventListener('pointerleave', () => { hoverId = null; hideTip(); });
      el.addEventListener('wheel', e => { e.preventDefault(); distTo = Math.max(210, Math.min(700, distTo * Math.exp(e.deltaY * 0.0012))); }, { passive: false });
      document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && document.body.classList.contains('cinema')) cinema(false); });
      document.addEventListener('keydown', e => { if (!raf || /INPUT|SELECT|TEXTAREA/.test(document.activeElement?.tagName || '')) return; if (e.key === ' ') { e.preventDefault(); replay(); } else if (e.key === 'f' || e.key === 'F') cinema(); else if (e.key === 'Escape' && document.body.classList.contains('cinema')) cinema(false); });
    }
    resize(); if (!raf) { lastT = performance.now(); raf = requestAnimationFrame(frame); } return true;
  }
  function hide() { if (raf) cancelAnimationFrame(raf); raf = 0; if (document.body.classList.contains('cinema')) cinema(false); }
  return { show, hide, setScenario, replay, cinema, refresh: () => { if (renderer) setLabels(); }, get active() { return !!raf; },
    state: () => ({ nodes: ids.length, links: OV_LINKS.length, hot: tl ? tl.hot.length : 0, labels: labels.length, bloom: !!composer, t: tl ? +((performance.now() - tl.t0) / 1000).toFixed(1) : 0, end: tl ? +tl.end.toFixed(1) : 0, continents: cont.map(c => c.name + ':' + c.n) }) };
})();
