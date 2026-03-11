'use client';

import { useState, useEffect, useRef } from 'react';
import { io, Socket } from 'socket.io-client';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Props {
  sessionId: string;
  name: string;
  onDone: () => void;
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:3000';

export default function ChatUI({ sessionId, name, onDone }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<Socket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const socket = io(`${WS_URL}/chat`, {
      transports: ['websocket', 'polling'],
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setConnected(true);
      socket.emit('message', {
        session_id: sessionId,
        content: `Hi! I'm ${name}.`,
      });
      setLoading(true);
    });

    socket.on('message', (data: { role: string; content: string }) => {
      setMessages((prev) => [
        ...prev,
        { role: data.role as 'user' | 'assistant', content: data.content },
      ]);
      setLoading(false);
    });

    socket.on('done', () => {
      setTimeout(onDone, 1500);
    });

    socket.on('error', (err: { message: string }) => {
      console.error('Socket error:', err);
      setLoading(false);
    });

    socket.on('disconnect', () => {
      setConnected(false);
    });

    return () => {
      socket.disconnect();
    };
  }, [sessionId, name, onDone]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const inputRef = useRef<HTMLTextAreaElement>(null);

  const autoResize = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  };

  const sendMessage = () => {
    if (!input.trim() || loading || !socketRef.current) return;

    const content = input.trim();
    setInput('');
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
    setMessages((prev) => [...prev, { role: 'user', content }]);
    setLoading(true);

    socketRef.current.emit('message', { session_id: sessionId, content });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.chat}>
        <div style={styles.header}>
          <div style={styles.avatar}>M</div>
          <div>
            <div style={styles.headerName}>Monday.com Assistant</div>
            <div style={styles.headerStatus}>
              <span
                style={{
                  ...styles.statusDot,
                  background: connected ? '#00B894' : '#ADB5BD',
                }}
              />
              {connected ? 'Online' : 'Connecting...'}
            </div>
          </div>
        </div>

        <div style={styles.messages}>
          {messages.length === 0 && (
            <div style={styles.typingWrapper}>
              <TypingDots />
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              style={{
                ...styles.message,
                ...(msg.role === 'user' ? styles.userMessage : styles.assistantMessage),
              }}
            >
              {msg.content}
            </div>
          ))}
          {loading && messages.length > 0 && (
            <div style={styles.assistantMessage}>
              <TypingDots />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div style={styles.inputArea}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => { setInput(e.target.value); autoResize(); }}
            onKeyDown={handleKeyDown}
            placeholder="Type your answer..."
            style={styles.input}
            disabled={loading}
            rows={1}
          />
          <button
            onClick={sendMessage}
            style={{
              ...styles.sendBtn,
              opacity: loading || !input.trim() ? 0.5 : 1,
            }}
            disabled={loading || !input.trim()}
          >
            →
          </button>
        </div>
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div style={{ display: 'flex', gap: '4px', alignItems: 'center', padding: '4px 0' }}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            background: '#ADB5BD',
            display: 'inline-block',
            animation: `blink 1.4s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  },
  chat: {
    background: '#fff',
    borderRadius: '16px',
    width: '100%',
    maxWidth: '600px',
    boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
    display: 'flex',
    flexDirection: 'column',
    height: '600px',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '20px 24px',
    borderBottom: '1px solid #E9ECEF',
  },
  avatar: {
    width: '44px',
    height: '44px',
    background: '#6C5CE7',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    fontWeight: 700,
    fontSize: '18px',
  },
  headerName: {
    fontWeight: 600,
    fontSize: '16px',
    color: '#212529',
  },
  headerStatus: {
    fontSize: '13px',
    color: '#6C757D',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  statusDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    display: 'inline-block',
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  typingWrapper: {
    alignSelf: 'flex-start',
  },
  message: {
    padding: '12px 16px',
    borderRadius: '12px',
    fontSize: '15px',
    lineHeight: 1.5,
    maxWidth: '80%',
    whiteSpace: 'pre-wrap',
  },
  userMessage: {
    background: '#6C5CE7',
    color: '#fff',
    alignSelf: 'flex-end',
    borderBottomRightRadius: '4px',
  },
  assistantMessage: {
    background: '#F1F3F5',
    color: '#212529',
    alignSelf: 'flex-start',
    borderBottomLeftRadius: '4px',
  },
  inputArea: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: '8px',
    padding: '16px 20px',
    borderTop: '1px solid #E9ECEF',
  },
  input: {
    flex: 1,
    padding: '12px 16px',
    border: '1.5px solid #E9ECEF',
    borderRadius: '8px',
    fontSize: '15px',
    color: '#212529',
    background: '#fff',
    resize: 'none',
    overflow: 'hidden',
    lineHeight: 1.5,
    fontFamily: 'inherit',
    maxHeight: '160px',
    overflowY: 'auto',
  },
  sendBtn: {
    width: '48px',
    height: '48px',
    background: '#6C5CE7',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    fontSize: '20px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
};
