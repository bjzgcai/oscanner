import { type ReactNode, forwardRef } from 'react';

interface BookPageProps {
  children?: ReactNode;
  side: 'left' | 'right';
}

const BookPage = forwardRef<HTMLDivElement, BookPageProps>(({ children, side }, ref) => {
  return (
    <div className={`book-page ${side}-page`} ref={ref}>
      {children}
    </div>
  );
});

BookPage.displayName = 'BookPage';

export default BookPage;