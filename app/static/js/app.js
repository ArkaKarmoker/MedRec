$(document).ready(function() {
    // ==============================
    // === STATE ===
    // ==============================
    let currentSessionId = null;
    const STORAGE_KEY = 'medrec_active_session';

    function saveActiveSession(id) {
        if (id) {
            localStorage.setItem(STORAGE_KEY, id);
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    }

    function getSavedSession() {
        return localStorage.getItem(STORAGE_KEY);
    }
    let dualEnabled = $('#dualResponseToggle').is(':checked');
    const userInitial = $('.sidebar .user-profile .user-avatar').first().text().trim() || 'U';

    // Welcome message HTML (shown for new/empty chats)
    const welcomeHTML = `
        <div class="message bot-message" id="welcome-message">
            <div class="avatar bot-avatar">M</div>
            <div class="message-content-wrapper">
                <div class="message-bubble bot-bubble">
                    Hey there! I'm MedRec, your AI-powered medicine recommendation chatbot. I can help with indications, side effects, dosages, generic names, and more based on our dataset. Ask away or try an example below!
                </div>
                <div class="message-footer">
                    <div class="response-nav" style="display: none;">
                        <button class="nav-btn prev-response" disabled data-bs-toggle="tooltip" data-bs-placement="top" title="Previous response">&lt;</button>
                        <span class="response-counter">1/1</span>
                        <button class="nav-btn next-response" disabled data-bs-toggle="tooltip" data-bs-placement="top" title="Next response">&gt;</button>
                    </div>
                    <div class="message-actions">
                        <button class="action-btn copy" data-bs-toggle="tooltip" data-bs-placement="top" title="Copy response"><i class="bi bi-copy"></i></button>
                        <button class="action-btn thumbs-up" data-bs-toggle="tooltip" data-bs-placement="top" title="Good response"><i class="bi bi-hand-thumbs-up"></i></button>
                        <button class="action-btn thumbs-down" data-bs-toggle="tooltip" data-bs-placement="top" title="Bad response"><i class="bi bi-hand-thumbs-down"></i></button>
                        <button class="action-btn regenerate" disabled style="cursor: not-allowed;" data-bs-toggle="tooltip" data-bs-placement="top" title="Regenerate response"><i class="bi bi-arrow-counterclockwise"></i></button>
                    </div>
                    <span class="model-name ms-auto">Auto</span>
                </div>
            </div>
        </div>
        <div class="examples-container">
            <button class="example-btn" data-query="What is the generic name of Sergel?">Generic name of Sergel?</button>
            <button class="example-btn" data-query="What are the indications for 3 Bion 100 mg Tablet?">Indications for 3 Bion 100 mg?</button>
            <button class="example-btn" data-query="Side effects of 3-C 200 mg Capsule?">Side effects of 3-C 200 mg?</button>
            <button class="example-btn" data-query="Generic name of 3 Bion?">Generic name of 3 Bion?</button>
            <button class="example-btn" data-query="Dosage for Cefixime Trihydrate?">Dosage for Cefixime?</button>
            <button class="example-btn" data-query="What are common drug interactions for Aspirin?">Drug interactions for Aspirin?</button>
            <button class="example-btn" data-query="Side effects of Paracetamol?">Side effects of Paracetamol?</button>
        </div>
    `;

    // ==============================
    // === UTILITIES ===
    // ==============================
    function scrollToBottom() {
        const chatHistory = $('#chat-history');
        chatHistory.scrollTop(chatHistory[0].scrollHeight);
    }

    function showToast(message, type) {
        type = type || 'success';
        const bgColor = type === 'success' ? 'var(--accent)' : type === 'error' ? '#f56c6c' : 'var(--bg-secondary)';
        const toast = $('<div class="medrec-toast"></div>')
            .text(message)
            .css({
                position: 'fixed',
                bottom: '24px',
                right: '24px',
                zIndex: 99999,
                padding: '12px 24px',
                borderRadius: '12px',
                background: bgColor,
                color: '#fff',
                fontSize: '0.9rem',
                boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
                maxWidth: '400px',
                animation: 'toastSlideIn 0.3s ease'
            });
        $('body').append(toast);
        setTimeout(function() { toast.fadeOut(300, function() { toast.remove(); }); }, 3000);
    }

    function formatModelName(model) {
        if (!model) return 'Unknown Model';
        return model.replace(/-/g, ' ').split(' ').map(function(word) {
            return word.charAt(0).toUpperCase() + word.slice(1);
        }).join(' ');
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ==============================
    // === MESSAGE RENDERING ===
    // ==============================
    function updateBotMessageView($botMessage) {
        var responses = $botMessage.data('responses') || [];
        var models = $botMessage.data('models') || [];
        var currentIndex = $botMessage.data('currentIndex') || 0;
        var total = responses.length;
        if (currentIndex < 0) currentIndex = 0;
        if (currentIndex >= total) currentIndex = total - 1;
        $botMessage.data('currentIndex', currentIndex);
        if (total > 0) {
            var $bubble = $botMessage.find('.message-bubble');
            $bubble.html(responses[currentIndex]);
            $bubble.find('pre code').each(function(i, block) {
                hljs.highlightElement(block);
            });
            var $modelNameSpan = $botMessage.find('.model-name');
            $modelNameSpan.text(models[currentIndex] || 'Unknown Model');
        }
        var $nav = $botMessage.find('.response-nav');
        $nav.find('.response-counter').text((currentIndex + 1) + '/' + total);
        $nav.find('.prev-response').prop('disabled', currentIndex === 0);
        $nav.find('.next-response').prop('disabled', currentIndex >= total - 1);
        $nav.toggle(total > 1);
    }

    function appendMessage(sender, text, userQuery, modelName) {
        userQuery = userQuery || null;
        modelName = modelName || '';
        var parsedText;
        if (sender === 'bot') {
            parsedText = marked.parse(text);
        } else {
            parsedText = escapeHtml(text);
        }
        var alignClass = sender === 'user' ? 'user-message' : 'bot-message';
        var bubbleClass = sender === 'user' ? 'user-bubble' : 'bot-bubble';
        var avatarClass = sender === 'user' ? 'user-avatar' : 'bot-avatar';
        var avatarText = sender === 'user' ? userInitial : 'M';
        var avatarPosition = sender === 'user' ? 'after' : 'before';
        var msgHtml = '<div class="message ' + alignClass + '">';
        if (avatarPosition === 'before') {
            msgHtml += '<div class="avatar ' + avatarClass + '">' + avatarText + '</div>';
        }
        msgHtml += '<div class="message-content-wrapper">';
        msgHtml += '<div class="message-bubble ' + bubbleClass + '">' + parsedText + '</div>';
        if (sender === 'bot') {
            msgHtml += '<div class="message-footer">' +
                '<div class="response-nav" style="display: none;">' +
                    '<button class="nav-btn prev-response" disabled data-bs-toggle="tooltip" data-bs-placement="top" title="Previous response">&lt;</button>' +
                    '<span class="response-counter">1/1</span>' +
                    '<button class="nav-btn next-response" disabled data-bs-toggle="tooltip" data-bs-placement="top" title="Next response">&gt;</button>' +
                '</div>' +
                '<div class="message-actions">' +
                    '<button class="action-btn copy" data-bs-toggle="tooltip" data-bs-placement="top" title="Copy response"><i class="bi bi-copy"></i></button>' +
                    '<button class="action-btn thumbs-up" data-bs-toggle="tooltip" data-bs-placement="top" title="Good response"><i class="bi bi-hand-thumbs-up"></i></button>' +
                    '<button class="action-btn thumbs-down" data-bs-toggle="tooltip" data-bs-placement="top" title="Bad response"><i class="bi bi-hand-thumbs-down"></i></button>' +
                    '<button class="action-btn regenerate" data-bs-toggle="tooltip" data-bs-placement="top" title="Regenerate response"><i class="bi bi-arrow-counterclockwise"></i></button>' +
                '</div>' +
                '<span class="model-name ms-auto">' + escapeHtml(modelName) + '</span>' +
            '</div>';
        }
        if (sender === 'user') {
            msgHtml += '<div class="message-footer">' +
                '<div class="message-actions">' +
                    '<button class="action-btn copy" data-bs-toggle="tooltip" data-bs-placement="top" title="Copy question"><i class="bi bi-copy"></i></button>' +
                '</div>' +
            '</div>';
        }
        msgHtml += '</div>'; // Close wrapper
        if (avatarPosition === 'after') {
            msgHtml += '<div class="avatar ' + avatarClass + '">' + avatarText + '</div>';
        }
        msgHtml += '</div>';
        var $msg = $(msgHtml);
        if (sender === 'bot') {
            $msg.data('responses', [parsedText]);
            $msg.data('models', [modelName]);
            $msg.data('currentIndex', 0);
            $msg.data('userQuery', userQuery);
        }
        $('#chat-history').append($msg);
        $msg.find('pre code').each(function(i, block) {
            hljs.highlightElement(block);
        });
        $msg.find('[data-bs-toggle="tooltip"]').each(function () {
            new bootstrap.Tooltip(this);
        });
        scrollToBottom();
    }

    function showLoading() {
        var loadingHtml =
            '<div class="message bot-message loading" id="loading-indicator">' +
                '<div class="avatar bot-avatar">M</div>' +
                '<div class="message-bubble bot-bubble">Thinking...</div>' +
            '</div>';
        $('#chat-history').append(loadingHtml);
        scrollToBottom();
    }

    function removeLoading() {
        $('#loading-indicator').remove();
    }

    function showWelcomeScreen() {
        $('#chat-history').html(welcomeHTML);
        $('#chat-header-title').text('New Chat');
        // Initialize tooltips in welcome screen
        $('#chat-history [data-bs-toggle="tooltip"]').each(function () {
            new bootstrap.Tooltip(this);
        });
        scrollToBottom();
    }

    // ==============================
    // === SIDEBAR RENDERING ===
    // ==============================
    function createChatItemHTML(session) {
        var pinIcon = session.is_pinned ? '<i class="bi bi-pin-fill me-1" style="font-size:0.7rem;color:var(--accent)"></i>' : '';
        var pinText = session.is_pinned ? 'Unpin' : 'Pin';
        var pinIconClass = session.is_pinned ? 'bi-pin-fill' : 'bi-pin-angle';
        var activeClass = (session.id == currentSessionId) ? ' active' : '';
        return '<div class="chat-item' + activeClass + '" data-session-id="' + session.id + '">' +
            '<div class="chat-text">' + pinIcon + '<i class="bi bi-chat-left-dots"></i>' + escapeHtml(session.title) + '</div>' +
            '<div class="dropdown chat-options">' +
                '<i class="bi bi-three-dots-vertical chat-options-btn" data-bs-toggle="dropdown" aria-expanded="false"></i>' +
                '<ul class="dropdown-menu dropdown-menu-custom">' +
                    '<li><a class="dropdown-item chat-action-rename" href="#" data-session-id="' + session.id + '"><i class="bi bi-pencil"></i> Rename</a></li>' +
                    '<li><a class="dropdown-item chat-action-pin" href="#" data-session-id="' + session.id + '"><i class="bi ' + pinIconClass + '"></i> ' + pinText + '</a></li>' +
                    '<li><a class="dropdown-item chat-action-share" href="#" data-session-id="' + session.id + '"><i class="bi bi-share"></i> Share</a></li>' +
                    '<li><hr class="dropdown-divider"></li>' +
                    '<li><a class="dropdown-item text-danger chat-action-delete" href="#" data-session-id="' + session.id + '"><i class="bi bi-trash"></i> Delete</a></li>' +
                '</ul>' +
            '</div>' +
        '</div>';
    }

    function renderSidebar(sessions) {
        var $chatList = $('#chat-list');
        $chatList.empty();
        var pinned = sessions.filter(function(s) { return s.is_pinned; });
        var regular = sessions.filter(function(s) { return !s.is_pinned; });

        if (pinned.length > 0) {
            $chatList.append('<div class="sidebar-section-label">Pinned</div>');
            pinned.forEach(function(s) { $chatList.append(createChatItemHTML(s)); });
        }
        if (regular.length > 0) {
            if (pinned.length > 0) {
                $chatList.append('<div class="sidebar-section-label">Recent</div>');
            }
            regular.forEach(function(s) { $chatList.append(createChatItemHTML(s)); });
        }
    }

    function refreshSidebar() {
        $.ajax({
            url: '/api/sessions/',
            type: 'GET',
            success: function(data) {
                renderSidebar(data.sessions || []);
            }
        });
    }

    function loadSessions() {
        $.ajax({
            url: '/api/sessions/',
            type: 'GET',
            success: function(data) {
                var sessions = data.sessions || [];
                renderSidebar(sessions);
                if (sessions.length === 0) {
                    currentSessionId = null;
                    saveActiveSession(null);
                    showWelcomeScreen();
                    history.replaceState(null, '', '/app/');
                    return;
                }
                
                // URL parsing
                var pathParts = window.location.pathname.split('/');
                var urlSessionId = null;
                if (pathParts.length >= 3 && pathParts[1] === 'app' && pathParts[2]) {
                    urlSessionId = pathParts[2];
                }

                if (urlSessionId) {
                    var foundUrl = sessions.some(function(s) { return String(s.id) === String(urlSessionId); });
                    if (foundUrl) {
                        loadSession(urlSessionId);
                        return;
                    }
                }

                var savedId = getSavedSession();
                // 'new_chat' means user was on the new-chat welcome screen
                if (savedId === 'new_chat') {
                    currentSessionId = null;
                    showWelcomeScreen();
                    history.replaceState(null, '', '/app/');
                    return;
                }
                // Check if saved session still exists
                var found = savedId && sessions.some(function(s) { return String(s.id) === String(savedId); });
                if (found) {
                    loadSession(savedId);
                } else {
                    // Fallback to most recent
                    loadSession(sessions[0].id);
                }
            },
            error: function() {
                showToast('Failed to load chat history', 'error');
                showWelcomeScreen();
            }
        });
    }

    function loadSession(sessionId) {
        currentSessionId = sessionId;
        saveActiveSession(sessionId);
        history.pushState(null, '', '/app/' + sessionId + '/');
        // Update active state in sidebar
        $('.chat-item').removeClass('active');
        $('.chat-item[data-session-id="' + sessionId + '"]').addClass('active');

        $.ajax({
            url: '/api/sessions/' + sessionId + '/',
            type: 'GET',
            success: function(data) {
                var messages = data.messages || [];
                $('#chat-header-title').text(data.title || 'New Chat');
                if (messages.length === 0) {
                    showWelcomeScreen();
                } else {
                    $('#chat-history').empty();
                    messages.forEach(function(msg) {
                        var modelName = msg.model_name ? formatModelName(msg.model_name) : '';
                        appendMessage(msg.role === 'user' ? 'user' : 'bot', msg.content, null, modelName);
                    });
                }
            },
            error: function() {
                showToast('Failed to load chat', 'error');
                showWelcomeScreen();
            }
        });
    }

    // ==============================
    // === SEND MESSAGE ===
    // ==============================
    function sendMessage(userQuery) {
        if (!userQuery.trim()) return;

        // Remove examples container and welcome message if visible
        $('.examples-container').remove();
        $('#welcome-message').remove();

        appendMessage('user', userQuery);
        showLoading();

        var selectedModel = $('#modelDropdown').data('selected-model') || 'auto';

        function doSend(sessionId) {
            $.ajax({
                url: '/api/chat/',
                type: 'POST',
                data: JSON.stringify({
                    query: userQuery,
                    model: selectedModel,
                    dual_response: dualEnabled,
                    session_id: sessionId
                }),
                contentType: 'application/json',
                success: function(data) {
                    setTimeout(function() {
                        removeLoading();
                        var modelName = data.model ? formatModelName(data.model) : 'Unknown Model';
                        appendMessage('bot', data.response, userQuery, modelName);
                        // Update sidebar title if auto-titled
                        if (data.title && sessionId) {
                            var $item = $('.chat-item[data-session-id="' + sessionId + '"]');
                            var hasPinIcon = $item.find('.bi-pin-fill').length > 0;
                            var pinHtml = hasPinIcon ? '<i class="bi bi-pin-fill me-1" style="font-size:0.7rem;color:var(--accent)"></i>' : '';
                            $item.find('.chat-text').html(pinHtml + '<i class="bi bi-chat-left-dots"></i>' + escapeHtml(data.title));
                            $('#chat-header-title').text(data.title);
                        }
                    }, 800);
                },
                error: function(xhr) {
                    setTimeout(function() {
                        removeLoading();
                        var errorMsg = (xhr.responseJSON && xhr.responseJSON.error) ? xhr.responseJSON.error : 'Sorry, something went wrong.';
                        appendMessage('bot', errorMsg, userQuery);
                    }, 800);
                }
            });
        }

        if (!currentSessionId) {
            // Create session first, then send
            $.ajax({
                url: '/api/sessions/create/',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({}),
                success: function(data) {
                    currentSessionId = data.id;
                    saveActiveSession(data.id);
                    history.pushState(null, '', '/app/' + data.id + '/');
                    refreshSidebar();
                    doSend(data.id);
                },
                error: function() {
                    removeLoading();
                    showToast('Failed to create chat session', 'error');
                }
            });
        } else {
            doSend(currentSessionId);
        }
    }

    // ==============================
    // === EVENT HANDLERS ===
    // ==============================

    // Auto-resize textarea
    $('#user-input').on('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // Send button click
    $('#send-btn').click(function() {
        var userQuery = $('#user-input').val().trim();
        if (!userQuery) return;
        $('#user-input').val('');
        $('#user-input').css('height', 'auto');
        sendMessage(userQuery);
    });

    // Enter key press
    $('#user-input').keypress(function(e) {
        if (e.which === 13 && !e.shiftKey) {
            e.preventDefault();
            $('#send-btn').click();
        }
    });

    // New Chat button
    $('.new-chat-btn').click(function() {
        currentSessionId = null;
        saveActiveSession('new_chat');
        $('.chat-item').removeClass('active');
        $('#chat-header-title').text('New Chat');
        showWelcomeScreen();
        history.pushState(null, '', '/app/');
    });

    // Example buttons
    $(document).on('click', '.example-btn', function() {
        var query = $(this).data('query');
        $('#user-input').val(query);
        $('#send-btn').click();
    });

    // Chat item click → load session
    $(document).on('click', '.chat-item', function(e) {
        if ($(e.target).closest('.chat-options').length) return;
        if ($(e.target).is('.rename-input')) return;
        var sessionId = $(this).data('session-id');
        if (sessionId && sessionId !== currentSessionId) {
            loadSession(sessionId);
        }
    });

    // Prevent dropdown clicks from bubbling to chat item
    $(document).on('click', '.chat-options', function(e) {
        e.stopPropagation();
    });

    // ==============================
    // === RENAME ===
    // ==============================
    $(document).on('click', '.chat-action-rename', function(e) {
        e.preventDefault();
        e.stopPropagation();
        var sessionId = $(this).data('session-id');
        var $chatItem = $('.chat-item[data-session-id="' + sessionId + '"]');
        var $chatText = $chatItem.find('.chat-text');
        var currentTitle = $chatText.text().trim();

        // Replace text with input
        var $input = $('<input type="text" class="rename-input">')
            .val(currentTitle)
            .css({
                background: 'var(--bg-secondary)',
                border: '1px solid var(--accent)',
                borderRadius: '4px',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
                padding: '2px 6px',
                width: '100%',
                outline: 'none'
            });
        $chatText.html('').append($input);
        $input.focus().select();

        var saved = false;
        function saveRename() {
            if (saved) return;
            saved = true;
            var newTitle = $input.val().trim();
            var hasPinIcon = $chatItem.data('pinned');
            var pinHtml = hasPinIcon ? '<i class="bi bi-pin-fill me-1" style="font-size:0.7rem;color:var(--accent)"></i>' : '';

            if (!newTitle || newTitle === currentTitle) {
                // Restore original
                $chatText.html(pinHtml + '<i class="bi bi-chat-left-dots"></i>' + escapeHtml(currentTitle));
                return;
            }
            $.ajax({
                url: '/api/sessions/' + sessionId + '/rename/',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({title: newTitle}),
                success: function(data) {
                    $chatText.html(pinHtml + '<i class="bi bi-chat-left-dots"></i>' + escapeHtml(data.title));
                    if (String(sessionId) === String(currentSessionId)) {
                        $('#chat-header-title').text(data.title);
                    }
                    showToast('Chat renamed');
                },
                error: function() {
                    $chatText.html(pinHtml + '<i class="bi bi-chat-left-dots"></i>' + escapeHtml(currentTitle));
                    showToast('Failed to rename', 'error');
                }
            });
        }

        $input.on('blur', saveRename);
        $input.on('keypress', function(ev) {
            if (ev.which === 13) {
                ev.preventDefault();
                $input.off('blur');
                saveRename();
            }
        });
        $input.on('keydown', function(ev) {
            if (ev.which === 27) { // Escape
                saved = true;
                $input.off('blur');
                var pinHtml2 = $chatItem.data('pinned') ? '<i class="bi bi-pin-fill me-1" style="font-size:0.7rem;color:var(--accent)"></i>' : '';
                $chatText.html(pinHtml2 + '<i class="bi bi-chat-left-dots"></i>' + escapeHtml(currentTitle));
            }
        });
    });

    // ==============================
    // === PIN ===
    // ==============================
    $(document).on('click', '.chat-action-pin', function(e) {
        e.preventDefault();
        e.stopPropagation();
        var sessionId = $(this).data('session-id');
        $.ajax({
            url: '/api/sessions/' + sessionId + '/pin/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({}),
            success: function(data) {
                showToast(data.is_pinned ? 'Chat pinned' : 'Chat unpinned');
                refreshSidebar();
            },
            error: function() {
                showToast('Failed to update pin', 'error');
            }
        });
    });

    // ==============================
    // === SHARE ===
    // ==============================
    var targetShareSessionId = null;

    function openShareModal(sessionId) {
        targetShareSessionId = sessionId;
        $('#shareStep1').show();
        $('#shareStep2').hide();
        var modal = new bootstrap.Modal(document.getElementById('shareModal'));
        modal.show();
    }

    $(document).on('click', '.chat-action-share', function(e) {
        e.preventDefault();
        e.stopPropagation();
        openShareModal($(this).data('session-id'));
    });

    $(document).on('click', '.share-btn', function() {
        if (!currentSessionId) {
            showToast('No chat to share', 'error');
            return;
        }
        openShareModal(currentSessionId);
    });

    $(document).on('click', '#confirmCreateLinkBtn', function() {
        var $btn = $(this);
        var originalText = $btn.text();
        $btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creating...');

        $.ajax({
            url: '/api/sessions/' + targetShareSessionId + '/share/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({}),
            success: function(data) {
                $('#shareLink').val(data.share_url);
                $('#shareStep1').hide();
                $('#shareStep2').show();
            },
            error: function() {
                showToast('Failed to generate share link', 'error');
            },
            complete: function() {
                $btn.prop('disabled', false).text(originalText);
            }
        });
    });

    // Copy share link button
    $(document).on('click', '#copyShareLink', function() {
        var link = $('#shareLink').val();
        navigator.clipboard.writeText(link).then(function() {
            showToast('Link copied to clipboard!');
        });
    });

    // ==============================
    // === DELETE ===
    // ==============================
    var deleteTargetId = null;

    $(document).on('click', '.chat-action-delete', function(e) {
        e.preventDefault();
        e.stopPropagation();
        deleteTargetId = $(this).data('session-id');
        var modal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
        modal.show();
    });

    $(document).on('click', '#confirmDeleteBtn', function() {
        if (!deleteTargetId) return;
        var targetId = deleteTargetId;
        $.ajax({
            url: '/api/sessions/' + targetId + '/delete/',
            type: 'DELETE',
            success: function() {
                var $item = $('.chat-item[data-session-id="' + targetId + '"]');
                var wasActive = $item.hasClass('active');
                $item.remove();
                showToast('Chat deleted');

                // Remove section labels if their section is now empty
                $('.sidebar-section-label').each(function() {
                    var $nextItems = $(this).nextUntil('.sidebar-section-label', '.chat-item');
                    if ($nextItems.length === 0) $(this).remove();
                });

                if (wasActive) {
                    var $next = $('.chat-item').first();
                    if ($next.length) {
                        loadSession($next.data('session-id'));
                    } else {
                        currentSessionId = null;
                        saveActiveSession(null);
                        showWelcomeScreen();
                    }
                }
                deleteTargetId = null;
                bootstrap.Modal.getInstance(document.getElementById('deleteConfirmModal')).hide();
            },
            error: function() {
                showToast('Failed to delete chat', 'error');
                deleteTargetId = null;
            }
        });
    });

    // ==============================
    // === DELETE ALL (Settings) ===
    // ==============================
    $(document).on('click', '.delete-all-chats-btn', function() {
        var myModal = new bootstrap.Modal(document.getElementById('deleteAllConfirmModal'));
        myModal.show();
    });

    $('#confirmDeleteAllBtn').click(function() {
        var $btn = $(this);
        var originalText = $btn.text();
        $btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Deleting...');

        $.ajax({
            url: '/api/sessions/delete-all/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({}),
            success: function() {
                $('#chat-list').empty();
                currentSessionId = null;
                saveActiveSession(null);
                showWelcomeScreen();
                showToast('All chats deleted');
                
                // Hide confirmation modal
                bootstrap.Modal.getInstance(document.getElementById('deleteAllConfirmModal')).hide();
                
                // Hide settings modal
                var settingsModal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
                if (settingsModal) {
                    settingsModal.hide();
                }
            },
            error: function() {
                showToast('Failed to delete all chats', 'error');
            },
            complete: function() {
                $btn.prop('disabled', false).text(originalText);
            }
        });
    });

    // ==============================
    // === SEARCH ===
    // ==============================
    $('.chat-search').on('input', function() {
        var query = $(this).val().toLowerCase().trim();
        $('.chat-item').each(function() {
            var title = $(this).find('.chat-text').text().toLowerCase();
            $(this).toggle(title.indexOf(query) !== -1);
        });
        // Hide/show section labels based on visible items
        $('.sidebar-section-label').each(function() {
            var $nextItems = $(this).nextUntil('.sidebar-section-label', '.chat-item:visible');
            $(this).toggle($nextItems.length > 0);
        });
    });

    // ==============================
    // === THEME TOGGLE ===
    // ==============================
    function setTheme(theme, sync) {
        sync = sync || false;
        localStorage.setItem('theme', theme);

        var isDark = true;
        if (theme === 'light') {
            isDark = false;
        } else if (theme === 'dark') {
            isDark = true;
        } else {
            // system
            isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        }

        if (!isDark) {
            $('html, body').removeClass('dark-theme').addClass('light-theme');
            $('html').attr('data-bs-theme', 'light');
            $('#theme-toggle').html('<i class="bi bi-sun"></i>');
        } else {
            $('html, body').removeClass('light-theme').addClass('dark-theme');
            $('html').attr('data-bs-theme', 'dark');
            $('#theme-toggle').html('<i class="bi bi-moon-stars"></i>');
        }

        // Sync with backend only when explicitly requested (user click)
        if (sync) {
            $.ajax({
                url: '/accounts/update-theme/',
                type: 'POST',
                data: JSON.stringify({ theme: theme }),
                contentType: 'application/json',
                success: function(response) {
                    if (response.status === 'success') {
                        showToast('Theme updated to ' + theme.charAt(0).toUpperCase() + theme.slice(1));
                    } else {
                        showToast('Failed to save theme preference', 'error');
                    }
                },
                error: function() {
                    showToast('Error saving theme preference', 'error');
                }
            });
        }
    }

    // Initialize theme from localStorage on page load
    var savedTheme = localStorage.getItem('theme') || 'system';
    setTheme(savedTheme, false);

    // Update theme-card active state to match saved theme
    $('.theme-card').removeClass('active');
    $('.theme-card[data-theme="' + savedTheme + '"]').addClass('active');

    $('#theme-toggle').click(function() {
        if ($('body').hasClass('dark-theme')) {
            setTheme('light', true);
        } else {
            setTheme('dark', true);
        }
    });

    // ==============================
    // === SETTINGS MODAL ===
    // ==============================
    $('#settings-btn').click(function() {
        var myModal = new bootstrap.Modal(document.getElementById('settingsModal'));
        myModal.show();
    });

    $('.settings-nav-item').click(function() {
        var target = $(this).data('target');
        $('.settings-nav-item').removeClass('active');
        $(this).addClass('active');
        $('.settings-section').removeClass('active');
        $('#' + target).addClass('active');
    });

    // Modal Theme Selection — using event delegation for Bootstrap modal compatibility
    $(document).on('click', '.theme-card', function() {
        $('.theme-card').removeClass('active');
        $(this).addClass('active');
        var selectedTheme = $(this).data('theme');
        setTheme(selectedTheme, true);
    });

    // ==============================
    // === SHARED LINKS MANAGEMENT ===
    // ==============================
    function loadSharedLinks() {
        $('#sharedLinksList').html('<div class="text-center py-4"><div class="spinner-border text-secondary" role="status"></div></div>');
        $('#noSharedLinksMsg').hide();
        
        $.ajax({
            url: '/api/sessions/shared-links/',
            type: 'GET',
            success: function(data) {
                $('#sharedLinksList').empty();
                if (data.links.length === 0) {
                    $('#noSharedLinksMsg').show();
                } else {
                    data.links.forEach(function(link) {
                        var html = `
                            <div class="d-flex align-items-center py-3 border-bottom border-secondary" id="shared-link-row-${link.id}" style="gap: 12px;">
                                <i class="bi bi-link-45deg text-secondary" style="font-size: 1.1rem; flex-shrink: 0;"></i>
                                <div class="text-truncate" style="flex: 1; min-width: 0; color: var(--text-primary); font-size: 0.95rem;">
                                    ${link.title}
                                </div>
                                <div style="font-size: 0.85rem; color: var(--text-secondary); white-space: nowrap; flex-shrink: 0;">
                                    Shared on ${link.shared_at}
                                </div>
                                <div class="d-flex" style="gap: 12px; flex-shrink: 0;">
                                    <i class="bi bi-copy copy-shared-link-btn" style="cursor: pointer; color: var(--text-secondary); transition: color 0.2s;" data-url="${link.share_url}" title="Copy Link" onmouseover="this.style.color='var(--text-primary)'" onmouseout="this.style.color='var(--text-secondary)'"></i>
                                    <i class="bi bi-trash delete-shared-link-btn" style="cursor: pointer; color: var(--text-secondary); transition: color 0.2s;" data-id="${link.id}" title="Delete Shared Link" onmouseover="this.style.color='var(--danger-color)'" onmouseout="this.style.color='var(--text-secondary)'"></i>
                                </div>
                            </div>
                        `;
                        $('#sharedLinksList').append(html);
                    });
                }
            },
            error: function() {
                $('#sharedLinksList').html('<div class="text-danger text-center py-3">Failed to load shared links.</div>');
            }
        });
    }

    $('#manageSharedLinksBtn').click(function() {
        $('#settingsMainView').hide();
        $('#sharedLinksView').show();
        loadSharedLinks();
    });

    $('#backToSettingsBtn').click(function() {
        $('#sharedLinksView').hide();
        $('#settingsMainView').show();
    });

    $(document).on('click', '.copy-shared-link-btn', function() {
        var url = $(this).data('url');
        navigator.clipboard.writeText(url).then(function() {
            showToast('Link copied to clipboard!');
        });
    });

    var deleteSharedLinkTargetId = null;
    var $deleteSharedLinkRow = null;

    $(document).on('click', '.delete-shared-link-btn', function() {
        deleteSharedLinkTargetId = $(this).data('id');
        $deleteSharedLinkRow = $('#shared-link-row-' + deleteSharedLinkTargetId);
        var modal = new bootstrap.Modal(document.getElementById('deleteSharedLinkConfirmModal'));
        modal.show();
    });

    $(document).on('click', '#confirmDeleteSharedLinkBtn', function() {
        if (!deleteSharedLinkTargetId) return;
        var sessionId = deleteSharedLinkTargetId;
        var $row = $deleteSharedLinkRow;

        $row.css('opacity', '0.5');

        // Hide the confirmation modal
        bootstrap.Modal.getInstance(document.getElementById('deleteSharedLinkConfirmModal')).hide();

        $.ajax({
            url: '/api/sessions/' + sessionId + '/share/',
            type: 'DELETE',
            success: function() {
                $row.remove();
                if ($('#sharedLinksList').children().length === 0) {
                    $('#noSharedLinksMsg').show();
                }
                showToast('Shared link deleted successfully.');
            },
            error: function() {
                $row.css('opacity', '1');
                showToast('Failed to delete shared link.', 'error');
            },
            complete: function() {
                deleteSharedLinkTargetId = null;
                $deleteSharedLinkRow = null;
            }
        });
    });

    // ==============================
    // === SIDEBAR TOGGLE ===
    // ==============================
    var $sidebar = $('.sidebar');
    var $mainContent = $('.main-content');
    var $openBtn = $('#sidebar-toggle-open');
    var $closeBtn = $('#sidebar-toggle-close');
    var $overlay = $('#sidebar-overlay');

    function openSidebar() {
        $sidebar.removeClass('closed');
        $closeBtn.show();
        $openBtn.hide();
        if ($(window).width() > 768) {
            $mainContent.css('margin-left', '260px');
        } else {
            $sidebar.addClass('open');
            $overlay.addClass('show');
        }
    }

    function closeSidebar() {
        $sidebar.addClass('closed');
        $openBtn.show();
        $closeBtn.hide();
        if ($(window).width() > 768) {
            $mainContent.css('margin-left', '0');
        } else {
            $sidebar.removeClass('open');
            $overlay.removeClass('show');
        }
    }

    $openBtn.on('click', openSidebar);
    $closeBtn.on('click', closeSidebar);

    // Close sidebar when tapping overlay on mobile
    $overlay.on('click', closeSidebar);

    // Close button inside sidebar (mobile)
    $('#sidebar-close-mobile').on('click', closeSidebar);

    // Close sidebar on mobile when a chat item is clicked
    $(document).on('click', '.chat-item', function() {
        if ($(window).width() <= 768) {
            closeSidebar();
        }
    });

    if ($(window).width() <= 768) {
        closeSidebar();
    } else {
        openSidebar();
    }

    $(window).on('resize', function() {
        if ($(window).width() <= 768) {
            if (!$sidebar.hasClass('closed')) {
                closeSidebar();
            }
            $overlay.removeClass('show');
        } else {
            $overlay.removeClass('show');
            if ($sidebar.hasClass('closed')) {
                openSidebar();
            }
        }
    });

    // ==============================
    // === ACTION BUTTONS ===
    // ==============================
    $(document).on('click', '.thumbs-up', function() {
        $(this).find('i').toggleClass('bi-hand-thumbs-up bi-hand-thumbs-up-fill');
        showToast('Thanks for the feedback!');
    });

    $(document).on('click', '.thumbs-down', function() {
        $(this).find('i').toggleClass('bi-hand-thumbs-down bi-hand-thumbs-down-fill');
        showToast('Sorry, we will improve!');
    });

    // ==============================
    // === REGENERATE ===
    // ==============================
    $(document).on('click', '.regenerate', function() {
        var $btn = $(this);
        var $botMessage = $btn.closest('.message.bot-message');
        var userQuery = $botMessage.data('userQuery');
        if (!userQuery) {
            showToast('Cannot regenerate this message', 'error');
            return;
        }
        var $bubble = $botMessage.find('.message-bubble');
        var originalBubbleHtml = $bubble.html();
        $bubble.html('Thinking...');
        $btn.prop('disabled', true);
        var selectedModel = $('#modelDropdown').data('selected-model') || 'auto';
        $.ajax({
            url: '/api/chat/',
            type: 'POST',
            data: JSON.stringify({
                query: userQuery,
                model: selectedModel,
                dual_response: dualEnabled,
                session_id: currentSessionId
            }),
            contentType: 'application/json',
            success: function(data) {
                var newParsedText = marked.parse(data.response);
                var responses = $botMessage.data('responses');
                responses.push(newParsedText);
                $botMessage.data('responses', responses);
                var models = $botMessage.data('models');
                var modelName = data.model ? formatModelName(data.model) : 'Unknown Model';
                models.push(modelName);
                $botMessage.data('models', models);
                $botMessage.data('currentIndex', responses.length - 1);
                updateBotMessageView($botMessage);
            },
            error: function() {
                $bubble.html(originalBubbleHtml);
                showToast('Regeneration failed', 'error');
            },
            complete: function() {
                $btn.prop('disabled', false);
            }
        });
    });

    // ==============================
    // === RESPONSE NAVIGATION ===
    // ==============================
    $(document).on('click', '.prev-response', function() {
        var $botMessage = $(this).closest('.message.bot-message');
        var currentIndex = $botMessage.data('currentIndex');
        $botMessage.data('currentIndex', --currentIndex);
        updateBotMessageView($botMessage);
    });

    $(document).on('click', '.next-response', function() {
        var $botMessage = $(this).closest('.message.bot-message');
        var currentIndex = $botMessage.data('currentIndex');
        $botMessage.data('currentIndex', ++currentIndex);
        updateBotMessageView($botMessage);
    });

    // ==============================
    // === COPY ===
    // ==============================
    $(document).on('click', '.copy', function() {
        var text = $(this).closest('.message-content-wrapper').find('.message-bubble').text();
        navigator.clipboard.writeText(text).then(function() {
            showToast('Copied to clipboard!');
        });
    });

    // ==============================
    // === MODEL SELECTION ===
    // ==============================
    $(document).on('click', '.model-select .dropdown-item', function(e) {
        e.preventDefault();
        // Model selection locked to Auto
    });

    // ==============================
    // === DUAL RESPONSE TOGGLE ===
    // ==============================
    $('#dualResponseToggle').change(function() {
        dualEnabled = $(this).is(':checked');
    });

    // ==============================
    // === VOICE INPUT ===
    // ==============================
    var micIcon = $('.input-icons .bi-mic').parent();
    var isRecording = false;
    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        var recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        var finalTranscript = '';
        recognition.onstart = function() {
            isRecording = true;
            micIcon.find('i').removeClass('bi-mic').addClass('bi-mic-fill');
        };
        recognition.onend = function() {
            isRecording = false;
            micIcon.find('i').removeClass('bi-mic-fill').addClass('bi-mic');
            if (finalTranscript.trim()) {
                $('#send-btn').click();
            }
            finalTranscript = '';
        };
        recognition.onresult = function(event) {
            var interimTranscript = '';
            for (var i = event.resultIndex; i < event.results.length; i++) {
                var transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript + ' ';
                } else {
                    interimTranscript += transcript;
                }
            }
            $('#user-input').val(finalTranscript + interimTranscript);
            $('#user-input').trigger('input');
        };
        recognition.onerror = function(event) {
            console.error('Speech recognition error', event.error);
            if (event.error !== 'no-speech') {
                showToast('Speech recognition error: ' + event.error, 'error');
            }
        };
        micIcon.click(function() {
            if (isRecording) {
                recognition.stop();
            } else {
                finalTranscript = '';
                recognition.start();
            }
        });
    } else {
        micIcon.click(function() {
            showToast('Speech recognition not supported in this browser', 'error');
        });
    }

    // ==============================
    // === INITIALIZE ===
    // ==============================

    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Load sessions from database
    loadSessions();
    scrollToBottom();
});
