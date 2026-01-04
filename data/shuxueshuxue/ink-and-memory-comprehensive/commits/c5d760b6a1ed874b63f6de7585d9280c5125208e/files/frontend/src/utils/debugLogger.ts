/**
 * Centralized debug logger for highlight application
 * Collects all events in a structured format for easy debugging
 */

interface LogEntry {
  timestamp: number;
  category: 'waitlist' | 'skip' | 'overlap' | 'apply' | 'phrase_not_found' | 'energy' | 'collision' | 'request';
  message: string;
  data?: any;
}

class DebugLogger {
  private logs: LogEntry[] = [];
  private maxLogs: number = 200;
  private enabled: boolean = true;

  log(category: LogEntry['category'], message: string, data?: any) {
    if (!this.enabled) return;

    this.logs.push({
      timestamp: Date.now(),
      category,
      message,
      data
    });

    // Keep only last N logs
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs);
    }
  }

  // @@@ Main export function - get formatted debug string
  getDebugString(): string {
    const startTime = this.logs[0]?.timestamp || Date.now();

    let output = '='.repeat(80) + '\n';
    output += 'HIGHLIGHT APPLICATION DEBUG LOG\n';
    output += `Total entries: ${this.logs.length}\n`;
    output += `Time range: ${new Date(startTime).toLocaleTimeString()} - ${new Date(this.logs[this.logs.length - 1]?.timestamp || Date.now()).toLocaleTimeString()}\n`;
    output += '='.repeat(80) + '\n\n';

    // Group by category
    const byCategory = this.logs.reduce((acc, log) => {
      if (!acc[log.category]) acc[log.category] = [];
      acc[log.category].push(log);
      return acc;
    }, {} as Record<string, LogEntry[]>);

    // Category icons
    const icons = {
      request: '📤',
      waitlist: '⏳',
      skip: '⏭️',
      overlap: '⚠️',
      apply: '✅',
      phrase_not_found: '❌',
      energy: '⚡',
      collision: '💥'
    };

    // Print by category
    for (const [category, entries] of Object.entries(byCategory)) {
      const icon = icons[category as keyof typeof icons] || '📝';
      output += `\n${icon} ${category.toUpperCase()} (${entries.length} entries)\n`;
      output += '-'.repeat(80) + '\n';

      entries.forEach((entry, idx) => {
        const relativeTime = ((entry.timestamp - startTime) / 1000).toFixed(2);
        output += `[+${relativeTime}s] ${entry.message}\n`;

        if (entry.data) {
          const dataStr = typeof entry.data === 'string'
            ? entry.data
            : JSON.stringify(entry.data, null, 2);
          output += `  Data: ${dataStr}\n`;
        }

        if (idx < entries.length - 1) output += '\n';
      });
    }

    output += '\n' + '='.repeat(80) + '\n';
    output += 'END DEBUG LOG\n';
    output += '='.repeat(80) + '\n';

    return output;
  }

  // Print to console
  dump() {
    console.log(this.getDebugString());
  }

  // Copy to clipboard (if available)
  async copyToClipboard() {
    const text = this.getDebugString();
    try {
      await navigator.clipboard.writeText(text);
      console.log('✅ Debug log copied to clipboard!');
      return true;
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      console.log('Debug log:');
      this.dump();
      return false;
    }
  }

  clear() {
    this.logs = [];
    console.log('🗑️ Debug log cleared');
  }

  enable() {
    this.enabled = true;
  }

  disable() {
    this.enabled = false;
  }

  getStats() {
    const byCategory = this.logs.reduce((acc, log) => {
      acc[log.category] = (acc[log.category] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return {
      total: this.logs.length,
      byCategory,
      enabled: this.enabled
    };
  }
}

// Global singleton
export const debugLogger = new DebugLogger();

// Expose to window for easy console access
if (typeof window !== 'undefined') {
  (window as any).debugLogger = debugLogger;
  (window as any).dumpLogs = () => debugLogger.dump();
  (window as any).copyLogs = () => debugLogger.copyToClipboard();
  (window as any).clearLogs = () => debugLogger.clear();
  (window as any).logStats = () => console.table(debugLogger.getStats());
}
