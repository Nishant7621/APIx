import './globals.css';

export const metadata = {
  title: 'APIx | Real-Time Airfare Price Index for India',
  description: 'High-frequency airfare intelligence and national CPI augmentation engine for MoSPI & RBI',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 antialiased selection:bg-blue-600 selection:text-white">
        {children}
      </body>
    </html>
  );
}
