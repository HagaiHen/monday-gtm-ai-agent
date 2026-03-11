import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'monday.com — Get your free workspace',
  description: 'Build a custom monday.com board tailored to your team.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
