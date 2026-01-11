# Git Engineer Skill Evaluator - Web Application

A modern web application built with Next.js, React, and Ant Design for evaluating engineering skills based on git commit history.

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **UI Library**: Ant Design (antd) + @ant-design/x
- **Charts**: Chart.js with react-chartjs-2
- **Language**: TypeScript
- **Styling**: Tailwind CSS + Custom CSS

## Getting Started

### Prerequisites

- Node.js 18+ installed
- npm or yarn package manager
- Backend API server running (default: http://localhost:8000)

### Installation

```bash
# Install dependencies
npm install
```

### Development

```bash
# Run the development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build for Production

```bash
# Create an optimized production build
npm run build

# Start the production server
npm start
```

## Features

- **Repository Analysis**: Analyze git repository authors from local commit data
- **AI-Powered Evaluation**: Six-dimensional skill assessment using Claude 4.5
- **Caching**: Smart caching system to save API calls and improve performance
- **Interactive Dashboard**:
  - Radar chart visualization
  - Contributor cards with avatars
  - Detailed evaluation metrics
  - Commit summary statistics
- **History**: Auto-complete with repository history from localStorage

## Project Structure

```
webapp/
├── app/
│   ├── components/        # React components (future)
│   ├── page.tsx          # Main dashboard page
│   ├── layout.tsx        # Root layout with Antd setup
│   ├── globals.css       # Global styles
│   └── dashboard.css     # Dashboard-specific styles
├── public/               # Static assets
├── package.json          # Dependencies and scripts
└── README.md            # This file
```

## API Integration

The application connects to a FastAPI backend at `http://localhost:8000` with the following endpoints:

- `GET /api/local/authors/:owner/:repo` - Get authors from repository
- `POST /api/local/evaluate/:owner/:repo/:author` - Evaluate author skills

## Configuration

The API server URL can be modified in `app/page.tsx`:

```typescript
const API_SERVER_URL = 'http://localhost:8000';
```
