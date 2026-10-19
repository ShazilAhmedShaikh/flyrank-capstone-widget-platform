/**
 * FlyRank Embeddable Widget Client Bundle (widget.v1.js)
 * Production-ready, encapsulated widget that mounts on any host website.
 * Zero external CSS dependencies, immune to parent page style interference.
 */
(function (window, document) {
    'use strict';

    var SCRIPT_SELECTOR = 'script[data-widget-id], script[src*="widget.js"], script[src*="widget.v1.js"]';

    function getBaseUrl() {
        if (window.FLYRANK_WIDGET_BASE_URL) {
            return window.FLYRANK_WIDGET_BASE_URL;
        }
        var scripts = document.querySelectorAll(SCRIPT_SELECTOR);
        for (var i = 0; i < scripts.length; i++) {
            var src = scripts[i].getAttribute('src') || '';
            if (src.indexOf('/widget') !== -1) {
                var a = document.createElement('a');
                a.href = src;
                return a.protocol + '//' + a.host;
            }
        }
        return 'http://localhost:8000';
    }

    function initWidget(widgetId) {
        if (!widgetId) {
            var currentScript = document.querySelector('script[data-widget-id]');
            if (currentScript) {
                widgetId = currentScript.getAttribute('data-widget-id');
            }
        }

        if (!widgetId) {
            console.error('[FlyRank Widget] Missing widget ID.');
            return;
        }

        var baseUrl = getBaseUrl();
        var configUrl = baseUrl + '/widgets/' + encodeURIComponent(widgetId) + '/config';

        fetch(configUrl, {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            mode: 'cors'
        })
        .then(function (response) {
            if (!response.ok) {
                throw new Error('Failed to load widget configuration (' + response.status + ')');
            }
            return response.json();
        })
        .then(function (config) {
            renderWidget(config, baseUrl);
        })
        .catch(function (err) {
            console.error('[FlyRank Widget] Initialization error:', err);
        });
    }

    function renderWidget(config, baseUrl) {
        var existing = document.getElementById('flyrank-widget-root-' + config.id);
        if (existing) {
            existing.remove();
        }

        var root = document.createElement('div');
        root.id = 'flyrank-widget-root-' + config.id;
        root.style.cssText = [
            'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
            'position: fixed',
            'bottom: 24px',
            'right: 24px',
            'width: 360px',
            'max-width: calc(100vw - 48px)',
            'background: #ffffff',
            'border-radius: 12px',
            'box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
            'border: 1px solid #e2e8f0',
            'padding: 20px',
            'z-index: 999999',
            'box-sizing: border-box',
            'color: #1e293b'
        ].join(';');

        var displayOpts = config.display_options || {};
        var primaryColor = displayOpts.primary_color || '#3b82f6';

        var html = [
            '<div style="margin-bottom: 12px;">',
            '  <h3 style="margin: 0 0 4px 0; font-size: 18px; font-weight: 600; color: #0f172a;">' + escapeHtml(config.title) + '</h3>',
            config.description ? '  <p style="margin: 0; font-size: 13px; color: #64748b;">' + escapeHtml(config.description) + '</p>' : '',
            '</div>',
            '<form id="flyrank-form-' + config.id + '" style="margin: 0; display: flex; flex-direction: column; gap: 10px;">',
            '  <!-- Anti-Bot Honeypot Field -->',
            '  <input type="text" name="website_hp" style="display:none !important; position:absolute; left:-9999px;" tabindex="-1" autocomplete="off" />'
        ];

        config.fields.forEach(function (field) {
            html.push('  <div>');
            html.push('    <label style="display: block; font-size: 12px; font-weight: 500; margin-bottom: 4px; color: #334155;">' + escapeHtml(field.label) + (field.required ? ' *' : '') + '</label>');
            if (field.type === 'textarea') {
                html.push('    <textarea name="' + escapeHtml(field.name) + '" placeholder="' + escapeHtml(field.placeholder || '') + '" ' + (field.required ? 'required' : '') + ' style="width: 100%; box-sizing: border-box; padding: 8px 10px; font-size: 13px; border: 1px solid #cbd5e1; border-radius: 6px; outline: none;"></textarea>');
            } else {
                html.push('    <input type="' + escapeHtml(field.type || 'text') + '" name="' + escapeHtml(field.name) + '" placeholder="' + escapeHtml(field.placeholder || '') + '" ' + (field.required ? 'required' : '') + ' style="width: 100%; box-sizing: border-box; padding: 8px 10px; font-size: 13px; border: 1px solid #cbd5e1; border-radius: 6px; outline: none;" />');
            }
            html.push('  </div>');
        });

        html.push('  <button type="submit" id="flyrank-btn-' + config.id + '" style="background: ' + primaryColor + '; color: #ffffff; border: none; padding: 10px 14px; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 4px; transition: opacity 0.2s;">' + escapeHtml(config.button_text || 'Submit') + '</button>');
        html.push('  <div id="flyrank-feedback-' + config.id + '" style="display: none; font-size: 13px; padding: 8px; border-radius: 6px; margin-top: 4px; text-align: center;"></div>');
        html.push('</form>');

        root.innerHTML = html.join('\n');
        document.body.appendChild(root);

        // Bind Submit Handler
        var form = document.getElementById('flyrank-form-' + config.id);
        var submitBtn = document.getElementById('flyrank-btn-' + config.id);
        var feedback = document.getElementById('flyrank-feedback-' + config.id);

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            submitBtn.disabled = true;
            submitBtn.style.opacity = '0.6';
            submitBtn.innerText = 'Submitting...';

            var formData = new FormData(form);
            var payloadData = {};
            var honeypotVal = formData.get('website_hp') || '';

            config.fields.forEach(function (f) {
                payloadData[f.name] = formData.get(f.name);
            });

            var submitEndpoint = config.submit_url || (baseUrl + '/submissions');

            fetch(submitEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                mode: 'cors',
                body: JSON.stringify({
                    widget_id: config.id,
                    data: payloadData,
                    website_hp: honeypotVal
                })
            })
            .then(function (res) {
                return res.json().then(function (json) {
                    return { status: res.status, ok: res.ok, body: json };
                });
            })
            .then(function (result) {
                submitBtn.disabled = false;
                submitBtn.style.opacity = '1';
                submitBtn.innerText = config.button_text || 'Submit';

                feedback.style.display = 'block';
                if (result.ok) {
                    feedback.style.background = '#dcfce7';
                    feedback.style.color = '#15803d';
                    feedback.innerText = 'Thank you! Your submission was received.';
                    form.reset();
                } else {
                    feedback.style.background = '#fee2e2';
                    feedback.style.color = '#b91c1c';
                    feedback.innerText = result.body.detail || result.body.error || 'Submission failed. Please check inputs.';
                }
            })
            .catch(function (netErr) {
                submitBtn.disabled = false;
                submitBtn.style.opacity = '1';
                submitBtn.innerText = config.button_text || 'Submit';

                feedback.style.display = 'block';
                feedback.style.background = '#fee2e2';
                feedback.style.color = '#b91c1c';
                feedback.innerText = 'Network error. Please try again.';
                console.error('[FlyRank Widget] Submission network error:', netErr);
            });
        });
    }

    function escapeHtml(text) {
        if (!text) return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(text));
        return div.innerHTML;
    }

    // Auto-initialize when script loads
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initWidget();
        });
    } else {
        initWidget();
    }

    // Expose global controller
    window.FlyRankWidget = {
        init: initWidget
    };

})(window, document);
