/**
 * Clean editor engine based on trace-based energy model
 */

// @@@ Core data model - cells + commentors + tasks + WeightPath
export interface EditorState {
  cells: Cell[];
  commentors: Commentor[];
  tasks: Task[];
  weightPath: WeightEntry[];
  sessionId: string;
}

export type Cell = TextCell | WidgetCell;

export interface TextCell {
  id: string;
  type: 'text';
  content: string;  // Plain text content
}

export interface WidgetCell {
  id: string;
  type: 'widget';
  widgetType: 'chat' | 'greeting' | 'other';
  data: any;  // Widget-specific data
}

export interface Commentor {
  id: string;
  phrase: string;       // Highlighted phrase
  comment: string;      // The comment
  voice: string;        // Voice name
  icon: string;         // Icon identifier
  color: string;        // Color identifier
  appliedAt?: number;   // Timestamp when applied (if applied)
  computedAt: number;   // Timestamp when computed
  textSnapshot: string; // Text at computation time
}

export interface Task {
  id: string;
  type: 'searching' | 'thinking' | 'other';
  message: string;
  startedAt: number;
  completedAt?: number;
}

export interface WeightEntry {
  timestamp: number;
  text: string;
  weight: number;
  delta: number;  // max(0, weight - prevWeight)
  energy: number; // Accumulated energy at this point
}

// @@@ Weight function implementation
export function computeWeight(text: string): number {
  let weight = 0;

  for (const char of text) {
    // Sentence boundaries
    if (/[.!?。！？\n]/.test(char)) {
      weight += 4;
    }
    // Chinese comma (ignored)
    else if (char === '，') {
      weight += 0;
    }
    // CJK characters
    else if (/[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff]/.test(char)) {
      weight += 2;
    }
    // Default
    else {
      weight += 1;
    }
  }

  return weight;
}

// @@@ Extract completed sentences (for backend analysis)
export function getCompletedSentences(text: string): string {
  // Split by sentence boundaries
  const parts = text.split(/([.!?。！？]+)/);

  let result = '';
  for (let i = 0; i < parts.length - 1; i += 2) {
    // Include sentence + its punctuation
    if (i + 1 < parts.length) {
      result += parts[i] + parts[i + 1];
    }
  }

  // Don't include the last part if it doesn't end with punctuation
  return result.trim();
}

// @@@ Main engine class
export class EditorEngine {
  private state: EditorState;
  private usedEnergy: number = 0;
  private threshold: number = 40;
  private commentorWaitlist: Commentor[] = [];
  private sentCache: Map<string, string> = new Map(); // Track sent sentences -> commentor hash
  private onStateChange?: (state: EditorState) => void;
  private isRequesting: boolean = false; // Track if request in progress

  constructor(sessionId: string) {
    this.state = {
      cells: [{ id: generateId(), type: 'text', content: '' }],
      commentors: [],
      tasks: [],
      weightPath: [],
      sessionId
    };
  }

  // @@@ Update text and track weight changes
  updateText(newText: string) {
    // Update the first text cell (for now, single cell mode)
    const textCell = this.state.cells.find(c => c.type === 'text') as TextCell;
    if (!textCell) return;

    textCell.content = newText;

    // Compute new weight entry
    const weight = computeWeight(newText);
    const lastEntry = this.state.weightPath[this.state.weightPath.length - 1];
    const prevWeight = lastEntry?.weight || 0;
    const delta = Math.max(0, weight - prevWeight);
    const prevEnergy = lastEntry?.energy || 0;
    const energy = prevEnergy + delta;

    // Add to weight path
    this.state.weightPath.push({
      timestamp: Date.now(),
      text: newText,
      weight,
      delta,
      energy
    });

    // Check if we should request analysis
    this.checkAnalysisTrigger(newText, energy);

    // Check if we can apply commentors
    this.checkCommentorApplication(newText, energy);

    this.notifyChange();
  }

  // @@@ Check if we should send text for analysis
  private checkAnalysisTrigger(text: string, _currentEnergy: number) {
    const completedSentences = getCompletedSentences(text);

    // Skip if no completed sentences or already requesting
    if (!completedSentences || this.isRequesting) {
      return;
    }

    // Build hash of current commentor configuration
    const commentorHash = this.getCommentorHash();

    // Check if this text+commentor combination was already sent
    const cacheKey = completedSentences;
    const cachedHash = this.sentCache.get(cacheKey);

    // Only send if not in cache OR commentor config changed
    if (!cachedHash || cachedHash !== commentorHash) {
      this.sentCache.set(cacheKey, commentorHash);

      // Request analysis from backend (async, results go to waitlist)
      this.requestAnalysis(completedSentences);
    }
  }

  // @@@ Get hash of current commentor configuration
  private getCommentorHash(): string {
    // For now, just use applied commentor count as simple hash
    // Could be more sophisticated if needed
    return `v1_${this.state.commentors.filter(c => c.appliedAt).length}`;
  }

  // @@@ Check if we can apply commentors from waitlist
  private checkCommentorApplication(text: string, currentEnergy: number): boolean {
    let appliedAny = false;

    // Apply ONE commentor at a time when we have enough energy
    while (this.commentorWaitlist.length > 0) {
      const unusedEnergy = currentEnergy - this.usedEnergy;

      // Stop if we don't have enough energy for the next commentor
      if (unusedEnergy < this.threshold) {
        break;
      }

      const commentor = this.commentorWaitlist.pop()!;

      // Check if text still matches (current text starts with snapshot)
      if (text.startsWith(commentor.textSnapshot)) {
        // Apply commentor
        commentor.appliedAt = Date.now();
        this.state.commentors.push(commentor);
        this.usedEnergy += this.threshold;
        appliedAny = true;
        console.log(`✅ Applied commentor: ${commentor.voice} on "${commentor.phrase}"`);
        console.log(`   Energy: used ${this.usedEnergy}/${currentEnergy} (${currentEnergy - this.usedEnergy} remaining)`);
      } else {
        console.log(`⏭️ Skipped outdated commentor: ${commentor.voice}`);
      }
    }

    if (appliedAny) {
      this.notifyChange();
    }

    return appliedAny;
  }

  // @@@ Request analysis from backend
  private async requestAnalysis(text: string) {
    // Prevent duplicate requests
    if (this.isRequesting) {
      return;
    }

    this.isRequesting = true;

    // Add a task to show we're working
    const task: Task = {
      id: generateId(),
      type: 'thinking',
      message: 'Analyzing text...',
      startedAt: Date.now()
    };
    this.state.tasks.push(task);
    this.notifyChange();

    try {
      // Call backend (returns ONLY ONE comment at a time)
      const { analyzeText } = await import('../api/voiceApi');

      // Send only APPLIED commentors to backend
      const appliedCommentors = this.state.commentors.filter(c => c.appliedAt);
      const result = await analyzeText(text, this.state.sessionId, undefined, appliedCommentors);

      // Backend returns at most ONE voice
      if (result.voices.length > 0) {
        const voice = result.voices[0]; // Only take first one
        const commentor: Commentor = {
          id: generateId(),
          phrase: voice.phrase,
          comment: voice.comment,
          voice: voice.voice,
          icon: voice.icon,
          color: voice.color,
          computedAt: Date.now(),
          textSnapshot: text
        };
        this.commentorWaitlist.push(commentor);
        console.log(`📥 Added 1 commentor to waitlist: ${commentor.voice}`);
      } else {
        console.log(`📭 No new commentor from backend`);
      }
    } catch (error) {
      console.error('Analysis failed:', error);
    } finally {
      this.isRequesting = false;

      // Complete task
      task.completedAt = Date.now();
      this.notifyChange();

      // Remove task after a delay
      setTimeout(() => {
        const idx = this.state.tasks.indexOf(task);
        if (idx !== -1) {
          this.state.tasks.splice(idx, 1);
          this.notifyChange();
        }
      }, 2000);

      // @@@ After request completes, immediately check if we can apply and request more
      this.processPendingComments(text);
    }
  }

  // @@@ Process pending comments and trigger more requests if needed
  private processPendingComments(text: string) {
    const lastEntry = this.state.weightPath[this.state.weightPath.length - 1];
    const currentEnergy = lastEntry?.energy || 0;

    // Try to apply comments from waitlist
    const appliedAny = this.checkCommentorApplication(text, currentEnergy);

    // If we applied comments, hash changed, so check if we need another request
    if (appliedAny) {
      // Give a small delay to let the UI update
      setTimeout(() => {
        this.checkAnalysisTrigger(text, currentEnergy);
      }, 50);
    }
  }

  // @@@ Add a widget cell
  addWidgetCell(widgetType: WidgetCell['widgetType'], data: any) {
    const widget: WidgetCell = {
      id: generateId(),
      type: 'widget',
      widgetType,
      data
    };
    this.state.cells.push(widget);
    this.notifyChange();
  }

  // @@@ Subscribe to state changes
  subscribe(callback: (state: EditorState) => void) {
    this.onStateChange = callback;
  }

  private notifyChange() {
    this.onStateChange?.(this.state);
  }

  // @@@ Get current state
  getState(): EditorState {
    return this.state;
  }

  // @@@ Load state from storage
  loadState(state: EditorState) {
    this.state = state;
    // Recompute used energy from applied commentors
    this.usedEnergy = this.state.commentors.filter(c => c.appliedAt).length * this.threshold;
    this.notifyChange();
  }
}

// @@@ Helper to generate IDs
function generateId(): string {
  return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}