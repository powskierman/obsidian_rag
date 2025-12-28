# Web App Feature Integration Specification
## Obsidian RAG - Streamlit to Next.js Migration

**Version:** 1.0
**Date:** December 26, 2025
**Status:** DRAFT - Awaiting Approval

---

## Executive Summary

This document specifies the integration of all missing features from the legacy Streamlit application into the new Next.js webapp. The goal is to achieve **feature parity** between the two interfaces while maintaining the modern, polished design of the new webapp.

### Current State
- **Legacy App (Streamlit):** Fully functional with comprehensive controls for search modes, LLM providers, settings, service monitoring, and conversation management
- **New Webapp (Next.js v1.1):** Basic chat interface with minimal settings (only model selection and basic system status)

### Gap Analysis
The webapp is missing approximately **85% of the legacy app's functionality**, including:
- Search mode selection (Vector, Knowledge-Graph, Hybrid)
- LLM provider selection (Ollama, Gemini, Claude)
- Detailed service status monitoring
- Advanced settings controls (sources slider, temperature, enhanced search)
- Conversation management (proper export, chat history)
- Model selection from available models
- Enhanced search features

---

## 1. Architecture Overview

### 1.1 Left Sidebar Redesign

The ChatSidebar component will be restructured to include two main sections:

```
┌─────────────────────────────┐
│  Obsidian RAG (Diamond)     │  ← Header (existing)
├─────────────────────────────┤
│                             │
│  CONFIGURATION PANEL        │  ← New Section 1
│  ┌─────────────────────┐   │
│  │ 🔍 Search Mode      │   │
│  │ 🤖 LLM Provider     │   │
│  │ 📊 Services         │   │
│  │ ⚙️  Settings        │   │
│  │ 💾 Actions          │   │
│  └─────────────────────┘   │
│                             │
├─────────────────────────────┤
│                             │
│  CHAT HISTORY               │  ← New Section 2
│  ┌─────────────────────┐   │
│  │ Recent Chats        │   │
│  │ • Today             │   │
│  │ • Yesterday         │   │
│  │ • Last 7 Days       │   │
│  └─────────────────────┘   │
│                             │
├─────────────────────────────┤
│  User Profile (Michel)      │  ← Footer (existing)
└─────────────────────────────┘
```

### 1.2 Component Structure

```
webapp/src/components/
├── ChatSidebar.tsx (enhanced)
├── sidebar/
│   ├── SearchModeSelector.tsx (new)
│   ├── LLMProviderSelector.tsx (new)
│   ├── ServicesStatus.tsx (new)
│   ├── SettingsPanel.tsx (new)
│   ├── ActionsPanel.tsx (new)
│   └── ChatHistory.tsx (new)
├── SettingsModal.tsx (deprecated → merge into sidebar)
├── PromptModal.tsx (keep for advanced config)
└── ThinkingIndicator.tsx (existing)
```

---

## 2. Feature Specifications

### 2.1 Search Mode Selector

**Component:** `SearchModeSelector.tsx`
**Location:** Top of configuration panel
**Legacy Reference:** `streamlit_ui_docker.py` lines 88-99

#### Visual Design
```
🔍 Search Mode
Choose search method: ⓘ

○ Vector
  Fast semantic search

○ Knowledge-Graph
  Deep reasoning & connections

● Hybrid (default)
  Best of both worlds
```

#### Functionality
- **Radio button group** with 3 options
- **Default:** Hybrid
- **Tooltip on hover:** Explains each mode
- **State management:** Stored in React state and passed to API calls
- **Visual indicator:** Selected mode shown with filled radio button + blue accent

#### Implementation Details
```typescript
interface SearchMode {
  id: 'vector' | 'knowledge-graph' | 'hybrid';
  label: string;
  description: string;
  icon: string;
}

const searchModes: SearchMode[] = [
  {
    id: 'vector',
    label: 'Vector',
    description: 'Fast semantic search',
    icon: '🔍'
  },
  {
    id: 'knowledge-graph',
    label: 'Knowledge-Graph',
    description: 'Deep reasoning & connections',
    icon: '🧠'
  },
  {
    id: 'hybrid',
    label: 'Hybrid',
    description: 'Best of both worlds',
    icon: '🔗'
  }
];
```

---

### 2.2 LLM Provider Selector

**Component:** `LLMProviderSelector.tsx`
**Location:** Below search mode
**Legacy Reference:** `streamlit_ui_docker.py` lines 103-135

#### Visual Design
```
🤖 LLM Provider
Choose LLM: ⓘ

● Ollama (Free)
  Local models

○ Gemini Pro ($)
  ⚠️ API key required

○ Claude API ($)
  ⚠️ API key required
```

#### Functionality
- **Radio button group** with 3 options
- **Default:** Ollama (Free)
- **API Key Indicators:** Show warning icon if key not configured
- **Dynamic availability:** Gray out options if API keys missing
- **Help text:** Inline instructions for setting up API keys

#### API Key Management
- Check environment variables on component mount
- Display configuration status
- Link to settings modal for API key entry (future feature)

#### Implementation Details
```typescript
interface LLMProvider {
  id: 'ollama' | 'gemini' | 'claude';
  label: string;
  cost: 'free' | 'paid';
  requiresApiKey: boolean;
  apiKeyEnvVar?: string;
}

const llmProviders: LLMProvider[] = [
  {
    id: 'ollama',
    label: 'Ollama',
    cost: 'free',
    requiresApiKey: false
  },
  {
    id: 'gemini',
    label: 'Gemini Pro',
    cost: 'paid',
    requiresApiKey: true,
    apiKeyEnvVar: 'GEMINI_API_KEY'
  },
  {
    id: 'claude',
    label: 'Claude API',
    cost: 'paid',
    requiresApiKey: true,
    apiKeyEnvVar: 'ANTHROPIC_API_KEY'
  }
];
```

---

### 2.3 Services Status Panel

**Component:** `ServicesStatus.tsx`
**Location:** Below LLM provider
**Legacy Reference:** `streamlit_ui_docker.py` lines 138-192

#### Visual Design
```
📊 Services

✅ Vector DB: 7,055 chunks
   ChromaDB embeddings available

✅ Knowledge Graph: 23,326 entities
   36,036 relationships
   Graph reasoning active

✅ Ollama: 21 LLM models available
   Local inference ready
```

#### Functionality
- **Real-time status checks** on component mount
- **Refresh button** to re-check services
- **Visual indicators:**
  - ✅ Green checkmark: Service available
  - ⚠️ Yellow warning: Service degraded
  - ❌ Red X: Service unavailable
- **Detailed counts:** Show specific metrics for each service
- **Auto-refresh:** Optional 30-second interval

#### API Endpoints
```typescript
// Vector DB Stats
GET http://localhost:8001/stats
Response: { total_documents: number, collection_name: string }

// Knowledge Graph Stats
GET http://localhost:8002/health
Response: {
  status: string,
  entities: number,
  relationships: number
}

// Ollama Models
GET http://localhost:11434/api/tags
Response: { models: Array<{name: string, size: number}> }
```

#### Implementation Details
- Filter out embedding-only models from Ollama list
- Show loading skeleton while fetching
- Cache results for 30 seconds to reduce API calls
- Handle offline state gracefully

---

### 2.4 Settings Panel

**Component:** `SettingsPanel.tsx`
**Location:** Below services
**Legacy Reference:** `streamlit_ui_docker.py` lines 195-244

#### Visual Design
```
⚙️ Settings

Model
┌──────────────────────────┐
│ llama3.2:latest       ▼ │
└──────────────────────────┘

Sources
├────────────●──────────────┤
1                          50
Currently: 10

Temperature
├───────●───────────────────┤
0.0                      1.0
Currently: 0.30

☑ Show Sources
☐ Enhanced Search
```

#### Functionality

**Model Dropdown:**
- Dynamically populated from available models
- Filters by selected LLM provider
- Shows model size/type in dropdown

**Sources Slider:**
- Range: 1-50
- Default: 10
- Live preview of current value
- Tooltip: "Number of relevant documents to retrieve"

**Temperature Slider:**
- Range: 0.0-1.0
- Step: 0.01
- Default: 0.30
- Live preview with 2 decimal precision
- Tooltip: "Controls response randomness (lower = more focused)"

**Checkboxes:**
- **Show Sources:** Display retrieved documents in chat
- **Enhanced Search:** Enable LLM knowledge + web search sections

#### State Management
```typescript
interface SettingsState {
  model: string;
  sources: number;
  temperature: number;
  showSources: boolean;
  enhancedSearch: boolean;
}

const defaultSettings: SettingsState = {
  model: 'llama3.2:latest',
  sources: 10,
  temperature: 0.3,
  showSources: true,
  enhancedSearch: false
};
```

---

### 2.5 Actions Panel

**Component:** `ActionsPanel.tsx`
**Location:** Bottom of configuration panel
**Legacy Reference:** `streamlit_ui_docker.py` lines 247-275

#### Visual Design
```
┌──────────────┐  ┌──────────────┐
│ 💾 Export    │  │ 🗑️ Clear     │
└──────────────┘  └──────────────┘
```

#### Functionality

**Export Button:**
- Downloads conversation as markdown file
- Filename format: `obsidian-rag-chat-YYYY-MM-DD-HHmmss.md`
- Includes:
  - Timestamp
  - Search mode used
  - Model used
  - All messages with sources
  - Formatted for readability

**Clear Button:**
- Clears all messages from chat history
- Shows confirmation modal: "Are you sure? This cannot be undone."
- Resets to empty state with welcome message

#### Export Format Example
```markdown
# Obsidian RAG Conversation
**Date:** December 26, 2025 10:30 PM
**Search Mode:** Hybrid
**Model:** llama3.2:latest

---

## User
What is the capital of France?

## Assistant
The capital of France is Paris.

**Sources:**
1. france-geography.md (95% relevance)
2. european-capitals.md (87% relevance)

---
```

---

### 2.6 Chat History Panel

**Component:** `ChatHistory.tsx`
**Location:** Middle section of sidebar
**New Feature:** Not in legacy Streamlit (enhancement)

#### Visual Design
```
Recent Chats

📝 What is lymphoma?
   2 hours ago • Hybrid

📝 Raspberry Pi setup guide
   Yesterday • Vector

📝 3D printing materials
   3 days ago • Knowledge-Graph

────────────────────────

🔍 Search conversations...
```

#### Functionality
- **List of recent conversations** (last 20)
- **Each item shows:**
  - First message preview (truncated to 40 chars)
  - Timestamp (relative: "2 hours ago")
  - Search mode used (badge)
- **Click to load:** Restore full conversation
- **Search box:** Filter by keyword
- **Grouped by time:** Today, Yesterday, Last 7 Days, Older

#### Data Structure
```typescript
interface ChatHistoryItem {
  id: string;
  firstMessage: string;
  timestamp: Date;
  searchMode: 'vector' | 'knowledge-graph' | 'hybrid';
  messages: Message[];
}
```

#### Storage
- **LocalStorage:** Persist across sessions
- **Key:** `obsidian-rag-chat-history`
- **Max entries:** 50 conversations
- **Auto-cleanup:** Remove entries older than 30 days

---

## 3. Enhanced Chat Features

### 3.1 Sources Display

**Location:** Below each assistant message
**Legacy Reference:** `streamlit_ui_docker.py` lines 400-425

#### Visual Design
```
──────────────────────────────────────
📚 Sources (3 documents)

1. france-geography.md (95%)
   /vault/europe/france-geography.md
   France is a country in Western Europe...

2. european-capitals.md (87%)
   /vault/reference/european-capitals.md
   The capital cities of Europe include...

3. paris-history.md (82%)
   /vault/cities/paris-history.md
   Paris has been the capital since...
──────────────────────────────────────
```

#### Functionality
- **Expandable section** (collapsed by default if >3 sources)
- **Each source shows:**
  - Filename (clickable if vault path available)
  - Relevance percentage
  - Full file path
  - Snippet (first 200 characters)
- **Sort by:** Relevance (highest first)
- **Only shown when:** `showSources` setting is enabled

---

### 3.2 Enhanced Search Sections

**Location:** Below main answer
**Legacy Reference:** `streamlit_ui_docker.py` lines 550-615
**Requires:** `enhancedSearch` setting enabled

#### Visual Design
```
──────────────────────────────────────
💡 LLM Knowledge

Based on broader knowledge, here are
additional insights not in your vault:

• Clinical trials for new treatments...
• Recent research from 2024...
• Alternative perspectives...

──────────────────────────────────────
🌐 Web Search Results

Found 3 relevant articles:

1. Mayo Clinic - Lymphoma Overview
   Latest information about lymphoma types,
   symptoms, and treatment options...

2. National Cancer Institute
   Comprehensive guide to lymphoma...

3. Johns Hopkins Medicine
   Expert insights on lymphoma care...
──────────────────────────────────────
```

#### Functionality
- **LLM Knowledge Section:**
  - Generated by Claude/Gemini
  - Complementary insights
  - Clearly labeled as "not from vault"

- **Web Search Section:**
  - Powered by Tavily API
  - Top 3 results
  - Clickable titles
  - Content summaries

---

### 3.3 Rating System

**Location:** Below each assistant message
**Legacy Reference:** `streamlit_ui_docker.py` lines 430-455

#### Visual Design
```
Rate this response:

😞  😕  😐  😊  😍
1   2   3   4   5

[Already rated: ⭐⭐⭐⭐]
```

#### Functionality
- **5-point scale** with emoji buttons
- **Once rated:** Show selected rating, disable buttons
- **Submit to:** `/feedback` endpoint
- **Payload:**
```typescript
{
  query_id: string;
  rating: number; // 1-5
  query: string;
  search_mode: string;
  model: string;
  timestamp: string;
}
```

---

## 4. API Integration

### 4.1 Backend Endpoints

All endpoints remain unchanged from legacy app:

```
Embedding Service (http://localhost:8001)
├── POST /query          - Vector search
├── GET  /stats          - Database stats
└── POST /feedback       - Submit ratings

Knowledge Graph (http://localhost:8002)
├── POST /query          - Graph reasoning
└── GET  /health         - Service status

Ollama (http://localhost:11434)
├── POST /api/generate   - Text generation
└── GET  /api/tags       - Available models

Claude API (via SDK)
└── POST /v1/messages    - Text generation

Gemini API (via REST)
└── POST /v1/models/gemini-3-pro-preview:generateContent
```

### 4.2 Request/Response Formats

**Vector Search Request:**
```typescript
POST http://localhost:8001/query
{
  query: string;
  n_results: number;          // from sources slider
  reranking: boolean;         // always true
  deduplicate: boolean;       // always true
}

Response:
{
  documents: string[][];      // matched documents
  metadatas: object[][];      // file paths, etc
  distances: number[][];      // relevance scores
}
```

**Knowledge Graph Request:**
```typescript
POST http://localhost:8002/query
{
  query: string;
  max_entities: number;       // default 20
  model?: string;            // optional model override
  system_prompt?: string;    // optional custom prompt
}

Response:
{
  answer: string;            // pre-synthesized answer
  query: string;
  entities?: string[];       // extracted entities
}
```

**Hybrid Search Logic:**
```typescript
1. Query knowledge graph first
2. Extract entities from graph response
3. Enhance user query with entities
4. Perform vector search with enhanced query
5. Combine graph answer as additional context
6. Generate final response with LLM
```

---

## 5. UI/UX Specifications

### 5.1 Design System Consistency

**Colors:**
```css
--sidebar-bg: #1C1C1E
--sidebar-border: #2C2C2E
--accent-blue: #0A84FF
--text-primary: #FFFFFF
--text-secondary: rgba(255, 255, 255, 0.6)
--success-green: #34C759
--warning-yellow: #FFD60A
--error-red: #FF3B30
```

**Typography:**
```css
--font-family: system-ui, -apple-system, sans-serif
--font-size-xs: 10px
--font-size-sm: 12px
--font-size-base: 14px
--font-size-lg: 16px
```

**Spacing:**
```css
--spacing-xs: 4px
--spacing-sm: 8px
--spacing-md: 12px
--spacing-lg: 16px
--spacing-xl: 24px
```

### 5.2 Responsive Behavior

**Sidebar Width:**
- Default: 280px (current)
- Collapsible: Optional future feature
- Mobile: Full screen overlay

**Scrolling:**
- Configuration panel: Scrollable if content exceeds viewport
- Chat history: Independent scroll container
- Sticky header and footer

### 5.3 Animations

**Transitions:**
- Radio button selection: 150ms ease
- Slider updates: Real-time (no delay)
- Panel expand/collapse: 200ms ease-in-out
- Service status refresh: Fade in 300ms

**Loading States:**
- Skeleton screens for service stats
- Spinner for API calls
- Pulse animation for "thinking"

---

## 6. State Management

### 6.1 Global State (React Context)

```typescript
interface AppState {
  // Search Configuration
  searchMode: 'vector' | 'knowledge-graph' | 'hybrid';
  llmProvider: 'ollama' | 'gemini' | 'claude';

  // Settings
  settings: {
    model: string;
    sources: number;
    temperature: number;
    showSources: boolean;
    enhancedSearch: boolean;
  };

  // Service Status
  services: {
    vectorDB: {
      available: boolean;
      chunks: number;
    };
    knowledgeGraph: {
      available: boolean;
      entities: number;
      relationships: number;
    };
    ollama: {
      available: boolean;
      models: string[];
    };
  };

  // Chat
  messages: Message[];
  currentQuery: string;
  isLoading: boolean;

  // History
  chatHistory: ChatHistoryItem[];
}
```

### 6.2 Persistence

**LocalStorage:**
```typescript
// Save on change
localStorage.setItem('obsidian-rag-settings', JSON.stringify(settings));
localStorage.setItem('obsidian-rag-chat-history', JSON.stringify(chatHistory));

// Load on mount
const savedSettings = JSON.parse(localStorage.getItem('obsidian-rag-settings'));
const savedHistory = JSON.parse(localStorage.getItem('obsidian-rag-chat-history'));
```

**SessionStorage:**
- Current conversation only (cleared on tab close)
- Temporary API keys (never persisted to localStorage)

---

## 7. Testing Requirements

### 7.1 Unit Tests

**Components:**
- [ ] SearchModeSelector.tsx - All 3 modes selectable
- [ ] LLMProviderSelector.tsx - API key validation
- [ ] ServicesStatus.tsx - Mock API responses
- [ ] SettingsPanel.tsx - Slider ranges, checkbox states
- [ ] ActionsPanel.tsx - Export format, clear confirmation
- [ ] ChatHistory.tsx - Load, search, filter

### 7.2 Integration Tests

**API Calls:**
- [ ] Vector search with different source counts
- [ ] Knowledge graph queries
- [ ] Hybrid search flow
- [ ] Model listing from Ollama
- [ ] Service health checks

### 7.3 E2E Tests

**User Flows:**
- [ ] Select search mode → Send query → View results
- [ ] Change model → Verify different response
- [ ] Toggle show sources → Verify visibility
- [ ] Export conversation → Download file
- [ ] Clear conversation → Confirm reset
- [ ] Load chat history → Restore messages

---

## 8. Migration Strategy

### 8.1 Phase 1: Core Features (Week 1)
- [x] Search mode selector
- [x] LLM provider selector
- [x] Services status panel
- [x] Settings panel (model, sources, temperature)
- [x] Actions panel (export/clear)

### 8.2 Phase 2: Enhanced Features (Week 2)
- [ ] Enhanced search sections
- [ ] Web search integration
- [ ] Rating system
- [ ] Export functionality

### 8.3 Phase 3: History & Polish (Week 3)
- [ ] Chat history panel
- [ ] Search conversations
- [ ] UI polish and animations
- [ ] Performance optimization

### 8.4 Phase 4: Testing & Deployment
- [ ] Comprehensive testing
- [ ] Bug fixes
- [ ] Documentation
- [ ] Production deployment

---

## 9. Open Questions

1. **API Key Management:** Should we build a settings modal for API keys, or rely on environment variables?
2. **Web Search:** Do we want Tavily integration, or alternative search provider?
3. **Chat History Sync:** Should conversation history sync across devices? (Future feature)
4. **Model Auto-detect:** Should we auto-detect best available model on startup?
5. **Offline Mode:** How should app behave when services are unavailable?

---

## 10. Success Criteria

### Definition of Done

✅ **Feature Parity Achieved When:**
1. All search modes functional (vector, knowledge-graph, hybrid)
2. All LLM providers selectable and working (Ollama, Gemini, Claude)
3. Service status accurately reflects backend health
4. Settings controls match Streamlit functionality
5. Export produces valid markdown files
6. Chat history persists across sessions
7. Enhanced search shows LLM knowledge + web results
8. Rating system submits feedback successfully

✅ **Quality Standards:**
1. No TypeScript errors or warnings
2. 90%+ test coverage for new components
3. Lighthouse score >90 for performance
4. Responsive on mobile, tablet, desktop
5. Accessible (WCAG 2.1 AA compliant)

---

## 11. Appendix

### A. File Structure (After Implementation)

```
webapp/src/
├── app/
│   ├── layout.tsx
│   ├── page.tsx (updated with new state)
│   └── globals.css
├── components/
│   ├── ChatSidebar.tsx (major refactor)
│   ├── sidebar/
│   │   ├── SearchModeSelector.tsx
│   │   ├── LLMProviderSelector.tsx
│   │   ├── ServicesStatus.tsx
│   │   ├── SettingsPanel.tsx
│   │   ├── ActionsPanel.tsx
│   │   └── ChatHistory.tsx
│   ├── chat/
│   │   ├── MessageList.tsx
│   │   ├── MessageInput.tsx
│   │   ├── SourcesDisplay.tsx
│   │   ├── EnhancedSearchDisplay.tsx
│   │   └── RatingButtons.tsx
│   ├── PromptModal.tsx
│   └── ThinkingIndicator.tsx
├── lib/
│   ├── api.ts (expanded with new endpoints)
│   └── types.ts (new type definitions)
└── context/
    └── AppContext.tsx (new global state)
```

### B. Dependencies to Add

```json
{
  "dependencies": {
    "@anthropic-ai/sdk": "^0.30.0",
    "date-fns": "^3.0.0",
    "zustand": "^4.4.0" // optional state management
  }
}
```

---

## Approval Required

**Reviewed By:** _____________________
**Date:** _____________________
**Approved:** [ ] Yes  [ ] No  [ ] With Changes

**Comments:**

---

**Document End**
