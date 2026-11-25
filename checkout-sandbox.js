'use strict';

const api = 'https://api.zunpyai.com/v1';
const storageKey = 'zunpy-sandbox-checkout';
const byId = (id) => document.getElementById(id);
let checkout = JSON.parse(sessionStorage.getItem(storageKey) || '{}');

function save(changes) {
  checkout = { ...checkout, ...changes };
  sessionStorage.setItem(storageKey, JSON.stringify(checkout));
}

function report(message) {
  byId('status').textContent = message;
}

async function request(path, { method = 'GET', body } = {}) {
  const headers = {};
  if (body) headers['Content-Type'] = 'application/json';
  if (path.startsWith('/orders/') && checkout.order_token) {
    headers['X-ZUNPY-Order-Token'] = checkout.order_token;
  }
  const response = await fetch(api + path, {
    method,
    headers,
    body: body && JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail?.message || data.detail;
    throw new Error(typeof detail === 'string' ? detail : `Error HTTP ${response.status}`);
  }
  return data;
}

function orderPath() {
  return '/orders/' + encodeURIComponent(checkout.order_id);
}

async function refresh() {
  const result = await request(orderPath() + '/status');
  byId('upload').hidden = result.status !== 'WAITING_UPLOAD';
  if (result.status === 'COMPLETED') {
    const csv = await request(orderPath() + '/result');
    byId('download').href = csv.download_url;
    byId('download').hidden = false;
  }
  report(`Pedido ${result.order_id} · ${result.status}${result.review ? ' · Requiere revisión' : ''}`);
}

async function capture() {
  const id = encodeURIComponent(checkout.paypal_order_id);
  const order = await request('/payments/paypal/order/' + id + '/capture', {
    method: 'POST',
    body: { claim_secret: checkout.claim_secret },
  });
  save({ order_id: order.order_id, order_token: order.order_token });
  byId('setup').hidden = true;
  byId('paypal').hidden = true;
  byId('retry').hidden = true;
  byId('invoice').hidden = false;
  await refresh();
}

async function act(button, action) {
  button.disabled = true;
  try {
    await action();
  } catch (error) {
    report(error.message);
  } finally {
    button.disabled = false;
  }
}

byId('setup').addEventListener('submit', (event) => {
  event.preventDefault();
  act(event.submitter, async () => {
    if (!window.paypal) {
      const sdk = document.createElement('script');
      const parameters = new URLSearchParams({
        'client-id': byId('client').value,
        currency: 'EUR',
        intent: 'capture',
      });
      sdk.src = 'https://www.paypal.com/sdk/js?' + parameters;
      await new Promise((resolve, reject) => {
        sdk.onload = resolve;
        sdk.onerror = () => reject(new Error('No se pudo cargar PayPal Sandbox.'));
        document.head.append(sdk);
      });
    }
    await window.paypal.Buttons({
      fundingSource: window.paypal.FUNDING.PAYPAL,
      createOrder: async () => {
        const order = await request('/payments/paypal/order', { method: 'POST' });
        const approval = new URL(order.approval_url);
        if (approval.origin !== 'https://www.sandbox.paypal.com' ||
            order.currency !== 'EUR' || order.amount_cents !== 2900) {
          throw new Error('La API no devolvió la configuración de pago esperada para esta prueba.');
        }
        save({ paypal_order_id: order.paypal_order_id, claim_secret: order.claim_secret });
        return order.paypal_order_id;
      },
      onApprove: async ({ orderID }) => {
        if (orderID !== checkout.paypal_order_id) throw new Error('Pedido PayPal inesperado.');
        save({ approved: true });
        byId('retry').hidden = false;
        await act(byId('retry'), capture);
      },
      onCancel: () => report('Pago cancelado. Puedes volver a intentarlo.'),
      onError: (error) => report(error.message || 'Error en PayPal Sandbox.'),
    }).render('#paypal');
    byId('setup').hidden = true;
  });
});

byId('retry').addEventListener('click', (event) => act(event.currentTarget, capture));
byId('refresh').addEventListener('click', (event) => act(event.currentTarget, refresh));

byId('upload').addEventListener('submit', (event) => {
  event.preventDefault();
  act(event.submitter, async () => {
    const file = byId('pdf').files[0];
    if (!file || !/\.pdf$/i.test(file.name) || !file.size || file.size > 10 * 1024 * 1024) {
      throw new Error('Selecciona un PDF de hasta 10 MiB.');
    }
    report('Validando y procesando la factura…');
    const base = orderPath();
    if (!checkout.uploadValidated) {
      let ticket = checkout.ticket;
      if (!ticket || Date.parse(ticket.expires_at) <= Date.now()) {
        ticket = await request(base + '/files', {
          method: 'POST',
          body: { filename: file.name, size_bytes: file.size, content_type: 'application/pdf' },
        });
        save({ ticket, uploadName: file.name, uploadSize: file.size });
      }
      if (checkout.uploadName !== file.name || checkout.uploadSize !== file.size) {
        throw new Error('Selecciona el PDF de la carga anterior o espera a que caduque su enlace.');
      }
      const upload = await fetch(ticket.upload_url, {
        method: 'PUT',
        headers: ticket.required_headers,
        body: file,
      });
      if (!upload.ok) throw new Error(`Error al subir el PDF (HTTP ${upload.status}).`);
      await request(base + '/files/' + encodeURIComponent(ticket.upload_id) + '/complete', {
        method: 'POST',
      });
      save({ uploadValidated: true, ticket: null });
    }
    await request(base + '/submit', { method: 'POST' });
    await refresh();
  });
});

if (checkout.order_id) {
  byId('setup').hidden = true;
  byId('invoice').hidden = false;
  act(byId('refresh'), refresh);
} else if (checkout.approved) {
  byId('setup').hidden = true;
  byId('retry').hidden = false;
}
