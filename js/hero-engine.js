/* Velmach Aerospace: home hero visual. Dependency-free WebGL renderer for a shaded open-rotor engine
   (spinner, front rotor, aft blade row, glass core cowl with turning stages, exhaust cone).
   VMHeroEngine.mount(canvas, { reduced, lite }) -> { canvas, lite, setPointer(x, y), destroy() } */
(function () {
  if (window.VMHeroEngine) return;
  var TAU = Math.PI * 2, D2R = Math.PI / 180, CAM = 7;

  function norm(v) { var l = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0] / l, v[1] / l, v[2] / l]; }
  var L1 = norm([-0.45, 0.7, 0.55]), L2 = norm([0.8, 0.1, -0.5]), H = norm([L1[0], L1[1], L1[2] + 1]);

  // colour; ambient, diffuse, specular, shininess; studio-band reflection, cool rim, alpha, fresnel alpha; glass = drawn in two passes
  function mat(r, g, b, o) {
    return { col: [r, g, b], m: [o.amb != null ? o.amb : 0.2, o.dif != null ? o.dif : 0.75, o.spec || 0.5, o.shin || 40],
      m2: [o.env || 0, o.rim != null ? o.rim : 0.5, o.a != null ? o.a : 1, o.fres || 0], back: o.back || 1, glass: !!o.glass };
  }
  var M = {
    blade: mat(0.3, 0.31, 0.34, { amb: 0.32, spec: 0.55, shin: 24, env: 0.24, rim: 0.35 }),
    edge: mat(0.78, 0.79, 0.82, { spec: 0.6, shin: 30, env: 0.2 }),
    aft: mat(0.38, 0.39, 0.43, { amb: 0.3, a: 0.6, fres: 0.3, spec: 0.5, shin: 30, env: 0.2 }),
    nose: mat(0.05, 0.045, 0.055, { amb: 0.3, spec: 0.9, shin: 60, env: 0.3, rim: 0.7 }),
    lip: mat(0.9, 0.9, 0.92, { spec: 0.5, env: 0.15 }),
    hub: mat(0.4, 0.41, 0.45, { spec: 0.8, shin: 50, env: 0.35 }),
    shell: mat(0.82, 0.84, 0.88, { a: 0.19, fres: 0.55, spec: 1, shin: 50, env: 0.7, rim: 1, back: 0.55, glass: true }),
    disc: mat(0.66, 0.67, 0.71, { spec: 0.7, shin: 30, env: 0.3 }),
    disc2: mat(0.4, 0.41, 0.45, { spec: 0.5, shin: 24, env: 0.15 }),
    dark: mat(0.17, 0.18, 0.21, { spec: 0.35, shin: 20 }),
    cyan: mat(0, 0.55, 0.8, { spec: 0.5, amb: 0.4 }),
    red: mat(0.6, 0.14, 0.14, { spec: 0.4, amb: 0.35 }),
    cone: mat(0.64, 0.66, 0.7, { spec: 0.95, shin: 60, env: 0.5 })
  };

  // Geometry as triangle lists grouped by (spin group, material): [x, y, z, nx, ny, nz] per vertex.
  function build(lite) {
    var seg = lite ? 40 : 72, groups = [];
    function grp(spin, mt) {
      for (var i = 0; i < groups.length; i++) if (groups[i].spin === spin && groups[i].mat === mt) return groups[i];
      var g = { spin: spin, mat: mt, d: [] }; groups.push(g); return g;
    }
    function vert(g, p, n) { g.d.push(p[0], p[1], p[2], n[0], n[1], n[2]); }
    function quad(g, P, N, a, b, c, d) { [a, b, c, a, c, d].forEach(function (i) { vert(g, P[i], N[i]); }); }
    // Surface of revolution around the engine axis (x); normals from the profile. alt: material for every other segment.
    function lathe(spin, prof, mt, alt, n) {
      n = n || seg;
      var P = [], N = [], cols = n + 1, i, j;
      for (i = 0; i < prof.length; i++) {
        var p0 = prof[Math.max(0, i - 1)], p1 = prof[Math.min(prof.length - 1, i + 1)], tx = p1[0] - p0[0], tr = p1[1] - p0[1], tl = Math.hypot(tx, tr) || 1,
          nx = -tr / tl, nr = tx / tl;
        for (j = 0; j <= n; j++) {
          var a = j / n * TAU, ca = Math.cos(a), sa = Math.sin(a);
          P.push([prof[i][0], prof[i][1] * ca, prof[i][1] * sa]); N.push([nx, nr * ca, nr * sa]);
        }
      }
      var g = grp(spin, mt), g2 = alt ? grp(spin, alt) : g;
      for (i = 0; i < prof.length - 1; i++) for (j = 0; j < n; j++) {
        var q = i * cols + j;
        quad(j % 2 ? g2 : g, P, N, q, q + cols, q + cols + 1, q + 1);
      }
    }
    // A row of twisted, swept, cambered blades. vs: chord stations; mats: material per chord band.
    function blades(spin, o) {
      var nu = lite ? 8 : 14, vs = o.vs, nv = vs.length;
      for (var k = 0; k < o.n; k++) {
        var phi = k / o.n * TAU, cp = Math.cos(phi), sp = Math.sin(phi), P = [], N = [], iu, iv;
        for (iu = 0; iu <= nu; iu++) {
          var u = iu / nu, r = o.r0 + (o.r1 - o.r0) * u, c = o.c0 * (0.8 + 0.5 * u - 0.9 * u * u * u * u),
            b = (o.b0 + (o.b1 - o.b0) * u) * D2R, cb = Math.cos(b), sb = Math.sin(b), sw = o.sweep * u * u;
          for (iv = 0; iv < nv; iv++) {
            var s = vs[iv] - 0.5, bend = o.camber * c * Math.sin(Math.PI * vs[iv]),
              ax = o.x + s * c * cb - sb * bend, tg = sw + s * c * sb + cb * bend;
            P.push([ax, r * cp - tg * sp, r * sp + tg * cp]);
          }
        }
        for (iu = 0; iu <= nu; iu++) for (iv = 0; iv < nv; iv++) {
          var A = P[Math.min(nu, iu + 1) * nv + iv], B = P[Math.max(0, iu - 1) * nv + iv], C = P[iu * nv + Math.min(nv - 1, iv + 1)], D = P[iu * nv + Math.max(0, iv - 1)],
            du = [A[0] - B[0], A[1] - B[1], A[2] - B[2]], dv = [C[0] - D[0], C[1] - D[1], C[2] - D[2]];
          N.push(norm([du[1] * dv[2] - du[2] * dv[1], du[2] * dv[0] - du[0] * dv[2], du[0] * dv[1] - du[1] * dv[0]]));
        }
        for (iu = 0; iu < nu; iu++) for (iv = 0; iv < nv - 1; iv++) {
          var p = iu * nv + iv;
          quad(grp(spin, o.mats[iv]), P, N, p, p + nv, p + nv + 1, p + 1);
        }
      }
    }

    // spinner: dark cap, bright lip ring, glossy bulb, rotor hub
    lathe('rotor', [[-1.255, 0], [-1.252, 0.025], [-1.25, 0.045]], M.nose);
    lathe('rotor', [[-1.25, 0.045], [-1.235, 0.08], [-1.215, 0.1]], M.lip);
    lathe('rotor', [[-1.215, 0.1], [-1.17, 0.165], [-1.1, 0.225], [-1, 0.272], [-0.88, 0.302], [-0.76, 0.312], [-0.66, 0.306], [-0.58, 0.29]], M.nose);
    lathe('rotor', [[-0.58, 0.29], [-0.56, 0.305], [-0.4, 0.305], [-0.38, 0.312]], M.hub);
    blades('rotor', { n: 12, x: -0.48, r0: 0.28, r1: 1.18, c0: 0.5, b0: 30, b1: 52, sweep: 0.32, camber: 0.08,
      vs: [0, 0.07, 0.25, 0.5, 0.75, 1], mats: [M.edge, M.blade, M.blade, M.blade, M.blade] });
    blades('aft', { n: 10, x: -0.22, r0: 0.33, r1: 0.98, c0: 0.22, b0: 14, b1: 26, sweep: -0.12, camber: 0.05,
      vs: [0, 0.5, 1], mats: [M.aft, M.aft] });
    // static body: aft hub, glass cowl, nozzle, combustor, exhaust cone
    lathe('body', [[-0.38, 0.312], [-0.3, 0.34], [-0.16, 0.36]], M.hub);
    lathe('body', [[-0.16, 0.36], [-0.05, 0.4], [0.1, 0.445], [0.3, 0.475], [0.5, 0.488], [0.7, 0.478], [0.86, 0.44], [0.98, 0.38], [1.08, 0.32]], M.shell);
    lathe('body', [[1.08, 0.32], [1.1, 0.27], [1.1, 0.26]], M.hub);
    lathe('body', [[1.1, 0.26], [1.16, 0.24], [1.24, 0.18], [1.32, 0.1], [1.41, 0]], M.cone);
    lathe('body', [[0.46, 0.27], [0.52, 0.27]], M.dark);
    lathe('body', [[0.52, 0.272], [0.545, 0.272]], M.cyan);
    lathe('body', [[0.545, 0.27], [0.62, 0.27]], M.dark);
    // turning core: shaft, compressor and turbine stages (striped rims read as blade rows)
    lathe('core', [[-0.14, 0.09], [1.08, 0.09]], M.dark, null, 16);
    function stage(x, r, alt) {
      lathe('core', [[x - 0.009, 0.09], [x - 0.009, r]], M.disc2, null, 24);
      lathe('core', [[x - 0.009, r], [x + 0.009, r]], M.disc, alt || M.disc2, lite ? 40 : 64);
    }
    var nc = lite ? 6 : 9, nt = lite ? 3 : 5, i;
    for (i = 0; i < nc; i++) stage(-0.08 + i * 0.5 / (nc - 1), 0.33 - i * 0.09 / (nc - 1));
    for (i = 0; i < nt; i++) stage(0.67 + i * 0.29 / (nt - 1), 0.25 + i * 0.07 / (nt - 1), i === 1 ? M.red : null);

    groups.forEach(function (g) { g.d = new Float32Array(g.d); });
    // draw order: opaque, then translucent blades, glass last (its inner and outer passes)
    var rank = function (g) { return g.mat.glass ? 2 : g.mat.m2[2] < 1 ? 1 : 0; };
    return groups.sort(function (a, b) { return rank(a) - rank(b); });
  }

  var VS = 'attribute vec3 aP;attribute vec3 aN;uniform mat3 uR;uniform vec2 uK;uniform float uCam,uOy;varying vec3 vN,vP;' +
    'void main(){vec3 p=uR*aP;vN=uR*aN;vP=p;float w=uCam-p.z;gl_Position=vec4(p.x*uK.x,p.y*uK.y+uOy*w,-p.z/3.0*w,w);}';
  var FS = 'precision mediump float;varying vec3 vN,vP;uniform vec3 uCol,uL1,uL2,uH;uniform vec4 uM,uM2;uniform float uSide,uDim,uFade,uEye;' +
    'void main(){vec3 n=normalize(vN);vec3 v=normalize(vec3(0.0,0.0,uEye)-vP);float f0=dot(n,v);' +
    'if(uSide*f0<0.0)discard;if(f0<0.0){n=-n;f0=-f0;}' +
    'float d1=max(dot(n,uL1),0.0),d2=max(dot(n,uL2),0.0),sp=pow(max(dot(n,uH),0.0),uM.w)*uM.z,e=n.y-0.42,g=sp+uM2.x*exp(-e*e*22.0),f=1.0-f0;f=f*f*f;' +
    'vec3 c=uCol*(uM.x+d1*uM.y)+vec3(g)+(d2*uM2.y*0.4+f*uM2.y*0.15)*vec3(0.7,0.85,1.0);' +
    'float a=min(1.0,uM2.z+f*uM2.w+sp*0.5*(1.0-uM2.z))*uFade;c=min(c,1.0)*uDim;gl_FragColor=vec4(c*a,a);}';

  function ease(x) { return 1 - Math.pow(1 - x, 3); }

  function mount(canvas, opts) {
    var reduced = !!opts.reduced, lite = !!opts.lite, alive = true;
    var gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: true, antialias: true, depth: true, powerPreference: 'low-power' });
    var api = { canvas: canvas, lite: lite, setPointer: function () {}, destroy: function () { alive = false; } };
    if (!gl) return api;   // no WebGL: the blueprint plate and callouts still carry the visual

    var groups = build(lite), prog = null, U = {}, aP, aN;
    function init() {
      function sh(type, src) { var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; }
      prog = gl.createProgram(); gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { prog = null; return; }
      gl.useProgram(prog);
      ['uR', 'uK', 'uCam', 'uOy', 'uCol', 'uL1', 'uL2', 'uH', 'uM', 'uM2', 'uSide', 'uDim', 'uFade', 'uEye'].forEach(function (n) { U[n] = gl.getUniformLocation(prog, n); });
      aP = gl.getAttribLocation(prog, 'aP'); aN = gl.getAttribLocation(prog, 'aN');
      gl.enableVertexAttribArray(aP); gl.enableVertexAttribArray(aN);
      groups.forEach(function (g) { g.buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, g.buf); gl.bufferData(gl.ARRAY_BUFFER, g.d, gl.STATIC_DRAW); g.n = g.d.length / 6; });
      gl.uniform3fv(U.uL1, L1); gl.uniform3fv(U.uL2, L2); gl.uniform3fv(U.uH, H); gl.uniform1f(U.uCam, CAM); gl.uniform1f(U.uEye, CAM);
      gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.clearColor(0, 0, 0, 0);
    }
    init();

    var w = 0, h = 0, dpr = 1, raf = 0, t0 = 0, last = 0, visible = true, px = 0, py = 0, tx = 0, ty = 0;
    function resize() {
      var r = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, lite ? 1.5 : 2); w = r.width; h = r.height;
      canvas.width = Math.max(1, Math.round(w * dpr)); canvas.height = Math.max(1, Math.round(h * dpr));
      if (reduced) draw(0); // animated mode redraws on the next frame
    }

    function draw(t) {
      if (!w || !h || !prog || gl.isContextLost()) return;
      var intro = reduced ? 1 : ease(Math.min(1, t / 2.6));
      px += (tx - px) * 0.05; py += (ty - py) * 0.05;
      var yaw = (27 + 3 * Math.sin(t * TAU / 26) + px * 6 + (1 - intro) * 16) * D2R,
        pitch = (8 + 1.5 * Math.sin(t * TAU / 19 + 1) - py * 4) * D2R,
        roll = (-1.5 + 0.8 * Math.sin(t * TAU / 31 + 2)) * D2R;
      // constant angular velocity on every stage (no intro offset, which made the rotor appear to slow down)
      var spins = { rotor: -t * TAU / 14, aft: t * TAU / 70, core: -t * TAU / 5, body: 0 };
      var cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch), cr = Math.cos(roll), sr = Math.sin(roll);
      // view = Rz(roll) * Rx(pitch) * Ry(yaw), as columns
      var b0 = sp * sy, b2 = -sp * cy,
        V0 = [cr * cy - sr * b0, sr * cy + cr * b0, -cp * sy], V1 = [-sr * cp, cr * cp, sp], V2 = [cr * sy - sr * b2, sr * sy + cr * b2, cp * cy];
      var R = {};
      for (var k in spins) {
        var c = Math.cos(spins[k]), s = Math.sin(spins[k]);   // view * Rx(spin), column-major
        R[k] = new Float32Array([V0[0], V0[1], V0[2], V1[0] * c + V2[0] * s, V1[1] * c + V2[1] * s, V1[2] * c + V2[2] * s,
          V2[0] * c - V1[0] * s, V2[1] * c - V1[1] * s, V2[2] * c - V1[2] * s]);
      }
      var S = Math.min(w / 3.3, h / 2.8) * (0.94 + 0.06 * intro);
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.uniform2f(U.uK, 2 * S * CAM / w, 2 * S * CAM / h); gl.uniform1f(U.uOy, -0.04);
      gl.uniform1f(U.uFade, reduced ? 1 : Math.min(1, t / 1.2));
      groups.forEach(function (g) {
        var m = g.mat;
        gl.bindBuffer(gl.ARRAY_BUFFER, g.buf);
        gl.vertexAttribPointer(aP, 3, gl.FLOAT, false, 24, 0); gl.vertexAttribPointer(aN, 3, gl.FLOAT, false, 24, 12);
        gl.uniformMatrix3fv(U.uR, false, R[g.spin]);
        gl.uniform3fv(U.uCol, m.col); gl.uniform4fv(U.uM, m.m); gl.uniform4fv(U.uM2, m.m2);
        gl.depthMask(m.m2[2] >= 1);
        if (m.glass) {   // inner (far) wall dimmed, then outer wall
          gl.uniform1f(U.uSide, -1); gl.uniform1f(U.uDim, m.back); gl.drawArrays(gl.TRIANGLES, 0, g.n);
          gl.uniform1f(U.uSide, 1); gl.uniform1f(U.uDim, 1); gl.drawArrays(gl.TRIANGLES, 0, g.n);
        } else { gl.uniform1f(U.uSide, 0); gl.uniform1f(U.uDim, 1); gl.drawArrays(gl.TRIANGLES, 0, g.n); }
      });
      gl.depthMask(true);
    }

    function tick(now) {
      raf = 0;
      if (!alive) return;
      if (!t0) t0 = now;
      // lite (phones): ~30 fps is plenty for this slow motion
      if (!lite || now - last > 30) { last = now; draw((now - t0) / 1000); }
      schedule();
    }
    function schedule() { if (alive && !reduced && visible && !document.hidden && !raf) raf = requestAnimationFrame(tick); }
    function onVis() { schedule(); }
    function onLost(e) { e.preventDefault(); cancelAnimationFrame(raf); raf = 0; }
    function onRestored() { init(); resize(); schedule(); }

    var ro = window.ResizeObserver ? new ResizeObserver(resize) : null;
    if (ro) ro.observe(canvas); else window.addEventListener('resize', resize);
    var io = window.IntersectionObserver ? new IntersectionObserver(function (es) { visible = es[0].isIntersecting; schedule(); }) : null;
    if (io) io.observe(canvas);
    document.addEventListener('visibilitychange', onVis);
    canvas.addEventListener('webglcontextlost', onLost);
    canvas.addEventListener('webglcontextrestored', onRestored);
    resize();
    schedule();

    api.setPointer = function (x, y) { if (!reduced) { tx = x; ty = y; } };
    api.destroy = function () {
      alive = false; cancelAnimationFrame(raf);
      if (ro) ro.disconnect(); else window.removeEventListener('resize', resize);
      if (io) io.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      canvas.removeEventListener('webglcontextlost', onLost);
      canvas.removeEventListener('webglcontextrestored', onRestored);
    };
    return api;
  }

  window.VMHeroEngine = { mount: mount };
})();
