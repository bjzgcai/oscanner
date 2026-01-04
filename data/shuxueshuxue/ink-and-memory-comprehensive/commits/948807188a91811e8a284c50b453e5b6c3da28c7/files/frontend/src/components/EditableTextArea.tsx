import { useEditor, EditorContent } from '@tiptap/react';
import { useEffect, forwardRef, useImperativeHandle } from 'react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import { VoiceHighlight, type VoiceTrigger } from '../extensions/VoiceHighlight';
import VoiceQuote from '../extensions/VoiceQuote';

interface EditableTextAreaProps {
  onChange: (text: string) => void;
  onContentChange?: (html: string) => void;
  triggers: VoiceTrigger[];
  onCursorChange?: (position: number) => void;
  onPhraseHover?: (phrase: string | null) => void;
  content?: string;
}

export interface EditableTextAreaRef {
  insertText: (text: string) => void;
  insertVoiceQuote: (voiceName: string, comment: string, voiceConfig?: any) => void;
  getTextWithoutQuotes: () => string;
  getQuotedComments: () => Array<{ voiceName: string; comment: string }>;
  getJSON: () => any;
  setJSON: (json: any) => void;
}

const EditableTextArea = forwardRef<EditableTextAreaRef, EditableTextAreaProps>(
  (props, ref) => {
    const { onChange, onContentChange, triggers, onCursorChange, onPhraseHover, content } = props;

    const editor = useEditor({
      extensions: [
        StarterKit,
        Placeholder.configure({
          placeholder: 'write here, I am listening...',
        }),
        VoiceHighlight.configure({
          triggers,
          onPhraseHover
        }),
        VoiceQuote
      ],
      content: content || '',
      onUpdate: ({ editor }) => {
        onChange(editor.getText());
        onContentChange?.(editor.getHTML());
        onCursorChange?.(editor.state.selection.from);
      },
      onSelectionUpdate: ({ editor }) => {
        onCursorChange?.(editor.state.selection.from);
      },
      autofocus: true,
    });

    // @@@ Expose editor to window for debugging
    useEffect(() => {
      if (editor) {
        (window as any).__editor = editor;
      }
    }, [editor]);

    // @@@ Dynamic trigger updates - Update highlights when triggers change
    useEffect(() => {
      if (editor && editor.isEditable) {
        // Force recalculation by creating a new transaction with meta
        const tr = editor.state.tr;
        tr.setMeta('voiceHighlight', { triggers });
        editor.view.dispatch(tr);
      }
    }, [triggers, editor]);

    // @@@ Update onPhraseHover callback when it changes
    useEffect(() => {
      if (editor) {
        editor.extensionManager.extensions.forEach((ext: any) => {
          if (ext.name === 'voiceHighlight' && ext.options) {
            ext.options.onPhraseHover = onPhraseHover;
          }
        });
      }
    }, [onPhraseHover, editor]);

    // Expose methods to parent component
    useImperativeHandle(ref, () => ({
      insertText: (text: string) => {
        if (editor) {
          // Insert text at current cursor position
          editor.chain().focus().insertContent(text).run();
        }
      },
      insertVoiceQuote: (voiceName: string, comment: string, voiceConfig?: any) => {
        if (editor) {
          // @@@ Generate unique ID for this widget (for conversation tracking)
          const widgetId = `widget_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

          // Insert atomic voice quote widget
          editor.chain().focus().insertContent({
            type: 'voiceQuote',
            attrs: {
              widgetId,
              voiceName,
              comment,
              timestamp: Date.now(),
              voiceConfig: voiceConfig || {}
            }
          }).run();
        }
      },
      getTextWithoutQuotes: () => {
        if (!editor) return '';

        // @@@ Extract text excluding voice quote nodes
        let textWithoutQuotes = '';
        editor.state.doc.descendants((node) => {
          // Skip voice quote nodes entirely
          if (node.type.name === 'voiceQuote') {
            return false;
          }
          // Collect text from other nodes
          if (node.isText) {
            textWithoutQuotes += node.text;
          }
          return true;
        });

        return textWithoutQuotes;
      },
      getQuotedComments: () => {
        if (!editor) return [];

        // @@@ Extract all quoted comments from voice quote widgets
        const quotedComments: Array<{ voiceName: string; comment: string }> = [];
        editor.state.doc.descendants((node) => {
          if (node.type.name === 'voiceQuote') {
            quotedComments.push({
              voiceName: node.attrs.voiceName,
              comment: node.attrs.comment
            });
          }
        });

        return quotedComments;
      },
      getJSON: () => {
        if (!editor) return null;
        // @@@ JSON is the proper format for persistence (not HTML)
        return editor.getJSON();
      },
      setJSON: (json: any) => {
        if (!editor) return;
        // @@@ Restore from JSON (proper way, not HTML)
        editor.commands.setContent(json);
      }
    }), [editor]);

    return <div className="editable-text-area"><EditorContent editor={editor} /></div>;
  }
);

EditableTextArea.displayName = 'EditableTextArea';

export default EditableTextArea;
