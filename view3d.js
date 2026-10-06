'use strict';
// 3D presentation view: the same network wrapped on a globe, with the shock animated on it.
// Uses the fixed 2D layout (sector neighbourhoods) for longitude and latitude. Needs vendor/three.min.js.
const G3 = (() => {
  const RAD = 100, HOP_S = 1.35, HOLD_S = 4.5;
  let box, renderer, scene, camera, globe, points, lines, hot, pulses, labelBox, raf = 0, ro = null;
  let ids = [], idx = {}, P3 = {}, base = {}, links = [], labels = [], res = null, t0 = 0, drag = null, spin = 0.0016, dist = 330, wantY = null;
  const hex = h => { const c = new THREE.Color(h); return [c.r, c.g, c.b]; };
  const sizeOf = id => N[id].cap ? Math.max(2.2, Math.min(9, 1.8 + 0.085 * Math.sqrt(N[id].cap))) : 2.2;
  function place(id) {
    const [x, y] = LAY.pos[id], lon = (x / LAY.w - 0.5) * Math.PI * 1.9, lat = (0.5 - y / LAY.h) * Math.PI * 0.82;
    return new THREE.Vector3(RAD * Math.cos(lat) * Math.sin(lon), RAD * Math.sin(lat), RAD * Math.cos(lat) * Math.cos(lon));
  }
  function arc(a, b, n = 14) {
    const mid = a.clone().add(b); const d = a.distanceTo(b);
    if (mid.length() < 1) mid.set(0, RAD, 0);
    mid.normalize().multiplyScalar(RAD * (1 + 0.42 * d / (2 * RAD)));
    const curve = new THREE.QuadraticBezierCurve3(a, mid, b); return curve.getPoints(n);
  }
  const pointMat = () => new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { scale: { value: 1 } },
    vertexShader: `attribute float size; attribute vec3 color; attribute float bright; varying vec3 vC; varying float vA; uniform float scale;
      void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); vec3 n = normalize(normalMatrix * normalize(position));
        vA = bright * (0.16 + 0.84 * smoothstep(-0.25, 0.45, n.z)); vC = color; gl_PointSize = size * scale * (330.0 / -mv.z); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `varying vec3 vC; varying float vA; void main(){ float d = length(gl_PointCoord - 0.5); if (d > 0.5) discard;
      float core = smoothstep(0.26, 0.14, d), halo = smoothstep(0.5, 0.0, d) * 0.55; gl_FragColor = vec4(vC * (core + halo) * vA, 1.0); }`
  });
  function build() {
    scene = new THREE.Scene(); camera = new THREE.PerspectiveCamera(38, 1, 1, 2000); globe = new THREE.Group(); scene.add(globe); globe.rotation.x = 0.22;
    ids = OV_IDS.slice(); ids.forEach((id, i) => { idx[id] = i; P3[id] = place(id); base[id] = hex(famOf(id).color); });
    // faint shell so the far side reads as "behind"
    globe.add(new THREE.Mesh(new THREE.SphereGeometry(RAD * 0.985, 48, 32), new THREE.MeshBasicMaterial({ color: 0x0b0d14, transparent: true, opacity: 0.86 })));
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(ids.flatMap(id => P3[id].toArray())), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(ids.length * 3), 3));
    g.setAttribute('size', new THREE.BufferAttribute(new Float32Array(ids.length), 1));
    g.setAttribute('bright', new THREE.BufferAttribute(new Float32Array(ids.length), 1));
    points = new THREE.Points(g, pointMat()); globe.add(points);
    links = OV_LINKS.map(l => ({ l, pts: arc(P3[l.from], P3[l.to]) }));
    const seg = [], col = [];
    for (const { l, pts } of links) { const c = base[l.from]; for (let i = 0; i < pts.length - 1; i++) { seg.push(...pts[i].toArray(), ...pts[i + 1].toArray()); col.push(...c, ...c); } }
    const lg = new THREE.BufferGeometry(); lg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(seg), 3)); lg.setAttribute('color', new THREE.BufferAttribute(new Float32Array(col), 3));
    lines = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.34, blending: THREE.AdditiveBlending, depthWrite: false })); globe.add(lines);
    hot = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false })); globe.add(hot);
    const pg = new THREE.BufferGeometry(); const MAXP = 400;
    pg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAXP * 3), 3)); pg.setAttribute('color', new THREE.BufferAttribute(new Float32Array(MAXP * 3), 3));
    pg.setAttribute('size', new THREE.BufferAttribute(new Float32Array(MAXP), 1)); pg.setAttribute('bright', new THREE.BufferAttribute(new Float32Array(MAXP), 1));
    pulses = new THREE.Points(pg, pointMat()); globe.add(pulses);
  }
  function setLabels() {
    labelBox.innerHTML = ''; labels = [];
    const add = (id, cls) => { if (!P3[id] || labels.some(x => x.id === id)) return; const e = document.createElement('span'); e.className = 'l3 ' + (cls || ''); e.textContent = tick(id); labelBox.appendChild(e); labels.push({ id, e, p: P3[id] }); };
    if (res) { res.sc.origins.forEach(id => add(id, 'o')); res.rows.slice(0, 16).forEach(r => add(r.id, r.sgn > 0 ? 'up' : 'dn')); }
    else { [...S.pf].forEach(id => add(id, 'h')); [...OV_IDS].sort((a, b) => (N[b].cap || 0) - (N[a].cap || 0)).slice(0, 18).forEach(id => add(id)); HUBS.forEach(id => add(id)); }
    for (const s of LAY.sectors) { const e = document.createElement('span'); e.className = 'l3 sec'; e.textContent = s.name; labelBox.appendChild(e); const lon = (s.x / LAY.w - 0.5) * Math.PI * 1.9, lat = (0.5 - s.y / LAY.h) * Math.PI * 0.82, r = RAD * 1.07; labels.push({ id: null, e, p: new THREE.Vector3(r * Math.cos(lat) * Math.sin(lon), r * Math.sin(lat), r * Math.cos(lat) * Math.cos(lon)) }); }
  }
  // scenario: who lights up when, and which links carry it
  let sched = null;
  function setScenario(r) {
    res = r; sched = null; t0 = performance.now();
    if (res) {
      const org = res.sc.origins.filter(id => P3[id]), hopOf = id => org.includes(id) && !(res.byId[id]?.hop > 0) ? 0 : res.byId[id]?.hop ?? 99;
      const hl = links.filter(({ l }) => res.pass[l.id] && hopOf(l.from) < 99 && hopOf(l.to) < 99 && hopOf(l.from) !== hopOf(l.to)).map(({ l, pts }) => {
        const fwd = hopOf(l.from) < hopOf(l.to); return { pts: fwd ? pts : pts.slice().reverse(), at: (Math.max(hopOf(l.from), hopOf(l.to)) - 1) * HOP_S, c: hex(linkCol(l.id)), w: Math.sqrt(res.pass[l.id] / res.runs) };
      });
      const seg = []; for (const h of hl) for (let i = 0; i < h.pts.length - 1; i++) seg.push(...h.pts[i].toArray(), ...h.pts[i + 1].toArray());
      hot.geometry.dispose(); hot.geometry = new THREE.BufferGeometry();
      hot.geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(seg), 3)); hot.geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(seg.length), 3));
      const maxHop = Math.max(1, ...res.rows.filter(x => P3[x.id]).map(x => x.hop));
      sched = { org, hl, hopOf, cycle: (maxHop + 0.4) * HOP_S + HOLD_S };
      // turn the globe so the starting company faces the viewer
      if (org[0]) wantY = -Math.atan2(P3[org[0]].x, P3[org[0]].z);
    } else { hot.geometry.dispose(); hot.geometry = new THREE.BufferGeometry(); wantY = null; }
    hot.visible = !!res; lines.material.opacity = res ? 0.07 : 0.34;
    setLabels();
  }
  function frame(now) {
    raf = requestAnimationFrame(frame);
    const t = res && sched ? ((now - t0) / 1000) % sched.cycle : 0, tw = now / 1000;
    const col = points.geometry.attributes.color.array, size = points.geometry.attributes.size.array, br = points.geometry.attributes.bright.array;
    for (let i = 0; i < ids.length; i++) {
      const id = ids[i]; let c = base[id], s = sizeOf(id), b = OVDEG[id] ? 0.95 : 0.3;
      if (S.pf.has(id) && !res) { b = 1.25; s *= 1.35; }
      if (!res) b *= 0.9 + 0.1 * Math.sin(tw * 1.6 + i);
      if (res && sched) {
        const row = res.byId[id], isO = sched.org.includes(id);
        if (isO && !(row?.hop > 0)) { c = row ? hex(colOf(row.sgn)) : [1, 1, 1]; s = sizeOf(id) * 1.7 + 1.5 * Math.sin(tw * 5) + 2; b = 1.5; }
        else if (row && P3[id]) {
          const at = (row.hop - 0.15) * HOP_S, k = t < at ? 0 : Math.min(1, (t - at) / 0.35), flash = t >= at ? Math.max(0, 1 - (t - at) / 0.8) : 0;
          c = k ? hex(colOf(row.sgn)) : [0.32, 0.34, 0.4]; s = sizeOf(id) * (k ? 1 + 1.3 * Math.sqrt(row.p) + 1.8 * flash : 0.9); b = k ? 0.55 + 0.75 * Math.sqrt(row.p) + flash : 0.2;
        } else { c = [0.32, 0.34, 0.4]; b = 0.17; }
      }
      col[i * 3] = c[0]; col[i * 3 + 1] = c[1]; col[i * 3 + 2] = c[2]; size[i] = s * 2.9; br[i] = b;
    }
    points.geometry.attributes.color.needsUpdate = points.geometry.attributes.size.needsUpdate = points.geometry.attributes.bright.needsUpdate = true;
    // pulses + lit links
    const pp = pulses.geometry.attributes.position.array, pc = pulses.geometry.attributes.color.array, ps = pulses.geometry.attributes.size.array, pb = pulses.geometry.attributes.bright.array; let n = 0;
    if (res && sched) {
      const hc = hot.geometry.attributes.color.array; let o = 0;
      for (const h of sched.hl) {
        const k = (t - h.at) / (HOP_S * 0.85), lit = Math.max(0, Math.min(1, k)), segs = h.pts.length - 1;
        for (let i = 0; i < segs; i++) { const on = lit * segs > i ? 0.25 + 0.75 * h.w : 0; for (let v = 0; v < 2; v++) { hc[o++] = h.c[0] * on; hc[o++] = h.c[1] * on; hc[o++] = h.c[2] * on; } }
        if (k > 0 && k < 1 && n < 400) { const f = k * segs, i = Math.min(segs - 1, Math.floor(f)), p = h.pts[i].clone().lerp(h.pts[i + 1], f - i); pp[n * 3] = p.x; pp[n * 3 + 1] = p.y; pp[n * 3 + 2] = p.z; pc[n * 3] = 1; pc[n * 3 + 1] = 0.95; pc[n * 3 + 2] = 0.9; ps[n] = 7 + 7 * h.w; pb[n] = 1.6; n++; }
      }
      hot.geometry.attributes.color.needsUpdate = true;
    }
    pulses.geometry.setDrawRange(0, n); pulses.geometry.attributes.position.needsUpdate = pulses.geometry.attributes.color.needsUpdate = pulses.geometry.attributes.size.needsUpdate = pulses.geometry.attributes.bright.needsUpdate = true;
    // motion
    if (!drag) {
      if (wantY != null) { let d = wantY - globe.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d)); globe.rotation.y += d * 0.04; if (Math.abs(d) < 0.01) wantY = null; }
      else globe.rotation.y += res ? spin * 0.3 : spin;
    }
    camera.position.set(0, 0, dist); camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
    // labels (plain HTML on top, only for the side facing the viewer)
    const w = box.clientWidth, h = box.clientHeight, v = new THREE.Vector3(), nrm = new THREE.Vector3();
    for (const L of labels) {
      v.copy(L.p).applyMatrix4(globe.matrixWorld); nrm.copy(v).normalize(); const facing = nrm.z;
      let show = facing > 0.28;
      if (show && res && sched && L.id && !sched.org.includes(L.id)) { const row = res.byId[L.id]; show = !!row && t >= (row.hop - 0.15) * HOP_S; }
      if (!show) { L.e.style.opacity = 0; continue; }
      v.project(camera); L.e.style.opacity = Math.min(1, (facing - 0.28) * 4); L.e.style.transform = `translate(-50%,-140%) translate(${((v.x + 1) / 2 * w).toFixed(1)}px,${((1 - v.y) / 2 * h).toFixed(1)}px)`;
    }
  }
  function resize() { const w = box.clientWidth, h = box.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); points.material.uniforms.scale.value = pulses.material.uniforms.scale.value = h / 620 * Math.min(2, window.devicePixelRatio || 1); }
  function show(container) {
    if (!window.THREE) { container.innerHTML = '<p class="g3err">The 3D library did not load (vendor/three.min.js).</p>'; return false; }
    if (!renderer) {
      box = container; renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1)); box.appendChild(renderer.domElement);
      labelBox = document.createElement('div'); labelBox.className = 'l3box'; box.appendChild(labelBox);
      build(); ro = new ResizeObserver(resize); ro.observe(box);
      const el = renderer.domElement;
      el.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, ry: globe.rotation.y, rx: globe.rotation.x }; wantY = null; el.setPointerCapture(e.pointerId); });
      el.addEventListener('pointermove', e => { if (!drag) return; globe.rotation.y = drag.ry + (e.clientX - drag.x) * 0.006; globe.rotation.x = Math.max(-1.1, Math.min(1.1, drag.rx + (e.clientY - drag.y) * 0.006)); });
      el.addEventListener('pointerup', () => { drag = null; });
      el.addEventListener('wheel', e => { e.preventDefault(); dist = Math.max(170, Math.min(520, dist * Math.exp(e.deltaY * 0.0012))); }, { passive: false });
    }
    resize(); if (!raf) raf = requestAnimationFrame(frame); return true;
  }
  function hide() { if (raf) cancelAnimationFrame(raf); raf = 0; }
  return { show, hide, setScenario, refresh: () => { if (renderer) setLabels(); }, get active() { return !!raf; }, state: () => ({ nodes: ids.length, links: links.length, hot: sched ? sched.hl.length : 0, labels: labels.length }) };
})();
