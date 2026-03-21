/**
 * Atlas Chat — Client-side chat logic
 * Handles: SSE streaming from fetch ReadableStream, auto-expanding textarea,
 * example query buttons, keyboard shortcuts, tool chip rendering.
 */
(function () {
    'use strict';

    // ---- DOM references ----
    var messagesEl = document.getElementById('chat-messages');
    var inputEl = document.getElementById('chat-input');
    var formEl = document.getElementById('chat-form');
    var sendBtn = document.getElementById('send-btn');

    if (!messagesEl || !inputEl || !formEl || !sendBtn) {
        // Not on the chat page — silently exit
        return;
    }

    var isStreaming = false;

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
        messagesEl.appendChild(els.wrapper);
        scrollToBottom();

        return {
            appendText: function (chunk) {
                textNode.textContent += chunk;
                scrollToBottom();
            },
            addToolChip: function (toolName) {
                var chip = document.createElement('div');
                chip.className = 'tool-chip';
                chip.setAttribute('data-tool', toolName);
                chip.textContent = 'Querying ' + toolName + '\u2026';
                els.content.insertBefore(chip, textNode);
                scrollToBottom();
                return chip;
            },
            markToolDone: function (chip) {
                if (chip) {
                    chip.classList.add('done');
                }
            },
            finalize: function () {
                cursor.remove();
            },
            markError: function (msg) {
                els.wrapper.classList.add('error-message');
                cursor.remove();
                textNode.textContent = msg || 'Something went wrong. Please try again.';
                scrollToBottom();
            }
        };
    }

    // ---- SSE stream reader (fetch-based — POST body needed) ----
    function readSSEStream(response, assistantMsg) {
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
                // Mark previous chip done before showing next
                if (activeChip) {
                    assistantMsg.markToolDone(activeChip);
                }
                activeChip = assistantMsg.addToolChip(event.name);
            } else if (event.type === 'text') {
                // Once text starts arriving, mark last tool chip done
                if (activeChip) {
                    assistantMsg.markToolDone(activeChip);
                    activeChip = null;
                }
                assistantMsg.appendText(event.delta || '');
            } else if (event.type === 'done') {
                if (activeChip) {
                    assistantMsg.markToolDone(activeChip);
                    activeChip = null;
                }
                assistantMsg.finalize();
                setStreaming(false);
            } else if (event.type === 'error') {
                assistantMsg.markError(event.message || null);
                setStreaming(false);
            }
        }

        function pump() {
            return reader.read().then(function (result) {
                if (result.done) {
                    // Flush any remaining buffer
                    if (buffer.trim()) {
                        buffer.split('\n').forEach(processLine);
                    }
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
            console.error('[Atlas] Stream read error:', err);
            assistantMsg.markError('Connection interrupted. Please try again.');
            setStreaming(false);
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

        setStreaming(true);
        appendUserMessage(text);
        var assistantMsg = createAssistantMessage();

        fetch('/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }
                readSSEStream(response, assistantMsg);
            })
            .catch(function (err) {
                console.error('[Atlas] Fetch error:', err);
                assistantMsg.markError(
                    err.message === 'HTTP 401'
                        ? 'Your session has expired. Please sign in again.'
                        : 'Could not reach the server. Please check your connection.'
                );
                setStreaming(false);
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

    // ---- Example query buttons ----
    messagesEl.addEventListener('click', function (e) {
        var btn = e.target.closest('.example-query');
        if (!btn) return;
        var query = btn.getAttribute('data-query');
        if (!query) return;
        inputEl.value = query;
        resizeInput();
        inputEl.focus();
        // Auto-submit the example query
        inputEl.value = '';
        resetInputSize();
        sendMessage(query);
    });

    // ---- Initial scroll ----
    scrollToBottom();
})();
