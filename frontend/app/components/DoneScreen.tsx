'use client';

interface Props {
  name: string;
}

export default function DoneScreen({ name }: Props) {
  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.checkmark}>✓</div>
        <h1 style={styles.title}>You're all set, {name.split(' ')[0]}!</h1>
        <p style={styles.subtitle}>
          Your Monday.com workspace is being prepared just for you.
        </p>
        <div style={styles.infoBox}>
          <span style={styles.emailIcon}>📧</span>
          <div>
            <div style={styles.infoTitle}>Check your email</div>
            <div style={styles.infoText}>
              We're sending you your board link and payment details. It should arrive within
              a minute.
            </div>
          </div>
        </div>
        <p style={styles.footer}>Welcome to monday.com — where work gets done.</p>
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
    maxWidth: '480px',
    boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
    textAlign: 'center',
  },
  checkmark: {
    width: '72px',
    height: '72px',
    background: '#00B894',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '0 auto 24px',
    fontSize: '32px',
    color: '#fff',
    lineHeight: '72px',
  },
  title: {
    fontSize: '28px',
    fontWeight: 700,
    color: '#212529',
    marginBottom: '12px',
  },
  subtitle: {
    fontSize: '16px',
    color: '#6C757D',
    marginBottom: '32px',
    lineHeight: 1.5,
  },
  infoBox: {
    background: '#F8F9FA',
    borderRadius: '12px',
    padding: '20px',
    display: 'flex',
    gap: '16px',
    alignItems: 'flex-start',
    textAlign: 'left',
    marginBottom: '32px',
  },
  emailIcon: {
    fontSize: '28px',
    flexShrink: 0,
  },
  infoTitle: {
    fontWeight: 600,
    fontSize: '15px',
    color: '#212529',
    marginBottom: '4px',
  },
  infoText: {
    fontSize: '14px',
    color: '#6C757D',
    lineHeight: 1.5,
  },
  footer: {
    fontSize: '13px',
    color: '#ADB5BD',
    fontStyle: 'italic',
  },
};
