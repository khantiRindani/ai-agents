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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleNewChat = async () => {
    if (loading) return;
    try {
      await fetch('/api/chat/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId }),
      });
    } catch (err) {
      console.warn("Failed to clear session on backend", err);
    }

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
  };

  const handleSendMessage = async (textToSend) => {
    const query = textToSend || input.trim();
    if (!query || loading) return;

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

      if (!res.ok) {
        throw new Error(`Server returned status: ${res.status}`);
      }

      const data = await res.json();
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
    } catch (err) {
      console.error(err);
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'bot',
        text: "Sorry, I encountered an issue retrieving the answer. Please try again or reach out to human support at support@example.com.",
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
          <button class="new-chat-btn" onClick=${handleNewChat} title="Start a fresh conversation and clear memory">
            <svg width="15" height="15" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
            </svg>
            <span>New Chat</span>
          </button>
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
            onInput=${(e) => setInput(e.target.value)}
            disabled=${loading}
          />
          <button type="submit" class="send-btn" disabled=${loading || !input.trim()}>
            <span>Send</span>
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path>
            </svg>
          </button>
        </form>
      </div>
    </div>
  `;
}

render(html`<${App} />`, document.getElementById('app'));
