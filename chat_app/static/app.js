/**
 * Atlas Chat — Client-side chat logic
 * Handles: SSE streaming from fetch ReadableStream, auto-expanding textarea,
 * example query buttons, keyboard shortcuts, tool chip rendering,
 * sidebar thread management (create, switch, delete, rename).
 */
(function () {
    'use strict';

    // ---- DOM references ----
    var messagesEl = document.getElementById('chat-messages');
    var inputEl = document.getElementById('chat-input');
    var formEl = document.getElementById('chat-form');
    var sendBtn = document.getElementById('send-btn');
    var sidebarEl = document.getElementById('sidebar');
    var threadListEl = document.getElementById('thread-list');
    var newChatBtn = document.getElementById('new-chat-btn');

    // ---- Dark mode toggle (placed before early return so it works on login splash) ----
    var themeToggleBtn = document.getElementById('theme-toggle');
    var themeToggleIcon = document.getElementById('theme-toggle-icon');

    function updateDarkModeIcon(theme) {
        if (!themeToggleIcon) return;
        // ☀ (sun) in dark mode, ☾ (crescent moon) in light mode
        themeToggleIcon.innerHTML = theme === 'dark' ? '&#9790;' : '&#9788;';
    }

    function toggleDarkMode() {
        var current = document.documentElement.getAttribute('data-theme') || 'light';
        var next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('atlas-theme', next);
        updateDarkModeIcon(next);
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleDarkMode);
    }

    updateDarkModeIcon(document.documentElement.getAttribute('data-theme') || 'light');

    if (!messagesEl || !inputEl || !formEl || !sendBtn) {
        // Not on the chat page — silently exit
        return;
    }

    var isStreaming = false;
    var currentAbortController = null;

    // ---- Thread state ----
    var currentThreadId = null;

    // ---- Auto-expanding textarea ----
    function resizeInput() {
        inputEl.style.height = 'auto';
        var maxH = 200;
        var newH = Math.min(inputEl.scrollHeight, maxH);
        inputEl.style.height = newH + 'px';
    }

    function resetInputSize() {
        inputEl.style.height = 'auto';
    }

    inputEl.addEventListener('input', resizeInput);

    // ---- Scroll helpers ----
    function scrollToBottom() {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    // ---- JSON syntax highlighter ----
    function highlightJson(jsonStr) {
        var escaped = jsonStr
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        return escaped.replace(
            /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
            function(match) {
                var cls = 'json-num';
                if (/^"/.test(match)) {
                    cls = /:$/.test(match) ? 'json-key' : 'json-str';
                } else if (/true|false/.test(match)) {
                    cls = 'json-bool';
                } else if (/null/.test(match)) {
                    cls = 'json-null';
                }
                return '<span class="' + cls + '">' + match + '</span>';
            }
        );
    }

    // ---- Copy to clipboard utility ----
    function copyText(text, btn) {
        if (!navigator.clipboard) return;
        navigator.clipboard.writeText(text).then(function() {
            var original = btn.textContent;
            btn.textContent = 'Copied!';
            btn.classList.add('copy-success');
            btn.disabled = true;
            setTimeout(function() {
                btn.textContent = original;
                btn.classList.remove('copy-success');
                btn.disabled = false;
            }, 1500);
        }).catch(function(err) {
            console.error('[Atlas] Copy failed:', err);
        });
    }

    // ---- Message DOM builders ----
    function createMessageEl(role) {
        var div = document.createElement('div');
        div.className = 'message ' + (role === 'user' ? 'user-message' : 'assistant-message');
        var content = document.createElement('div');
        content.className = 'message-content';
        div.appendChild(content);
        return { wrapper: div, content: content };
    }

    function appendUserMessage(text) {
        var els = createMessageEl('user');
        var p = document.createElement('p');
        p.textContent = text;
        els.content.appendChild(p);
        messagesEl.appendChild(els.wrapper);
        scrollToBottom();
    }

    /** Create assistant message container and return helpers for streaming into it. */
    function createAssistantMessage() {
        var els = createMessageEl('assistant');
        var textNode = document.createTextNode('');
        var cursor = document.createElement('span');
        cursor.className = 'streaming-cursor';
        els.content.appendChild(textNode);
        els.content.appendChild(cursor);

        var dotsEl = document.createElement('div');
        dotsEl.className = 'thinking-dots';
        dotsEl.innerHTML = '<span></span><span></span><span></span>';
        els.content.insertBefore(dotsEl, textNode);
        scrollToBottom();

        var dotsRemoved = false;
        function removeDots() {
            if (!dotsRemoved && dotsEl.parentNode) {
                dotsEl.parentNode.removeChild(dotsEl);
                dotsRemoved = true;
            }
        }

        var copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.type = 'button';
        copyBtn.title = 'Copy response';
        copyBtn.textContent = 'Copy';
        copyBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            copyText(textNode.textContent, copyBtn);
        });
        els.content.appendChild(copyBtn);

        messagesEl.appendChild(els.wrapper);
        scrollToBottom();

        return {
            removeDots: removeDots,
            markInterrupted: function () {
                removeDots();
                cursor.remove();
                var marker = document.createElement('span');
                marker.className = 'interrupted-marker';
                marker.textContent = ' [response cancelled]';
                els.content.appendChild(marker);
            },
            appendText: function (chunk) {
                textNode.textContent += chunk;
                scrollToBottom();
            },
            addToolPanel: function (toolName, params, result, status) {
                var details = document.createElement('details');
                details.className = 'tool-panel';

                var summary = document.createElement('summary');
                summary.className = 'tool-panel-summary';
                var icon = document.createElement('span');
                icon.className = 'tool-panel-icon';
                var nameSpanEl = document.createElement('span');
                nameSpanEl.className = 'tool-panel-name';
                nameSpanEl.textContent = toolName;
                var statusEl = document.createElement('span');
                statusEl.className = 'tool-panel-status ' + (status === 'error' ? 'status-error' : 'status-success');
                statusEl.textContent = status === 'error' ? 'Error' : 'Success';
                summary.appendChild(icon);
                summary.appendChild(nameSpanEl);
                summary.appendChild(statusEl);

                var body = document.createElement('div');
                body.className = 'tool-panel-body';

                if (params && Object.keys(params).length > 0) {
                    var paramLabel = document.createElement('div');
                    paramLabel.className = 'tool-panel-label';
                    paramLabel.textContent = 'Parameters';
                    body.appendChild(paramLabel);
                    var paramPre = document.createElement('pre');
                    paramPre.className = 'tool-panel-json';
                    paramPre.innerHTML = highlightJson(JSON.stringify(params, null, 2));
                    body.appendChild(paramPre);
                }

                if (result) {
                    var resultLabel = document.createElement('div');
                    resultLabel.className = 'tool-panel-label';
                    resultLabel.textContent = 'Exchange Result';
                    body.appendChild(resultLabel);
                    var resultPre = document.createElement('pre');
                    resultPre.className = 'tool-panel-json tool-panel-result';
                    var resultStr;
                    try {
                        var parsed = JSON.parse(result);
                        resultStr = JSON.stringify(parsed, null, 2);
                    } catch (e) {
                        resultStr = result;
                    }
                    resultPre.innerHTML = highlightJson(resultStr);
                    body.appendChild(resultPre);

                    var toolCopyBtn = document.createElement('button');
                    toolCopyBtn.className = 'copy-btn tool-panel-copy';
                    toolCopyBtn.type = 'button';
                    toolCopyBtn.title = 'Copy Exchange JSON';
                    toolCopyBtn.textContent = 'Copy JSON';
                    toolCopyBtn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        copyText(resultStr || '', toolCopyBtn);
                    });
                    body.appendChild(toolCopyBtn);
                }

                details.appendChild(summary);
                details.appendChild(body);
                els.content.insertBefore(details, textNode);
                scrollToBottom();
                return details;
            },
            insertCard: function(cardEl) {
                els.content.insertBefore(cardEl, textNode);
                scrollToBottom();
            },
            markToolDone: function (panel) {
                if (panel) {
                    panel.classList.add('done');
                }
            },
            finalize: function () {
                cursor.remove();
                els.wrapper.classList.add('finalized');
            },
            markError: function (msg) {
                els.wrapper.classList.add('error-message');
                cursor.remove();
                textNode.textContent = msg || 'Something went wrong. Please try again.';
                scrollToBottom();
            }
        };
    }

    // ---- Profile card builder ----
    function addProfileCard(assistantMsg, resultJson) {
        var profile;
        try {
            profile = JSON.parse(resultJson);
        } catch (e) {
            return;
        }
        if (!profile || typeof profile !== 'object' || !profile.name) {
            return;
        }

        var card = document.createElement('div');
        card.className = 'profile-card';

        var img = document.createElement('img');
        img.className = 'profile-card-photo';
        img.alt = profile.name;
        img.src = (profile.photo_url || '') + '?name=' + encodeURIComponent(profile.name);

        var info = document.createElement('div');
        info.className = 'profile-card-info';

        var nameEl = document.createElement('div');
        nameEl.className = 'profile-card-name';
        nameEl.textContent = profile.name;
        info.appendChild(nameEl);

        if (profile.jobTitle) {
            var titleEl = document.createElement('div');
            titleEl.className = 'profile-card-field';
            titleEl.textContent = profile.jobTitle;
            info.appendChild(titleEl);
        }

        if (profile.department) {
            var deptEl = document.createElement('div');
            deptEl.className = 'profile-card-field profile-card-dept';
            deptEl.textContent = profile.department;
            info.appendChild(deptEl);
        }

        if (profile.email) {
            var emailEl = document.createElement('a');
            emailEl.className = 'profile-card-email';
            emailEl.href = 'mailto:' + profile.email;
            emailEl.textContent = profile.email;
            info.appendChild(emailEl);
        }

        card.appendChild(img);
        card.appendChild(info);
        assistantMsg.insertCard(card);
    }

    // ---- Search result cards builder ----
    function addSearchCards(assistantMsg, resultJson) {
        var data;
        try {
            if (typeof resultJson === 'object') {
                data = resultJson;
            } else {
                data = JSON.parse(resultJson);
            }
        } catch (e) {
            console.warn('addSearchCards: parse failed', e, resultJson);
            return false;
        }
        if (!data || !Array.isArray(data.results) || data.results.length === 0) {
            console.warn('addSearchCards: no results array', data);
            return false;
        }

        var container = document.createElement('div');
        container.className = 'search-results';

        data.results.forEach(function (item) {
            if (!item.name) return;

            var card = document.createElement('div');
            card.className = 'search-result-card';

            var nameEl = document.createElement('span');
            nameEl.className = 'search-result-name';
            nameEl.textContent = item.name;
            card.appendChild(nameEl);

            if (item.jobTitle) {
                var sep1 = document.createElement('span');
                sep1.className = 'search-result-sep';
                sep1.textContent = '\u00B7';
                card.appendChild(sep1);

                var titleEl = document.createElement('span');
                titleEl.className = 'search-result-title';
                titleEl.textContent = item.jobTitle;
                card.appendChild(titleEl);
            }

            if (item.department) {
                var sep2 = document.createElement('span');
                sep2.className = 'search-result-sep';
                sep2.textContent = '\u00B7';
                card.appendChild(sep2);

                var deptEl = document.createElement('span');
                deptEl.className = 'search-result-dept';
                deptEl.textContent = item.department;
                card.appendChild(deptEl);
            }

            if (item.email) {
                var emailRow = document.createElement('div');
                emailRow.className = 'search-result-email-row';
                var emailEl = document.createElement('a');
                emailEl.className = 'search-result-email';
                emailEl.href = 'mailto:' + item.email;
                emailEl.textContent = item.email;
                emailRow.appendChild(emailEl);
                card.appendChild(emailRow);
            }

            container.appendChild(card);
        });

        assistantMsg.insertCard(container);
        return true;
    }

    // ---- Welcome message ----
    function showWelcomeMessage() {
        var msgEl = document.createElement('div');
        msgEl.className = 'message assistant-message';
        msgEl.id = 'welcome-message';
        var content = document.createElement('div');
        content.className = 'message-content';
        content.innerHTML = (
            '<p>Hello! I&rsquo;m <strong>Atlas</strong>, MMC&rsquo;s Exchange infrastructure assistant.</p>' +
            '<p>I can help you query live Exchange data. Try one of these:</p>' +
            '<div class="example-queries">' +
            '<button class="example-query" data-query="Check mailbox size for a specific user">Check mailbox size for a specific user</button>' +
            '<button class="example-query" data-query="Show DAG health and replication status">Show DAG health and replication status</button>' +
            '<button class="example-query" data-query="Check mail flow routing for an address">Check mail flow routing for an address</button>' +
            '<button class="example-query" data-query="Show hybrid connector status">Show hybrid connector status</button>' +
            '</div>'
        );
        msgEl.appendChild(content);
        messagesEl.appendChild(msgEl);
        scrollToBottom();
    }

    // ---- SSE stream reader (fetch-based — POST body needed) ----
    function readSSEStream(response, assistantMsg, signal) {
        var reader = response.body.getReader();
        var decoder = new TextDecoder('utf-8');
        var buffer = '';
        var activeChip = null;

        function processLine(line) {
            if (!line.startsWith('data: ')) return;
            var jsonStr = line.slice(6).trim();
            if (!jsonStr) return;

            var event;
            try {
                event = JSON.parse(jsonStr);
            } catch (e) {
                return; // Malformed line — skip
            }

            if (event.type === 'tool') {
                // Mark previous panel done before showing next
                assistantMsg.removeDots();
                if (activeChip) {
                    assistantMsg.markToolDone(activeChip);
                }
                if (event.name === 'get_colleague_profile' && event.status === 'success') {
                    addProfileCard(assistantMsg, event.result || '');
                    activeChip = null;
                } else if (event.name === 'search_colleagues' && event.status === 'success') {
                    addSearchCards(assistantMsg, event.result || '');
                    activeChip = null;
                } else {
                    activeChip = assistantMsg.addToolPanel(
                        event.name,
                        event.params || {},
                        event.result || null,
                        event.status || 'success'
                    );
                }
            } else if (event.type === 'text') {
                // Once text starts arriving, mark last tool chip done
                assistantMsg.removeDots();
                if (activeChip) {
                    assistantMsg.markToolDone(activeChip);
                    activeChip = null;
                }
                assistantMsg.appendText(event.delta || '');
            } else if (event.type === 'thread_named') {
                // Auto-naming: update sidebar thread name in real-time
                if (event.thread_id && event.name) {
                    var items = threadListEl ? threadListEl.querySelectorAll('.thread-item') : [];
                    for (var i = 0; i < items.length; i++) {
                        if (parseInt(items[i].dataset.id) === event.thread_id) {
                            var nameSpan = items[i].querySelector('.thread-name');
                            if (nameSpan && document.activeElement !== nameSpan) {
                                nameSpan.textContent = event.name;
                                nameSpan.dataset.originalName = event.name;
                            }
                            break;
                        }
                    }
                }
            } else if (event.type === 'done') {
                if (activeChip) {
                    assistantMsg.markToolDone(activeChip);
                    activeChip = null;
                }
                assistantMsg.removeDots();
                assistantMsg.finalize();
                setStreaming(false);
                currentAbortController = null;
                // Re-fetch thread list to update sidebar ordering (updated_at changed)
                fetchThreads();
            } else if (event.type === 'error') {
                assistantMsg.removeDots();
                assistantMsg.markError(event.message || null);
                setStreaming(false);
                currentAbortController = null;
            }
        }

        function pump() {
            if (signal && signal.aborted) {
                assistantMsg.removeDots();
                assistantMsg.markInterrupted();
                setStreaming(false);
                return;
            }
            return reader.read().then(function (result) {
                if (result.done) {
                    // Flush any remaining buffer
                    if (buffer.trim()) {
                        buffer.split('\n').forEach(processLine);
                    }
                    assistantMsg.removeDots();
                    assistantMsg.finalize();
                    setStreaming(false);
                    return;
                }

                buffer += decoder.decode(result.value, { stream: true });

                // SSE events are delimited by double newlines
                var parts = buffer.split('\n\n');
                buffer = parts.pop(); // Last incomplete part stays in buffer

                parts.forEach(function (block) {
                    block.split('\n').forEach(processLine);
                });

                return pump();
            });
        }

        pump().catch(function (err) {
            assistantMsg.removeDots();
            if (err.name === 'AbortError') {
                assistantMsg.markInterrupted();
            } else {
                console.error('[Atlas] Stream read error:', err);
                assistantMsg.markError('Connection interrupted. Please try again.');
            }
            setStreaming(false);
            currentAbortController = null;
        });
    }

    // ---- Streaming state ----
    function setStreaming(val) {
        isStreaming = val;
        sendBtn.disabled = val;
        sendBtn.textContent = val ? 'Sending\u2026' : 'Send';
    }

    // ---- Send message ----
    function sendMessage(text) {
        if (!text || isStreaming) return;

        if (!currentThreadId) {
            // No active thread — create one first, then send
            fetch('/api/threads', { method: 'POST' })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    currentThreadId = data.id;
                    fetchThreads();
                    doSend(text);
                })
                .catch(function (err) {
                    console.error('[Atlas] Failed to create thread before send:', err);
                });
            return;
        }

        doSend(text);
    }

    function doSend(text) {
        setStreaming(true);
        appendUserMessage(text);
        var assistantMsg = createAssistantMessage();

        currentAbortController = new AbortController();
        var signal = currentAbortController.signal;

        fetch('/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, thread_id: currentThreadId }),
            signal: signal
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }
                readSSEStream(response, assistantMsg, signal);
            })
            .catch(function (err) {
                assistantMsg.removeDots();
                if (err.name === 'AbortError') {
                    assistantMsg.markInterrupted();
                } else {
                    console.error('[Atlas] Fetch error:', err);
                    assistantMsg.markError(
                        err.message === 'HTTP 401'
                            ? 'Your session has expired. Please sign in again.'
                            : 'Could not reach the server. Please check your connection.'
                    );
                }
                setStreaming(false);
                currentAbortController = null;
            });
    }

    // ---- Sidebar: fetch and render thread list ----
    function fetchThreads() {
        if (!threadListEl) return;
        fetch('/api/threads')
            .then(function (r) { return r.json(); })
            .then(renderThreadList)
            .catch(function (err) {
                console.error('[Atlas] Failed to fetch threads:', err);
            });
    }

    function renderThreadList(threads) {
        if (!threadListEl) return;
        threadListEl.innerHTML = '';
        threads.forEach(function (thread) {
            var li = document.createElement('li');
            li.className = 'thread-item';
            li.dataset.id = thread.id;
            if (thread.id === currentThreadId) {
                li.classList.add('active');
            }

            var nameSpan = document.createElement('span');
            nameSpan.className = 'thread-name';
            nameSpan.contentEditable = 'true';
            nameSpan.textContent = thread.name || 'New chat';
            nameSpan.dataset.originalName = thread.name || '';
            nameSpan.title = thread.name || 'New chat';

            var delBtn = document.createElement('button');
            delBtn.className = 'thread-delete';
            delBtn.type = 'button';
            delBtn.title = 'Delete conversation';
            delBtn.textContent = '\u00d7'; // multiplication sign ×

            // Wire click on li — but not when clicking the name span in edit mode or the delete btn
            li.addEventListener('click', function (e) {
                if (e.target === nameSpan && document.activeElement === nameSpan) return;
                if (e.target === delBtn) return;
                switchThread(thread.id);
            });

            // Wire delete button
            delBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                deleteThread(thread.id);
            });

            // Wire inline rename
            makeRenameHandler(thread.id, nameSpan);

            li.appendChild(nameSpan);
            li.appendChild(delBtn);
            threadListEl.appendChild(li);
        });
    }

    // ---- Sidebar: switch to thread ----
    function switchThread(threadId) {
        if (threadId === currentThreadId) return;
        currentThreadId = threadId;

        // Update active indicator immediately
        if (threadListEl) {
            var items = threadListEl.querySelectorAll('.thread-item');
            items.forEach(function (item) {
                item.classList.toggle('active', parseInt(item.dataset.id) === threadId);
            });
        }

        // Load message history
        fetch('/api/threads/' + threadId + '/messages')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                messagesEl.innerHTML = '';
                var messages = data.messages || [];
                var visibleMessages = messages.filter(function (m) { return m.role !== 'system'; });

                if (visibleMessages.length === 0) {
                    showWelcomeMessage();
                } else {
                    visibleMessages.forEach(function (msg) {
                        if (msg.role === 'user') {
                            appendUserMessage(msg.content);
                        } else if (msg.role === 'assistant' && msg.content) {
                            var els = createMessageEl('assistant');
                            var p = document.createElement('p');
                            p.textContent = msg.content;
                            els.content.appendChild(p);
                            messagesEl.appendChild(els.wrapper);
                        }
                    });
                }
                scrollToBottom();
            })
            .catch(function (err) {
                console.error('[Atlas] Failed to load thread messages:', err);
            });
    }

    // ---- Sidebar: create new thread ----
    function createNewThread() {
        fetch('/api/threads', { method: 'POST' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                currentThreadId = data.id;
                fetchThreads();
                messagesEl.innerHTML = '';
                showWelcomeMessage();
                inputEl.focus();
            })
            .catch(function (err) {
                console.error('[Atlas] Failed to create new thread:', err);
            });
    }

    // ---- Sidebar: delete thread ----
    function deleteThread(threadId) {
        if (!window.confirm('Delete this conversation? This cannot be undone.')) return;

        fetch('/api/threads/' + threadId, { method: 'DELETE' })
            .then(function () {
                if (threadId === currentThreadId) {
                    currentThreadId = null;
                }
                return fetch('/api/threads').then(function (r) { return r.json(); });
            })
            .then(function (threads) {
                renderThreadList(threads);
                if (threads.length > 0 && !currentThreadId) {
                    switchThread(threads[0].id);
                } else if (threads.length === 0) {
                    createNewThread();
                }
            })
            .catch(function (err) {
                console.error('[Atlas] Failed to delete thread:', err);
            });
    }

    // ---- Sidebar: inline rename handler ----
    function makeRenameHandler(threadId, nameEl) {
        nameEl.addEventListener('focus', function () {
            // Select all text for easy replacement
            var range = document.createRange();
            range.selectNodeContents(nameEl);
            var sel = window.getSelection();
            if (sel) {
                sel.removeAllRanges();
                sel.addRange(range);
            }
        });

        nameEl.addEventListener('blur', function () {
            var newName = nameEl.textContent.trim();
            var original = nameEl.dataset.originalName;
            if (newName === original || !newName) {
                // Restore original if blank or unchanged
                nameEl.textContent = original || 'New chat';
                return;
            }
            // Send PATCH to rename
            fetch('/api/threads/' + threadId, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName })
            })
                .then(function (r) {
                    if (r.ok) {
                        nameEl.dataset.originalName = newName;
                        nameEl.title = newName;
                    } else {
                        nameEl.textContent = original || 'New chat';
                    }
                })
                .catch(function () {
                    nameEl.textContent = original || 'New chat';
                });
        });

        nameEl.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                nameEl.blur();
            } else if (e.key === 'Escape') {
                nameEl.textContent = nameEl.dataset.originalName || 'New chat';
                nameEl.blur();
            }
        });
    }

    // ---- Form submit handler ----
    formEl.addEventListener('submit', function (e) {
        e.preventDefault();
        var text = inputEl.value.trim();
        if (!text) return;
        inputEl.value = '';
        resetInputSize();
        sendMessage(text);
    });

    // ---- Keyboard shortcut: Ctrl+Enter to send ----
    inputEl.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            var text = inputEl.value.trim();
            if (!text) return;
            inputEl.value = '';
            resetInputSize();
            sendMessage(text);
        }
    });

    // ---- Keyboard shortcut: Escape to cancel streaming ----
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && isStreaming && currentAbortController) {
            currentAbortController.abort();
            currentAbortController = null;
        }
    });

    // ---- Example query buttons (delegated) ----
    messagesEl.addEventListener('click', function (e) {
        var btn = e.target.closest('.example-query');
        if (!btn) return;
        var query = btn.getAttribute('data-query');
        if (!query) return;
        // Auto-submit the example query
        inputEl.value = '';
        resetInputSize();
        sendMessage(query);
    });

    // ---- New Chat button ----
    if (newChatBtn) {
        newChatBtn.addEventListener('click', createNewThread);
    }

    // ---- Initial load ----
    (function initLoad() {
        var layoutEl = document.querySelector('.app-layout');
        var rawLastId = layoutEl ? layoutEl.dataset.lastThreadId : '';
        var lastThreadId = rawLastId ? parseInt(rawLastId, 10) : null;

        fetch('/api/threads')
            .then(function (r) { return r.json(); })
            .then(function (threads) {
                if (threads.length > 0) {
                    renderThreadList(threads);
                    // Prefer last_thread_id if it still exists in the list
                    var preferredId = null;
                    if (lastThreadId) {
                        for (var i = 0; i < threads.length; i++) {
                            if (threads[i].id === lastThreadId) {
                                preferredId = lastThreadId;
                                break;
                            }
                        }
                    }
                    switchThread(preferredId !== null ? preferredId : threads[0].id);
                } else {
                    createNewThread();
                }
            })
            .catch(function (err) {
                console.error('[Atlas] Failed to load threads on init:', err);
                // Fall through: welcome screen already shows from Jinja template
                scrollToBottom();
            });
    })();

})();
