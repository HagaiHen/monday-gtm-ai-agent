'use client';

import { useState, FormEvent } from 'react';

interface LeadData {
  sessionId: string;
  name: string;
  email: string;
  company: string;
  website: string;
  industry: string;
  painPoint: string;
  teamSize: string;
}

interface Props {
  onSubmit: (data: LeadData) => void;
}

const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || 'http://localhost:3000';

const INDUSTRIES = [
  'Technology',
  'Marketing & Advertising',
  'Construction & Real Estate',
  'Healthcare',
  'Finance & Banking',
  'Retail & E-commerce',
  'Education',
  'Manufacturing',
  'Media & Entertainment',
  'Professional Services',
  'Non-profit',
  'Other',
];

export default function LeadForm({ onSubmit }: Props) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [website, setWebsite] = useState('');
  const [industry, setIndustry] = useState('');
  const [painPoint, setPainPoint] = useState('');
  const [teamSize, setTeamSize] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !company.trim() || !website.trim() || !industry || !painPoint.trim() || !teamSize.trim()) {
      setError('Please fill in all required fields.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${GATEWAY_URL}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, company, website, industry, pain_point: painPoint, team_size: teamSize }),
      });

      if (!response.ok) throw new Error('Failed to create session');

      const data = await response.json();
      onSubmit({ sessionId: data.session_id, name, email, company, website, industry, painPoint, teamSize });
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <span style={styles.logoIcon}>M</span>
          <span style={styles.logoText}>monday.com</span>
        </div>

        <h1 style={styles.title}>Get your free workspace</h1>
        <p style={styles.subtitle}>
          Tell us about your team and we'll build a custom board tailored to your needs.
        </p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Full Name <span style={styles.required}>*</span></label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Smith"
                style={styles.input}
                disabled={loading}
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Work Email <span style={styles.required}>*</span></label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="jane@company.com"
                style={styles.input}
                disabled={loading}
              />
            </div>
          </div>

          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Company <span style={styles.required}>*</span></label>
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Acme Corp"
                style={styles.input}
                disabled={loading}
              />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Company Website <span style={styles.required}>*</span></label>
              <input
                type="url"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="https://acme.com"
                style={styles.input}
                disabled={loading}
              />
            </div>
          </div>

          <div style={styles.row}>
            <div style={styles.field}>
              <label style={styles.label}>Industry <span style={styles.required}>*</span></label>
              <select
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                style={{ ...styles.input, color: industry ? '#212529' : '#ADB5BD' }}
                disabled={loading}
              >
                <option value="" disabled>Select your industry</option>
                {INDUSTRIES.map((ind) => (
                  <option key={ind} value={ind}>{ind}</option>
                ))}
              </select>
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Team Size <span style={styles.required}>*</span></label>
              <input
                type="number"
                min="1"
                value={teamSize}
                onChange={(e) => setTeamSize(e.target.value)}
                placeholder="e.g. 12"
                style={styles.input}
                disabled={loading}
              />
            </div>
          </div>

          <div style={styles.field}>
            <label style={styles.label}>
              Use case <span style={styles.required}>*</span>
            </label>
            <textarea
              value={painPoint}
              onChange={(e) => setPainPoint(e.target.value)}
              placeholder="e.g. We struggle to track client projects across teams — tasks fall through the cracks and we have no visibility into deadlines."
              style={styles.textarea}
              rows={3}
              disabled={loading}
            />
          </div>

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" style={styles.button} disabled={loading}>
            {loading ? 'Setting up...' : 'Get started →'}
          </button>
        </form>
      </div>
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
  card: {
    background: '#fff',
    borderRadius: '16px',
    padding: '48px',
    width: '100%',
    maxWidth: '580px',
    boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '28px',
  },
  logoIcon: {
    width: '36px',
    height: '36px',
    background: '#6C5CE7',
    borderRadius: '8px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    fontWeight: 700,
    fontSize: '18px',
  },
  logoText: {
    fontSize: '20px',
    fontWeight: 700,
    color: '#212529',
  },
  title: {
    fontSize: '26px',
    fontWeight: 700,
    color: '#212529',
    marginBottom: '8px',
  },
  subtitle: {
    fontSize: '15px',
    color: '#6C757D',
    marginBottom: '28px',
    lineHeight: 1.5,
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  row: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  label: {
    fontSize: '13px',
    fontWeight: 500,
    color: '#343A40',
  },
  required: {
    color: '#E74C3C',
  },
  input: {
    padding: '11px 14px',
    border: '1.5px solid #E9ECEF',
    borderRadius: '8px',
    fontSize: '14px',
    color: '#212529',
    background: '#fff',
    width: '100%',
  },
  textarea: {
    padding: '11px 14px',
    border: '1.5px solid #E9ECEF',
    borderRadius: '8px',
    fontSize: '14px',
    color: '#212529',
    background: '#fff',
    resize: 'vertical',
    fontFamily: 'inherit',
    lineHeight: 1.5,
  },
  error: {
    color: '#E74C3C',
    fontSize: '13px',
  },
  button: {
    padding: '14px',
    background: '#6C5CE7',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    fontSize: '16px',
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: '4px',
  },
};
