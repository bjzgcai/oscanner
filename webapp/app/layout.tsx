import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AntdRegistry } from '@ant-design/nextjs-registry';
import Navigation from '../components/Navigation';
import { AppSettingsProvider } from '../components/AppSettingsContext';
import { UserSettingsProvider } from '../components/UserSettingsContext';
import I18nProviderFromSettings from '../components/I18nProviderFromSettings';
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Git Engineer Skill Evaluator",
  description: "LLM-Powered Six-Dimensional Engineering Capability Analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} antialiased`}>
        <AntdRegistry>
          <AppSettingsProvider>
            <UserSettingsProvider>
              <I18nProviderFromSettings>
                <Navigation />
                {children}
              </I18nProviderFromSettings>
            </UserSettingsProvider>
          </AppSettingsProvider>
        </AntdRegistry>
      </body>
    </html>
  );
}
