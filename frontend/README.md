# Storyline Frontend

Vue.js 3 frontend application for the Storyline.

## Features

- **Character Management**: Browse, select, and create new characters
- **Session Management**: Start new conversations or continue existing ones
- **Real-time Chat**: Stream responses using Server-Sent Events
- **YAML Import**: Create characters from YAML definitions
- **Settings**: Configure AI processor and preferences
- **Mobile Responsive**: Works on desktop and mobile devices

## Getting Started

### Prerequisites

- Node.js 24+ and npm
- Backend server running on port 8000

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000` with API proxy to `http://localhost:8000`.

### Build for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

## Configuration

The application uses Vite with the following configuration:

- **Development Server**: Port 3000
- **API Proxy**: All API calls are proxied to localhost:8000
- **TypeScript**: Full TypeScript support with strict mode
- **Vue 3**: Composition API with `<script setup>` syntax

## Key Technologies

- **Vue 3**: Progressive JavaScript framework
- **TypeScript**: Type-safe JavaScript
- **Vue Router**: Client-side routing
- **Vite**: Fast build tool and dev server
- **Native APIs**: Fetch API and EventSource for SSE

## API Integration

The frontend communicates with the backend through:

- REST API calls for character and session management
- Server-Sent Events for real-time chat streaming
- JSON payloads for all data exchange

## Settings

User preferences are stored in localStorage:

- `storyline_ai_processor`: Selected AI model
- `storyline_theme`: UI theme preference
- `storyline_last_character`: Last selected character

## Browser Support

- Modern browsers with ES2020+ support
- EventSource API for streaming
- Fetch API for HTTP requests
- LocalStorage for settings persistence

## Development Notes

- Uses CSS custom properties for theming
- Mobile-first responsive design
- Accessibility-friendly with proper ARIA labels
- Error boundaries and loading states
- Debounced inputs for performance