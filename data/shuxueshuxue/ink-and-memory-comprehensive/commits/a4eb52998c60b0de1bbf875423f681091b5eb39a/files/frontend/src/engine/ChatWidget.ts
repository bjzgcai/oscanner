/**
 * ChatWidget - Persistent 1-to-1 chat with a voice agent
 *
 * Each widget maintains its own conversation history.
 * The widget is inserted after the line where @ was triggered.
 */

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface ChatWidgetData {
  id: string;
  voiceName: string;
  voiceConfig: {
    name: string;
    tagline: string;
    icon: string;
    color: string;
  };
  messages: ChatMessage[];
  createdAt: number;
}

export class ChatWidget {
  private data: ChatWidgetData;

  constructor(voiceName: string, voiceConfig: any) {
    this.data = {
      id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(),
      voiceName,
      voiceConfig: {
        name: voiceConfig.name,
        tagline: voiceConfig.systemPrompt || voiceConfig.tagline,
        icon: voiceConfig.icon,
        color: voiceConfig.color
      },
      messages: [],
      createdAt: Date.now()
    };
  }

  // @@@ Load from saved state
  static fromData(data: ChatWidgetData): ChatWidget {
    const widget = Object.create(ChatWidget.prototype);
    widget.data = data;
    return widget;
  }

  // @@@ Add user message (frontend only, before sending to backend)
  addUserMessage(content: string): void {
    this.data.messages.push({
      role: 'user',
      content,
      timestamp: Date.now()
    });
  }

  // @@@ Add assistant response (after backend returns)
  addAssistantMessage(content: string): void {
    this.data.messages.push({
      role: 'assistant',
      content,
      timestamp: Date.now()
    });
  }

  // @@@ Get conversation history for backend API
  getConversationHistory(): Array<{ role: string; content: string }> {
    return this.data.messages.map(msg => ({
      role: msg.role,
      content: msg.content
    }));
  }

  // @@@ Get all data for persistence
  getData(): ChatWidgetData {
    return this.data;
  }

  getId(): string {
    return this.data.id;
  }

  getVoiceName(): string {
    return this.data.voiceName;
  }

  getVoiceConfig(): ChatWidgetData['voiceConfig'] {
    return this.data.voiceConfig;
  }

  getMessages(): ChatMessage[] {
    return this.data.messages;
  }
}
