/* Velmach Aerospace: "Is this an AOG?" box under the home search.
   Ticked: a panel offers the AOG desk (email, WhatsApp, call) with the typed part number filled in, and submitting the
   search opens the AOG email instead of the search results. Unticked: the search works as before. */
(function () {
  var box = document.querySelector('[data-paog]'); if (!box) return;
  var form = box.closest('form'), input = form && form.querySelector('input[name="q"]');
  var check = box.querySelector('[data-paog-check]'), panel = box.querySelector('[data-paog-panel]');
  var mail = box.querySelector('[data-paog-mail]'), wa = box.querySelector('[data-paog-wa]');
  var btnLabel = form && form.querySelector('.psearch-btn span'), btnText = btnLabel ? btnLabel.textContent : '';
  var C = window.VM_CONFIG || {}, to = (C.email && C.email.aog) || 'AOG@velmachaerospace.com';
  var waNum = ((C.phone && C.phone.tel) || '+971509259286').replace(/\D/g, '');

  function body(pn) {
    return 'AOG request (Aircraft on Ground)\nPart number: ' + (pn || '') + '\nQuantity:\nAircraft type / registration:\nDelivery location:\nContact name and phone:\n';
  }
  function links() {
    var pn = input ? input.value.trim() : '';
    mail.href = 'mailto:' + to + '?subject=' + encodeURIComponent('AOG request' + (pn ? ': ' + pn : '')) + '&body=' + encodeURIComponent(body(pn));
    wa.href = 'https://wa.me/' + waNum + '?text=' + encodeURIComponent(body(pn));
  }
  function sync() {
    var on = check.checked;
    panel.hidden = !on;
    box.classList.toggle('is-on', on);
    if (btnLabel) btnLabel.textContent = on ? 'Send AOG request' : btnText;
    links();
  }
  check.addEventListener('change', sync);
  if (input) input.addEventListener('input', links);
  if (form) form.addEventListener('submit', function (e) {
    if (!check.checked) return;
    e.preventDefault(); links();
    location.href = mail.href;
  }, true);
  sync();
})();
