/**
 * Mobile detection utility
 */
import React from 'react';

export function isMobile(): boolean {
  // Check if window exists (for SSR compatibility)
  if (typeof window === 'undefined') return false;

  // Check viewport width (mobile typically < 768px)
  const width = window.innerWidth;
  if (width < 768) return true;

  // Check user agent for mobile devices
  const userAgent = navigator.userAgent || navigator.vendor || (window as any).opera;

  // Mobile device patterns
  const mobilePatterns = [
    /Android/i,
    /webOS/i,
    /iPhone/i,
    /iPad/i,
    /iPod/i,
    /BlackBerry/i,
    /Windows Phone/i
  ];

  return mobilePatterns.some(pattern => pattern.test(userAgent));
}

/**
 * Hook to track mobile state with window resize
 */
export function useMobile() {
  const [mobile, setMobile] = React.useState(isMobile);

  React.useEffect(() => {
    const handleResize = () => setMobile(isMobile());
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return mobile;
}
