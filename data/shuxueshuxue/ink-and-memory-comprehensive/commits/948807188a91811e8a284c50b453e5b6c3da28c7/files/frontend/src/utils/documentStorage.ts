// @@@ Document storage wrapper - manages both TipTap content and chat conversations

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

interface StoredDocument {
  document: any; // TipTap JSON
  conversations: Record<string, Message[]>; // widgetId -> messages
  lastModified: number;
}

export class DocumentStorage {
  private storageKey: string;

  constructor(storageKey: string = 'ink_and_memory_document') {
    this.storageKey = storageKey;
  }

  // @@@ Save document + conversations
  save(documentJSON: any, conversations: Record<string, Message[]>): void {
    const stored: StoredDocument = {
      document: documentJSON,
      conversations,
      lastModified: Date.now()
    };
    localStorage.setItem(this.storageKey, JSON.stringify(stored));
  }

  // @@@ Load document + conversations
  load(): StoredDocument | null {
    const stored = localStorage.getItem(this.storageKey);
    if (!stored) return null;

    try {
      return JSON.parse(stored);
    } catch (e) {
      console.error('Failed to parse stored document:', e);
      return null;
    }
  }

  // @@@ Get conversation for a specific widget
  getConversation(widgetId: string): Message[] {
    const stored = this.load();
    return stored?.conversations[widgetId] || [];
  }

  // @@@ Update conversation for a specific widget
  updateConversation(widgetId: string, messages: Message[]): void {
    let stored = this.load();

    // @@@ Initialize if not exists
    if (!stored) {
      stored = {
        document: null,
        conversations: {},
        lastModified: Date.now()
      };
    }

    stored.conversations[widgetId] = messages;
    stored.lastModified = Date.now();
    localStorage.setItem(this.storageKey, JSON.stringify(stored));
  }

  // @@@ Clear all data
  clear(): void {
    localStorage.removeItem(this.storageKey);
  }
}

export default DocumentStorage;
