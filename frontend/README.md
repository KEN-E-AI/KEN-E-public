# Data Analytics Dashboard

A modern, production-ready data analytics dashboard built with React, TypeScript, and TailwindCSS. Features interactive charts, AI-powered chat assistant, and comprehensive data visualization tools.

## ✨ Features

- 📊 **Interactive Dashboard** - Real-time metrics with effectiveness and efficiency tracking
- 📈 **Data Visualization** - Interactive charts powered by Recharts
- 🤖 **AI Chat Assistant** - Multi-agent chat interface with conversation management
- 🔄 **Dynamic Filtering** - Channel and tactic-based data filtering
- 📱 **Responsive Design** - Optimized for desktop, tablet, and mobile
- 🎨 **Modern UI** - Clean interface built with Radix UI components
- 🌙 **Dark Mode Ready** - Built-in theme support
- ♿ **Accessibility** - WCAG compliant with keyboard navigation

## 🚀 Quick Start

### Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js** (version 18.0 or higher)
- **npm** (comes with Node.js)

Check your versions:

```bash
node --version
npm --version
```

### Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd fusion-starter
   ```

2. **Install dependencies**

   ```bash
   npm install
   ```

3. **Start the development server**

   ```bash
   npm run dev
   ```

4. **Open your browser**
   - Navigate to `http://localhost:5173`
   - The dashboard should load automatically

## 📋 Available Scripts

| Command              | Description                              |
| -------------------- | ---------------------------------------- |
| `npm run dev`        | Start development server with hot reload |
| `npm run build`      | Build for production                     |
| `npm run test`       | Run unit tests                           |
| `npm run typecheck`  | Check TypeScript types                   |
| `npm run format.fix` | Format code with Prettier                |

## 🛠 Tech Stack

### Core Framework

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server

### Styling & UI

- **TailwindCSS 3** - Utility-first CSS framework
- **Radix UI** - Accessible UI primitives
- **Lucide React** - Modern icon library
- **Class Variance Authority** - Component variants
- **Framer Motion** - Animations

### Data & Charts

- **Recharts** - Composable charting library
- **TanStack Query** - Data fetching and caching
- **React Hook Form** - Form management
- **Zod** - Schema validation

### Development Tools

- **Vitest** - Testing framework
- **Prettier** - Code formatting
- **PostCSS** - CSS processing
- **Autoprefixer** - CSS vendor prefixes

## 📁 Project Structure

```
├── public/                 # Static assets
├── src/
│   ├── components/
│   │   ├── ui/            # Reusable UI components
│   │   └── dashboard/     # Dashboard-specific components
│   ├── hooks/             # Custom React hooks
│   ├── lib/               # Utility functions
│   ├── pages/             # Page components
│   ├── App.tsx            # Main app component
│   ├── main.tsx           # App entry point
│   └── index.css          # Global styles
├── package.json           # Dependencies and scripts
├── tailwind.config.ts     # Tailwind configuration
├── tsconfig.json          # TypeScript configuration
└── vite.config.ts         # Vite configuration
```

## 🎯 Key Components

### Dashboard Features

- **Header Controls** - Date range, channel, and tactic selection
- **Metrics Cards** - Effectiveness and efficiency tracking with charts
- **Analysis Section** - Expandable insights with detailed charts
- **Recommendations** - Actionable suggestions with implementation options
- **Chat Sidebar** - AI assistant with multi-agent support

### UI Components

- **Interactive Charts** - Bar charts and line charts for data visualization
- **Responsive Layout** - Mobile-first design approach
- **Accessible Controls** - Keyboard navigation and screen reader support
- **Theme Support** - CSS variables for easy customization

## 🔧 Development

### Adding New Components

1. **UI Components** - Add to `src/components/ui/`
2. **Dashboard Components** - Add to `src/components/dashboard/`
3. **Pages** - Add to `src/pages/` and update routing in `src/App.tsx`

### Styling Guidelines

- Use TailwindCSS utility classes
- Leverage the `cn()` utility for conditional classes
- Follow the existing color scheme defined in `tailwind.config.ts`
- Use semantic HTML elements for accessibility

### TypeScript

- All components are fully typed
- Use proper interfaces for props
- Leverage type inference where possible
- Run `npm run typecheck` before committing

## 🚀 Production Deployment

### Build for Production

```bash
npm run build
```

This creates a `dist/` folder with optimized assets ready for deployment.

### Deployment Options

1. **Static Hosting** (Netlify, Vercel, GitHub Pages)

   ```bash
   npm run build
   # Deploy the dist/ folder
   ```

2. **Docker**

   ```dockerfile
   FROM node:18-alpine
   WORKDIR /app
   COPY package*.json ./
   RUN npm install
   COPY . .
   RUN npm run build
   EXPOSE 5173
   CMD ["npm", "run", "dev", "--", "--host"]
   ```

3. **CDN Integration**
   - The build output is optimized for CDN distribution
   - All assets are properly versioned and cacheable

## 🧪 Testing

Run the test suite:

```bash
npm run test
```

The project includes:

- Unit tests for utility functions
- Component testing setup
- TypeScript type checking

## 📝 Environment Variables

No environment variables are required for basic functionality. For production deployments, consider:

- `VITE_API_URL` - Backend API endpoint
- `VITE_ANALYTICS_ID` - Analytics tracking ID

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Troubleshooting

### Common Issues

**Port already in use:**

```bash
# Kill process on port 5173
npx kill-port 5173
npm run dev
```

**Module not found errors:**

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

**TypeScript errors:**

```bash
# Check for type issues
npm run typecheck
```

**Build failures:**

```bash
# Check for linting issues
npm run format.fix
npm run build
```

### Getting Help

- Check the [Issues](../../issues) page for known problems
- Review the component documentation in `src/components/ui/`
- Ensure all dependencies are up to date with `npm update`

---

Built with ❤️ using modern web technologies for scalable data analytics.
