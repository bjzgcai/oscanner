import { useEditor, EditorContent } from '@tiptap/react';
import { useEffect, forwardRef, useImperativeHandle } from 'react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import { VoiceHighlight, type VoiceTrigger } from '../extensions/VoiceHighlight';

interface EditableTextAreaProps {
  onChange: (text: string) => void;
  onContentChange?: (html: string) => void;
  triggers: VoiceTrigger[];
  onCursorChange?: (position: number) => void;
  content?: string;
}

export interface EditableTextAreaRef {
  insertText: (text: string) => void;
}

const EditableTextArea = forwardRef<EditableTextAreaRef, EditableTextAreaProps>(
  (props, ref) => {
    const { onChange, onContentChange, triggers, onCursorChange, content } = props;

    const editor = useEditor({
      extensions: [
        StarterKit,
        Placeholder.configure({
          placeholder: 'write here, I am listening...',
        }),
        VoiceHighlight.configure({ triggers })
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

    // @@@ Dynamic trigger updates - Update highlights when triggers change
    useEffect(() => {
      if (editor && editor.isEditable) {
        // Force recalculation by creating a new transaction with meta
        const tr = editor.state.tr;
        tr.setMeta('voiceHighlight', { triggers });
        editor.view.dispatch(tr);
      }
    }, [triggers, editor]);

    // Expose insertText method to parent component
    useImperativeHandle(ref, () => ({
      insertText: (text: string) => {
        if (editor) {
          // Insert text at current cursor position
          editor.chain().focus().insertContent(text).run();
        }
      }
    }), [editor]);

    return <div className="editable-text-area"><EditorContent editor={editor} /></div>;
  }
);

EditableTextArea.displayName = 'EditableTextArea';

export default EditableTextArea;
