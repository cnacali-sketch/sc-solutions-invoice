// Screen Navigation
function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

// Toast
function showToast(message, duration = 3000) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('active');
    setTimeout(() => toast.classList.remove('active'), duration);
}

// Back Buttons
document.querySelectorAll('.back-btn').forEach(btn => {
    btn.addEventListener('click', () => showScreen(btn.dataset.target));
});

// Home Menu Buttons
document.querySelectorAll('.home-btn').forEach(btn => {
    btn.addEventListener('click', () => showScreen(btn.dataset.target));
});

// Invoice Date Default
const today = new Date();
const day = String(today.getDate()).padStart(2, '0');
const month = String(today.getMonth() + 1).padStart(2, '0');
const year = today.getFullYear();
document.getElementById('invoice_date').value = `${day}-${month}-${year}`;

// Load Invoice Number
fetch('/api/invoice-number').then(r => r.json()).then(d => {
    document.getElementById('invoice_no').value = d.number;
});

// Load Settings
let companySettings = {};
function loadSettings() {
    fetch('/api/settings').then(r => r.json()).then(d => {
        companySettings = d;
        document.getElementById('setting_company_name').value = d.company_name || '';
        document.getElementById('setting_address').value = d.address || '';
        document.getElementById('setting_gst').value = d.gst || '';
        document.getElementById('setting_pan').value = d.pan || '';
        document.getElementById('setting_phone').value = d.phone || '';
        document.getElementById('setting_default_gst').value = d.default_gst || '18%';
        document.getElementById('setting_terms').value = (d.terms || []).join('\n');
        document.getElementById('gst_default').value = d.default_gst || '18%';
    });
}
loadSettings();

// Save Settings
function saveSettings() {
    const data = {
        company_name: document.getElementById('setting_company_name').value,
        address: document.getElementById('setting_address').value,
        gst: document.getElementById('setting_gst').value,
        pan: document.getElementById('setting_pan').value,
        phone: document.getElementById('setting_phone').value,
        default_gst: document.getElementById('setting_default_gst').value,
        terms: document.getElementById('setting_terms').value.split('\n').map(t => t.trim()).filter(t => t),
    };
    fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
        .then(r => r.json()).then(d => {
            showToast('Settings saved!');
            loadSettings();
        });
}

// Items
function createItemRow(item = {}) {
    const container = document.getElementById('items-container');
    const row = document.createElement('div');
    row.className = 'item-row';
    row.innerHTML = `
        <input class="item-desc" type="text" placeholder="Description" value="${item.description || ''}">
        <input type="text" placeholder="Area" value="${item.area || ''}">
        <select>
            <option value="0%" ${item.gst === '0%' ? 'selected' : ''}>0%</option>
            <option value="5%" ${item.gst === '5%' ? 'selected' : ''}>5%</option>
            <option value="12%" ${item.gst === '12%' ? 'selected' : ''}>12%</option>
            <option value="18%" ${(!item.gst || item.gst === '18%') ? 'selected' : ''}>18%</option>
            <option value="28%" ${item.gst === '28%' ? 'selected' : ''}>28%</option>
        </select>
        <input type="number" placeholder="Qty" value="${item.qty || '1'}">
        <input type="number" placeholder="Rate" value="${item.rate || ''}">
        <button class="btn-remove">&#10005;</button>
    `;
    row.querySelector('.btn-remove').addEventListener('click', () => {
        row.remove();
        updateTotal();
    });
    row.querySelectorAll('input, select').forEach(el => {
        el.addEventListener('input', updateTotal);
    });
    container.appendChild(row);
    updateTotal();
}

function addCustomItem() {
    createItemRow({ area: document.getElementById('unit_type').value, gst: document.getElementById('gst_default').value });
}

function clearItems() {
    document.getElementById('items-container').innerHTML = '';
    updateTotal();
}

function collectItems() {
    const items = [];
    document.querySelectorAll('#items-container .item-row').forEach(row => {
        const inputs = row.querySelectorAll('input, select');
        const desc = inputs[0].value.trim();
        if (!desc) return;
        const qty = parseFloat(inputs[3].value) || 0;
        const rate = parseFloat(inputs[4].value) || 0;
        if (qty <= 0 || rate < 0) return;
        items.push({
            description: desc,
            area: inputs[1].value.trim() || document.getElementById('unit_type').value,
            gst: inputs[2].value,
            qty: inputs[3].value,
            rate: inputs[4].value,
        });
    });
    return items;
}

function updateTotal() {
    const items = collectItems();
    fetch('/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items }),
    })
        .then(r => r.json())
        .then(d => {
            document.getElementById('total-display').textContent = `Subtotal ${d.subtotal} | Tax ${d.tax} | Total ${d.total}`;
        });
}

// Suggestions
function showSuggestions() {
    const unit = document.getElementById('unit_type').value;
    const work = document.getElementById('work_type').value;
    fetch(`/api/suggestions?unit=${encodeURIComponent(unit)}&work=${encodeURIComponent(work)}`)
        .then(r => r.json())
        .then(items => {
            const list = document.getElementById('suggestions-list');
            list.innerHTML = '';
            if (!items.length) {
                list.innerHTML = '<p class="empty-state">No suggestions for this combination.</p>';
            }
            items.forEach(item => {
                const btn = document.createElement('button');
                btn.className = 'suggestion-btn';
                const qty = parseFloat(item.qty) || 1;
                const rate = parseFloat(item.rate) || 0;
                const total = (qty * rate).toFixed(2);
                btn.innerHTML = `
                    <div class="desc">${escapeHtml(item.description)}</div>
                    <div class="meta">${item.area} | GST ${item.gst} | Qty ${item.qty} | Rate ₹${item.rate} | Total ₹${total}</div>
                `;
                btn.addEventListener('click', () => {
                    createItemRow(item);
                    closeSuggestions();
                });
                list.appendChild(btn);
            });
            document.getElementById('suggestions-modal').classList.add('active');
        });
}

function closeSuggestions() {
    document.getElementById('suggestions-modal').classList.remove('active');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Catalog Screen
function refreshCatalog() {
    const unit = document.getElementById('catalog_unit_type').value;
    fetch(`/api/suggestions?unit=${encodeURIComponent(unit)}&work=Service`)
        .then(r => r.json())
        .then(items => {
            const container = document.getElementById('catalog-container');
            container.innerHTML = '';
            if (!items.length) {
                container.innerHTML = '<p class="empty-state">No catalog items available.</p>';
                return;
            }
            const workGroups = {};
            items.forEach(item => {
                const work = item.area || 'General';
                if (!workGroups[work]) workGroups[work] = [];
                workGroups[work].push(item);
            });
            Object.entries(workGroups).forEach(([work, groupItems]) => {
                const title = document.createElement('div');
                title.className = 'catalog-work-type';
                title.textContent = work;
                container.appendChild(title);
                groupItems.forEach(item => {
                    const btn = document.createElement('button');
                    btn.className = 'catalog-btn';
                    const qty = parseFloat(item.qty) || 1;
                    const rate = parseFloat(item.rate) || 0;
                    const total = (qty * rate).toFixed(2);
                    btn.innerHTML = `
                        <div class="desc">${escapeHtml(item.description)}</div>
                        <div class="meta">${item.area} | GST ${item.gst} | Qty ${item.qty} | Rate ₹${item.rate} | Total ₹${total}</div>
                        <div class="add-hint">Tap to add to invoice</div>
                    `;
                    btn.addEventListener('click', () => {
                        createItemRow(item);
                        showToast('Item added!');
                    });
                    container.appendChild(btn);
                });
            });
        });
}
document.getElementById('catalog_unit_type').addEventListener('change', refreshCatalog);

// History
function refreshHistory() {
    fetch('/api/history')
        .then(r => r.json())
        .then(history => {
            const container = document.getElementById('history-container');
            container.innerHTML = '';
            if (!history.length) {
                container.innerHTML = '<p class="empty-state">No invoices generated yet.</p>';
                return;
            }
            history.forEach(rec => {
                const card = document.createElement('div');
                card.className = 'history-card';
                card.innerHTML = `
                    <div class="header">${escapeHtml(rec.invoice_no || '')}</div>
                    <div class="meta">${escapeHtml(rec.customer_name || '')} | ${escapeHtml(rec.invoice_date || '')}</div>
                    <div class="total">${rec.total || ''}</div>
                    <div class="actions">
                        <button class="btn-download" onclick="downloadInvoice('${rec.path?.split('/').pop() || ''}')">Download</button>
                        <button class="btn-view" onclick="viewInvoice('${rec.path?.split('/').pop() || ''}')">View</button>
                    </div>
                `;
                container.appendChild(card);
            });
        });
}

function downloadInvoice(filename) {
    if (!filename) return;
    window.open(`/download/${filename}`, '_blank');
}

function viewInvoice(filename) {
    if (!filename) return;
    window.open(`/api/invoice/${filename}`, '_blank');
}

// Generate PDF
function generatePDF() {
    const items = collectItems();
    if (!items.length) {
        showToast('Please add at least one item!');
        return;
    }
    const customerName = document.getElementById('customer_name').value.trim();
    if (!customerName) {
        showToast('Please enter customer name!');
        return;
    }

    const data = {
        invoice_no: document.getElementById('invoice_no').value,
        invoice_date: document.getElementById('invoice_date').value,
        payment_status: document.getElementById('payment_status').value,
        customer_name: customerName,
        customer_phone: document.getElementById('customer_phone').value,
        customer_address: document.getElementById('customer_address').value,
        unit_type: document.getElementById('unit_type').value,
        work_type: document.getElementById('work_type').value,
        items: items,
        discount: document.getElementById('discount').value,
        template: selectedTemplate,
    };

    showToast('Generating PDF...');
    fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    })
        .then(r => r.json())
        .then(result => {
            if (result.error) {
                showToast(result.error);
                return;
            }
            showToast('PDF generated! Downloading...');
            setTimeout(() => {
                window.open(result.download_url, '_blank');
            }, 500);
            refreshHistory();
            // Reset invoice number
            fetch('/api/invoice-number').then(r => r.json()).then(d => {
                document.getElementById('invoice_no').value = d.number;
            });
        });
}

// Catalog screen listener
const catalogScreen = document.getElementById('screen-catalog');
const catalogObserver = new MutationObserver(mutations => {
    mutations.forEach(mutation => {
        if (mutation.target.classList.contains('active')) {
            refreshCatalog();
        }
    });
});
catalogObserver.observe(catalogScreen, { attributes: true, attributeFilter: ['class'] });

// History screen listener
const historyScreen = document.getElementById('screen-history');
const historyObserver = new MutationObserver(mutations => {
    mutations.forEach(mutation => {
        if (mutation.target.classList.contains('active')) {
            refreshHistory();
        }
    });
});
historyObserver.observe(historyScreen, { attributes: true, attributeFilter: ['class'] });

// Template selection
let selectedTemplate = "A";
function selectTemplate(btn) {
    document.querySelectorAll('.template-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedTemplate = btn.dataset.template;
}

// Initial total
updateTotal();
