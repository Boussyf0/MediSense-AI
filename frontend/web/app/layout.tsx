import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';

export const metadata: Metadata = {
  title: 'MediSense AI — Console Clinique',
  description: 'Assistant médical IA pour professionnels de santé',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
