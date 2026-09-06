import { h, render } from 'https://esm.sh/preact@10.20.1';
import { useState, useRef, useEffect } from 'https://esm.sh/preact@10.20.1/hooks';
import htm from 'https://esm.sh/htm@3.1.1';
import { marked } from 'https://esm.sh/marked@12.0.2';

const html = htm.bind(h);

// Configure marked options
marked.setOptions({
  breaks: true,
  gfm: true,
});

const SAMPLE_QUERIES = [
  "How do I track my order?",
  "What is the return & refund policy?",
  "Can I cancel an order after placing it?",
  "How do I exchange an item?",
  "What payment methods do you accept?"
];

function MessageItem({ msg }) {
  const [showSources, setShowSources] = useState(false);
  const isUser = msg.sender === 'user';

  // Render markdown safely
  const renderedContent = isUser 
    ? msg.text 
    : marked.parse(msg.text || '');

  return html`
    <div class="message-row ${isUser ? 'user' : 'bot'}">
      <div class="bubble">
        ${isUser 
          ? html`<p>${msg.text}</p>`
          : html`<div class="markdown-body" dangerouslySetInnerHTML=${{ __html: renderedContent }} />`
        }

        ${!isUser && msg.sources && msg.sources.length > 0 && html`
          <div class="sources-container">
            <button 
              class="sources-toggle" 
              onClick=${() => setShowSources(!showSources)}
            >
              <span>${showSources ? '▲ Hide' : '▼ View'} ${msg.sources.length} Cited Sources</span>
            </button>

            ${showSources && html`
              <div class="sources-list">
                ${msg.sources.map((src) => html`
                  <div class="source-card" key=${src.id}>
                    <div class="source-card-header">
                      <span class="source-title">${src.title}</span>
                      <span class="source-badge">${src.category}</span>
                    </div>
                    <p class="source-excerpt">${src.excerpt}</p>
                  </div>
                `)}
              </div>
            `}
          </div>
        `}
      </div>
      <span class="timestamp">${msg.timestamp}</span>
    </div>
  `;
}

function App() {
  const [sessionId, setSessionId] = useState(() => `sess_${Date.now()}`);
  const [sessions, setSessions] = useState([]);
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'bot',
      text: "How can I help you today with orders, returns, shipping, or account policies?",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      sources: []
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const fetchSessions = async () => {
    try {
      const res = await fetch('/api/sessions');
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch (err) {
      console.warn("Failed to fetch sessions", err);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        await fetch('/api/sessions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sessionId })
        });
      } catch (err) {
        console.warn("Failed to create initial session", err);
      }
      fetchSessions();
    })();
  }, []);

  const loadSession = async (id) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/sessions/${id}`);
      const data = await res.json();
      const loadedMessages = data.history.map((m, idx) => ({
        id: `loaded_${idx}`,
        sender: m.sender,
        text: m.text,
        timestamp: '',
        sources: []
      }));
      if (loadedMessages.length === 0) {
        loadedMessages.push({
          id: 'welcome_reset',
          sender: 'bot',
          text: "How can I help you today with orders, returns, shipping, or account policies?",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          sources: []
        });
      }
      setMessages(loadedMessages);
      setSessionId(id);
    } catch (err) {
      console.error("Failed to load session", err);
    } finally {
      setLoading(false);
    }
  };

  const deleteSession = async (e, id) => {
    e.stopPropagation();
    try {
      await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
      if (sessionId === id) {
        handleNewChat();
      }
      fetchSessions();
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleNewChat = async () => {
    const newId = `sess_${Date.now()}`;
    setSessionId(newId);
    setMessages([
      {
        id: 'welcome_reset',
        sender: 'bot',
        text: "New conversation started. How can I help you today?",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: []
      }
    ]);
    setInput('');

    try {
      await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId: newId })
      });
      await fetchSessions();
    } catch (err) {
      console.warn("Failed to create session on server", err);
    }
  };

  const handleSendMessage = async (textToSend) => {
    const query = textToSend || input.trim();
    if (!query || loading) return;
    
    if (query.length > 200) {
      alert("Please keep your question under 200 characters.");
      return;
    }

    const userMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query, sessionId }),
      });

      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.error || `Server returned status: ${res.status}`);
      }

      if (data.sessionId) {
        setSessionId(data.sessionId);
      }

      const botMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'bot',
        text: data.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: data.sources || [],
      };

      setMessages((prev) => [...prev, botMessage]);
      fetchSessions();
    } catch (err) {
      console.error(err);
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'bot',
        text: err.message || "Sorry, I encountered an issue retrieving the answer. Please try again or reach out to human support at support@example.com.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: [],
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    handleSendMessage();
  };

  return html`
    <!-- Sidebar -->
    <div class="sidebar">
      <div class="sidebar-header">
        <button class="new-chat-btn" onClick=${handleNewChat} title="Start a fresh conversation">
          <svg width="15" height="15" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
          </svg>
          <span>New Chat</span>
        </button>
      </div>
      <div class="sessions-list">
        ${sessions.length === 0 && html`
          <div style="padding: 24px 12px; text-align: center; color: var(--text-dim); font-size: 0.8rem;">
            No conversations saved yet.
          </div>
        `}
        ${sessions.map((s) => html`
          <div 
            class=${`session-item ${s.id === sessionId ? 'active' : ''}`} 
            onClick=${() => loadSession(s.id)}
            key=${s.id}
          >
            <div class="session-info">
              <span class="session-preview">${s.preview}</span>
              <span class="session-time">${new Date(s.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
            <button class="delete-session-btn" onClick=${(e) => deleteSession(e, s.id)} title="Delete Session">
              <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
              </svg>
            </button>
          </div>
        `)}
      </div>
    </div>

    <!-- Main Chat Area -->
    <div class="chat-container">
      <!-- Header -->
      <header class="chat-header">
        <div class="header-brand">
          <div class="avatar-bot">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
            </svg>
          </div>
          <div class="brand-info">
            <h1>SupportAI Assistant</h1>
            <p>RAG Knowledge Base • Multi-turn Memory</p>
          </div>
        </div>
        <div class="header-actions">
          <span class="badge-tag">Bitext KB</span>
        </div>
      </header>

      <!-- Message History -->
      <div class="messages-list">
        ${messages.map((m) => html`<${MessageItem} key=${m.id} msg=${m} />`)}

        ${loading && html`
          <div class="message-row bot">
            <div class="bubble">
              <div class="typing-indicator">
                <span class="dot"></span>
                <span class="dot"></span>
                <span class="dot"></span>
              </div>
            </div>
          </div>
        `}
        <div ref=${messagesEndRef} />
      </div>

      <!-- Suggestion Chips -->
      <div class="chips-container">
        ${SAMPLE_QUERIES.map((query) => html`
          <button 
            class="chip-btn" 
            onClick=${() => handleSendMessage(query)}
            disabled=${loading}
          >
            ${query}
          </button>
        `)}
      </div>

      <!-- Input Area -->
      <div class="input-area">
        <form class="input-form" onSubmit=${onSubmit}>
          <input
            type="text"
            class="chat-input"
            placeholder="Ask a follow-up or any support question..."
            value=${input}
            onInput=${(e) => setInput(e.target.value.substring(0, 200))}
            disabled=${loading}
            maxLength="200"
          />
          <button type="submit" class="send-btn" disabled=${loading || !input.trim()}>
            <span>Send</span>
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path>
            </svg>
          </button>
        </form>
        <div style="text-align: right; font-size: 0.7rem; color: var(--text-dim); margin-top: 4px;">
          ${input.length} / 200
        </div>
      </div>
    </div>
  `;
}

render(html`<${App} />`, document.getElementById('app'));
