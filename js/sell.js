/* Velmach Aerospace: Sell Your Inventory page (sell.html).
   Mounts the shared footer and runs the three-step intake form. Sending: with VM_CONFIG.rfq.endpoint set
   (js/site-config.js, e.g. a Formspree form) the form POSTs multipart data including the files; with it empty
   the visitor's email app opens with every field filled in, and they attach the file(s) themselves. */
(function () {
  'use strict';
  var doc = document;
  var $ = function (s, el) { return (el || doc).querySelector(s); };
  var $$ = function (s, el) { return Array.prototype.slice.call((el || doc).querySelectorAll(s)); };
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- shared footer (same as js/home.js) ---------- */
  function mountFooter(tries) {
    var host = $('#site-footer');
    if (!host || host.firstChild) return;
    if (window.React && window.ReactDOM && window.getDC && window.ReactDOM.createRoot && window.getDC('SiteFooter')) {
      window.ReactDOM.createRoot(host).render(window.React.createElement(window.getDC('SiteFooter')));
    } else if ((tries || 0) < 200) setTimeout(function () { mountFooter((tries || 0) + 1); }, 50);
  }
  mountFooter(0);

  /* ---------- smooth scroll to the form ---------- */
  $$('[data-scroll]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var target = $(a.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
      if (history.replaceState) history.replaceState(null, '', a.getAttribute('href'));
      setTimeout(function () { var h = $('.sl-step:not([hidden]) .sl-step-h'); h && h.focus({ preventScroll: true }); }, reduced ? 0 : 500);
    });
  });

  /* ---------- form ---------- */
  var form = $('#sl-form');
  if (!form) return;
  var steps = $$('.sl-step', form), pills = $$('.sl-pstep');
  var btnBack = $('#sl-back'), btnNext = $('#sl-next'), btnSubmit = $('#sl-submit');
  var live = $('#sl-live'), formErr = $('#sl-form-err');
  var drop = $('#sl-drop'), fileInput = $('#sl-files'), fileList = $('#sl-file-list'), filesErr = $('#sl-files-err');
  var success = $('#sl-success'), successBody = $('#sl-success-body');
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  var ALLOWED = ['xlsx', 'xls', 'csv', 'pdf'];
  var MAX = 10 * 1024 * 1024;
  var current = 1, files = [];
  var cfg = window.VM_CONFIG || {};
  var rfq = cfg.rfq || {};
  var TO = rfq.to || 'sales@velmachaerospace.com';
  var LABELS = ['Company & contact', 'Inventory type', 'Upload listing'];

  function announce(msg) { live.textContent = ''; setTimeout(function () { live.textContent = msg; }, 40); }
  function val(name) { var el = form.elements[name]; return el && el.value ? String(el.value).trim() : ''; }
  function types() { return $$('input[name="types"]:checked', form).map(function (x) { return x.value; }); }
  function fmtSize(n) { return n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(0) + ' KB' : (n / 1048576).toFixed(1) + ' MB'; }
  function ext(name) { var m = /\.([^.]+)$/.exec(name || ''); return m ? m[1].toLowerCase() : ''; }

  function setErr(id, msg) {
    var p = $('#' + id + '-err'), input = $('#' + id);
    if (p) p.textContent = msg || '';
    if (input && input.tagName !== 'DIV') { if (msg) input.setAttribute('aria-invalid', 'true'); else input.removeAttribute('aria-invalid'); }
  }

  function validate(step) {
    var errs = [];
    if (step === 1) {
      var checks = [
        ['sl-company', val('company') ? '' : 'Enter your company name.'],
        ['sl-contact', val('contact') ? '' : 'Enter a contact name.'],
        ['sl-email', !val('email') ? 'Enter your email address.' : (EMAIL_RE.test(val('email')) ? '' : 'Enter a valid email address, like name@company.com.')],
        ['sl-phone', !val('phone') ? 'Enter a phone number with country code.' :
          (/^\+?[\d\s().-]{7,}$/.test(val('phone')) && val('phone').replace(/\D/g, '').length >= 7 ? '' : 'Enter a valid phone number, including the country code (e.g. +971).')]
      ];
      checks.forEach(function (c) { setErr(c[0], c[1]); if (c[1]) errs.push(c[0]); });
    } else if (step === 2) {
      var none = !types().length;
      $('#sl-types-err').textContent = none ? 'Select at least one inventory type.' : '';
      $('.sl-types').classList.toggle('sl-types-wrap-err', none);
      if (none) errs.push('types');
    } else if (step === 3) {
      if (!files.length) { filesErr.textContent = 'Add at least one inventory file (.xlsx, .xls, .csv or .pdf).'; errs.push('sl-drop'); }
      else filesErr.textContent = '';
      drop.classList.toggle('is-invalid', !files.length);
    }
    if (errs.length) {
      var first = errs[0] === 'types' ? $('input[name="types"]', form) : $('#' + errs[0]);
      first && first.focus();
      announce(errs.length === 1 ? 'There is 1 error on this step.' : 'There are ' + errs.length + ' errors on this step.');
    }
    return !errs.length;
  }

  function show(step, focus) {
    current = step;
    steps.forEach(function (s) { s.hidden = Number(s.getAttribute('data-step')) !== step; });
    pills.forEach(function (p) {
      var n = Number(p.getAttribute('data-pstep'));
      p.classList.toggle('is-current', n === step);
      p.classList.toggle('is-done', n < step);
      if (n === step) p.setAttribute('aria-current', 'step'); else p.removeAttribute('aria-current');
      $('.sl-pstate', p).textContent = n === step ? ' (current step)' : n < step ? ' (completed)' : '';
    });
    btnBack.hidden = step === 1;
    btnNext.hidden = step === 3;
    btnSubmit.hidden = step !== 3;
    formErr.textContent = '';
    if (focus) {
      var h = $('.sl-step[data-step="' + step + '"] .sl-step-h', form);
      h.focus({ preventScroll: true });
      var top = $('.sl-panel').getBoundingClientRect().top;
      if (top < 80) $('#sell-form').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
      announce('Step ' + step + ' of 3: ' + LABELS[step - 1]);
    }
  }

  btnNext.addEventListener('click', function () { if (validate(current)) show(current + 1, true); });
  btnBack.addEventListener('click', function () { show(current - 1, true); });
  // Enter in a text field moves to the next step instead of submitting early
  form.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT' && e.target.type !== 'checkbox' && current < 3) { e.preventDefault(); btnNext.click(); }
  });
  // clear an error as soon as the field is corrected
  form.addEventListener('input', function (e) {
    var id = e.target.id;
    if (id && e.target.getAttribute('aria-invalid') === 'true') setErr(id, '');
    if (e.target.name === 'types' && types().length) { $('#sl-types-err').textContent = ''; $('.sl-types').classList.remove('sl-types-wrap-err'); }
  });

  /* ---------- files ---------- */
  function renderFiles() {
    fileList.textContent = '';
    files.forEach(function (f, i) {
      var li = doc.createElement('li'); li.className = 'sl-file';
      var e = doc.createElement('span'); e.className = 'sl-file-ext'; e.setAttribute('aria-hidden', 'true'); e.textContent = ext(f.name);
      var meta = doc.createElement('span'); meta.className = 'sl-file-meta';
      var n = doc.createElement('span'); n.className = 'sl-file-name'; n.textContent = f.name; n.title = f.name;
      var s = doc.createElement('span'); s.className = 'sl-file-size'; s.textContent = fmtSize(f.size);
      meta.appendChild(n); meta.appendChild(s);
      var rm = doc.createElement('button'); rm.type = 'button'; rm.className = 'sl-file-rm';
      rm.setAttribute('aria-label', 'Remove ' + f.name);
      rm.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
      rm.addEventListener('click', function () {
        files.splice(i, 1); renderFiles();
        announce(f.name + ' removed. ' + files.length + (files.length === 1 ? ' file' : ' files') + ' selected.');
        var next = $$('.sl-file-rm', fileList)[Math.min(i, files.length - 1)];
        (next || drop).focus();
      });
      li.appendChild(e); li.appendChild(meta); li.appendChild(rm);
      fileList.appendChild(li);
    });
  }

  function addFiles(list) {
    var rejected = [], added = 0;
    Array.prototype.forEach.call(list || [], function (f) {
      if (ALLOWED.indexOf(ext(f.name)) < 0) { rejected.push(f.name + ' is not an accepted file type (.xlsx, .xls, .csv or .pdf).'); return; }
      if (f.size > MAX) { rejected.push(f.name + ' is larger than 10 MB (' + fmtSize(f.size) + ').'); return; }
      if (files.some(function (x) { return x.name === f.name && x.size === f.size; })) return;
      files.push(f); added++;
    });
    renderFiles();
    filesErr.textContent = rejected.join(' ');
    drop.classList.toggle('is-invalid', rejected.length > 0);
    var msg = added ? added + (added === 1 ? ' file added. ' : ' files added. ') : '';
    announce(msg + (rejected.length ? rejected.join(' ') : '') || 'No files added.');
  }

  drop.addEventListener('click', function () { fileInput.click(); });
  drop.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
  });
  fileInput.addEventListener('change', function () { addFiles(fileInput.files); fileInput.value = ''; });
  ['dragenter', 'dragover'].forEach(function (t) {
    drop.addEventListener(t, function (e) { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'; drop.classList.add('is-over'); });
  });
  ['dragleave', 'dragend'].forEach(function (t) {
    drop.addEventListener(t, function (e) { if (t === 'dragleave' && drop.contains(e.relatedTarget)) return; drop.classList.remove('is-over'); });
  });
  drop.addEventListener('drop', function (e) {
    e.preventDefault(); drop.classList.remove('is-over');
    if (e.dataTransfer) addFiles(e.dataTransfer.files);
  });
  // a file dropped next to the zone should not open in the browser and leave the page
  ['dragover', 'drop'].forEach(function (t) {
    window.addEventListener(t, function (e) { if (!drop.contains(e.target)) e.preventDefault(); });
  });

  /* ---------- submit ---------- */
  function data() {
    return {
      company: val('company'), contact: val('contact'), email: val('email'), phone: val('phone'), country: val('country'),
      types: types(), lines: val('lines'), deal: val('deal'), notes: val('notes')
    };
  }

  function bodyText(d) {
    return [
      'INVENTORY OFFER - Velmach Aerospace', '',
      'COMPANY & CONTACT',
      'Company: ' + d.company,
      'Contact name: ' + d.contact,
      'Email: ' + d.email,
      'Phone: ' + d.phone,
      'Country: ' + (d.country || '-'), '',
      'INVENTORY',
      'Inventory type: ' + (d.types.join(', ') || '-'),
      'Approx. line items: ' + (d.lines || '-'),
      'Preferred deal: ' + (d.deal || '-'), '',
      'Notes:', d.notes || '-', '',
      'FILES (' + files.length + ')',
      files.map(function (f, i) { return (i + 1) + '. ' + f.name + ' (' + fmtSize(f.size) + ')'; }).join('\n') || '-'
    ].join('\n');
  }

  function para(html) { var p = doc.createElement('p'); p.innerHTML = html; return p; }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  function done(mode, d) {
    successBody.textContent = '';
    if (mode === 'mail') {
      $('#sl-success-h').textContent = 'Your email app has opened';
      successBody.appendChild(para('We have filled in an email to <strong>' + esc(TO) + '</strong> with your details.'));
      var note = para('<strong>Before you send it, attach your inventory file' + (files.length === 1 ? '' : 's') + '</strong> (' +
        esc(files.map(function (f) { return f.name; }).join(', ')) + ') to that email. Files cannot be added to it automatically.');
      note.className = 'sl-note';
      successBody.appendChild(note);
      successBody.appendChild(para('Once we receive it, our team replies with a preliminary evaluation within 48-72 business hours. ' +
        'If your email app did not open, write to <a href="mailto:' + esc(TO) + '">' + esc(TO) + '</a>.'));
    } else {
      $('#sl-success-h').textContent = 'Thank you, ' + (d && d.contact ? d.contact.split(' ')[0] : 'we have your list');
      successBody.appendChild(para('Your inventory list has been sent to our team. We reply with a preliminary evaluation within 48-72 business hours.'));
    }
    form.hidden = true; $('.sl-progress').hidden = true; success.hidden = false;
    $('#sl-success-h').focus({ preventScroll: true });
    $('#sell-form').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
    announce($('#sl-success-h').textContent + '. ' + successBody.textContent);
  }

  function mailto(d) {
    var subject = 'Inventory offer: ' + d.company;
    window.location.href = 'mailto:' + TO + '?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(bodyText(d));
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (current !== 3) { btnNext.click(); return; }
    if (!validate(3)) return;
    var d = data();
    if (val('website')) { done('sent', d); return; }   // spam trap filled: send nothing
    var endpoint = rfq.endpoint;
    if (!endpoint) { mailto(d); done('mail', d); return; }

    var fd = new FormData();
    fd.append('_subject', 'Inventory offer: ' + d.company);
    fd.append('_replyto', d.email);
    fd.append('company', d.company); fd.append('contact_name', d.contact); fd.append('email', d.email);
    fd.append('phone', d.phone); fd.append('country', d.country);
    fd.append('inventory_type', d.types.join(', '));
    fd.append('line_items', d.lines); fd.append('preferred_deal', d.deal); fd.append('notes', d.notes);
    fd.append('message', bodyText(d));
    files.forEach(function (f) { fd.append('attachment', f, f.name); });

    btnSubmit.disabled = true; btnBack.disabled = true;
    btnSubmit.textContent = 'Sending...';
    announce('Sending your inventory list.');
    fetch(endpoint, { method: 'POST', body: fd, headers: { Accept: 'application/json' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); done('sent', d); })
      .catch(function () {
        formErr.textContent = 'We could not send the form. Please try again, or email your list to ' + TO + '.';
        announce(formErr.textContent);
      })
      .then(function () { btnSubmit.disabled = false; btnBack.disabled = false; btnSubmit.textContent = 'Submit inventory'; });
  });

  $('#sl-again').addEventListener('click', function () {
    form.reset(); files = []; renderFiles();
    $$('.sl-err', form).forEach(function (p) { p.textContent = ''; });
    $$('[aria-invalid]', form).forEach(function (el) { el.removeAttribute('aria-invalid'); });
    success.hidden = true; form.hidden = false; $('.sl-progress').hidden = false;
    show(1, true);
  });

  show(1, false);
})();
