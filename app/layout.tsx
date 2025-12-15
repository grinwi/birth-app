import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Birthdays App',
  description: 'Manage birthdays with filters, sorting, and CSV sync',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
