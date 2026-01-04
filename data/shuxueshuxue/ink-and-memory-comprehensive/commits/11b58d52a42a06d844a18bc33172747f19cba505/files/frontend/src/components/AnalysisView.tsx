import { useState } from 'react';

export default function AnalysisView() {
  const [currentPage, setCurrentPage] = useState(0);

  const pages = [
    { id: 0, name: 'Adventure' },
    { id: 1, name: 'Patterns' },
    { id: 2, name: 'Traits' },
    { id: 3, name: 'Echoes' },
    { id: 4, name: 'Ask Away' }
  ];

  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
      paddingTop: '2rem'
    }}>
      {/* Left sidebar - Page tabs */}
      <div style={{
        width: 200,
        background: '#fffef9',
        alignSelf: 'flex-start',
        borderTop: '1px solid #d0c4b0',
        borderBottom: '1px solid #d0c4b0'
      }}>
        {pages.map(page => (
          <div
            key={page.id}
            onClick={() => setCurrentPage(page.id)}
            style={{
              padding: '1rem 1.5rem',
              cursor: 'pointer',
              background: currentPage === page.id ? '#f5e6d3' : 'transparent',
              borderLeft: currentPage === page.id ? '4px solid #8b7355' : '4px solid transparent',
              fontWeight: currentPage === page.id ? 600 : 400,
              color: currentPage === page.id ? '#333' : '#666',
              transition: 'all 0.2s'
            }}
            onMouseEnter={e => {
              if (currentPage !== page.id) {
                e.currentTarget.style.background = '#f9f5ed';
              }
            }}
            onMouseLeave={e => {
              if (currentPage !== page.id) {
                e.currentTarget.style.background = 'transparent';
              }
            }}
          >
            {page.name}
          </div>
        ))}
      </div>

      {/* Right content area */}
      <div style={{
        flex: 1,
        padding: '2rem',
        overflowY: 'auto',
        background: '#f5e6d3'
      }}>
        {currentPage === 0 && <Page0StickyNotes />}
        {currentPage === 1 && <PlaceholderPage title="行为模式分析" />}
        {currentPage === 2 && <PlaceholderPage title="性格特征分析" />}
        {currentPage === 3 && <PlaceholderPage title="重复出现的话题" />}
        {currentPage === 4 && <Page4ChatQA />}
      </div>
    </div>
  );
}

// Page 0: Sticky notes with actionable nudges
function Page0StickyNotes() {
  const notes = [
    { text: '下次点咖啡，试试菜单上从没点过的那一个。', color: '#FFF9BE', rotation: -2 },
    { text: '给一个很久没联系的人发条消息，就说"想起你了"。', color: '#D4EAF1', rotation: 1 },
    { text: '今天走不同的路回家，哪怕只是换一条街。', color: '#F1D4D4', rotation: -1 },
    { text: '在电梯里和陌生人说句话，比如"今天天气不错"。', color: '#FFF9BE', rotation: 2 },
    { text: '把一件拖了很久的小事做掉，5 分钟就够了。', color: '#D4EAF1', rotation: -3 },
    { text: '闭上眼睛吃一口东西，专注地感受味道。', color: '#F1D4D4', rotation: 1 }
  ];

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '2rem',
      padding: '2rem'
    }}>
      {notes.map((note, index) => (
        <div
          key={index}
          style={{
            width: 200,
            height: 200,
            background: note.color,
            padding: '1.5rem',
            boxShadow: '0 4px 8px rgba(0,0,0,0.15)',
            transform: `rotate(${note.rotation}deg)`,
            transition: 'all 0.2s',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
            fontSize: '1.1rem',
            lineHeight: 1.6,
            color: '#333'
          }}
          onMouseEnter={e => {
            e.currentTarget.style.transform = `rotate(${note.rotation}deg) scale(1.05)`;
            e.currentTarget.style.boxShadow = '0 6px 12px rgba(0,0,0,0.2)';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.transform = `rotate(${note.rotation}deg)`;
            e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)';
          }}
        >
          {note.text}
        </div>
      ))}
    </div>
  );
}

// Placeholder for pages 1-3
function PlaceholderPage({ title }: { title: string }) {
  return (
    <div style={{
      padding: '4rem',
      textAlign: 'center',
      color: '#666'
    }}>
      <h2 style={{
        fontSize: '2rem',
        marginBottom: '1rem',
        color: '#333'
      }}>{title}</h2>
      <p style={{ fontSize: '1.2rem' }}>Coming soon...</p>
    </div>
  );
}

// Page 4: Chat-style Q&A interface
function Page4ChatQA() {
  const conversations = [
    { type: 'user', text: '我最近写了什么？', name: '你' },
    { type: 'ai', text: '你写了一段关于源代码贬值的想法。', name: 'AI' },
    { type: 'user', text: '我为什么会失落？', name: '你' },
    { type: 'ai', text: '你提到感觉自己不再被需要了，AI 可以做得更好。这种从"创造者"变成"搬运工"的落差，让你失落。', name: 'AI' },
    { type: 'user', text: '被需要对我来说意味着什么？', name: '你' },
    { type: 'ai', text: '从你的文字来看，被需要意味着你的思考和创造是有价值的，不只是机械地搬运代码。那种主动思考、创造的体验，对你很重要。', name: 'AI' }
  ];

  return (
    <div style={{
      maxWidth: 800,
      margin: '0 auto',
      padding: '2rem'
    }}>
      {conversations.map((conv, index) => (
        <div key={index}>
          <div style={{
            display: 'flex',
            gap: '1rem',
            padding: '1.5rem 0',
            alignItems: 'flex-start'
          }}>
            {/* Name on the left */}
            <div style={{
              fontSize: '1rem',
              fontWeight: 600,
              color: '#666',
              flexShrink: 0,
              minWidth: 40
            }}>
              {conv.name}
            </div>

            {/* Text content */}
            <div style={{
              flex: 1,
              fontSize: '1.1rem',
              lineHeight: 1.8,
              color: '#333'
            }}>
              {conv.text}
            </div>
          </div>

          {/* Subtle divider */}
          {index < conversations.length - 1 && (
            <div style={{
              height: 1,
              background: 'linear-gradient(to right, transparent, #d0c4b0 20%, #d0c4b0 80%, transparent)',
              opacity: 0.3
            }} />
          )}
        </div>
      ))}
    </div>
  );
}
