# KEN-E Frontend

A modern React TypeScript application for marketing analytics and insights, built with Vite, TailwindCSS, and Radix UI.

## ✨ Features

- 📊 **Interactive Dashboard** - Real-time metrics with effectiveness and efficiency tracking
- 📈 **Data Visualization** - Interactive charts powered by Recharts
- 🤖 **AI Chat Assistant** - Multi-agent chat interface with conversation management
- 🔄 **Dynamic Filtering** - Channel and tactic-based data filtering
- 📱 **Responsive Design** - Optimized for desktop, tablet, and mobile
- 🎨 **Modern UI** - Clean interface built with Radix UI components (~50 components)
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

### Local Development Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd ken-e/frontend
   ```

2. **Install dependencies**

   ```bash
   npm install
   ```

3. **Configure environment**

   The frontend environment is now managed through the unified environment switching system at the root level:

   **Option A: Use the unified environment switcher (recommended)**

   See the [root README](../README.md#2-configure-environment) for unified switching (`./set-environment.sh` / `make env-dev`).

   **Option B: Configure frontend only**

   ```bash
   # If you need to configure just the frontend
   cp .env.development .env  # or .env.staging, .env.production
   ```

4. **Start the development server**

   After setting your environment, start the dev server:

   ```bash
   # For development environment (default)
   npm run dev:development

   # For staging environment
   npm run dev:staging

   # For production environment (use with caution!)
   npm run dev:production
   ```

5. **Open your browser**
   - Navigate to `http://localhost:8080`
   - The application will load with the selected environment configuration

### Environment Details

| Environment | API URL               | Firebase Project | Usage                      |
| ----------- | --------------------- | ---------------- | -------------------------- |
| Development | http://localhost:8000 | ken-e-dev        | Local development          |
| Staging     | http://localhost:8000 | ken-e-staging    | Testing with staging data  |
| Production  | https://api.ken-e.ai  | ken-e-production | Production data (careful!) |

### Switching Between Environments

For unified switching across all components, see the [root README](../README.md#2-configure-environment).

To switch the frontend only:

```bash
./scripts/set_environment.sh [development|staging|production]
npm run dev:[environment]
```

### Environment Files

The project uses the following environment files:

- `.env.development` - Development environment configuration
- `.env.staging` - Staging environment configuration
- `.env.production` - Production environment configuration
- `.env.local` - Active environment (created by set_environment.sh, gitignored)
- `.env.example` - Template with all required environment variables

**Note:** Never commit `.env.local` or any file containing actual credentials to version control.

## 📋 Available Scripts

| Command                    | Description                                         |
| -------------------------- | --------------------------------------------------- |
| `npm run dev`              | Start dev server on port 8080 (default development) |
| `npm run dev:development`  | Start dev server on port 8080 (development env)     |
| `npm run dev:staging`      | Start dev server on port 8080 (staging env)         |
| `npm run dev:production`   | Start dev server on port 8080 (production env)      |
| `npm run build`            | Build for production                                |
| `npm run build:staging`    | Build for staging environment                       |
| `npm run build:production` | Build for production environment                    |
| `npm run test`             | Run Vitest unit tests                               |
| `npm run typecheck`        | Check TypeScript types                              |
| `npm run format.fix`       | Format code with Prettier                           |

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

### Required Variables

Each environment file (`.env.development`, `.env.staging`, `.env.production`) should contain:

- `VITE_API_BASE_URL` - Backend API endpoint
- `VITE_FIREBASE_*` - Firebase configuration (API key, auth domain, project ID, etc.)
- `VITE_RECAPTCHA_SITE_KEY` - Google reCAPTCHA site key (can reference Secret Manager)
- `VITE_ENVIRONMENT` - Environment indicator (development|staging|production)

### Secret Manager Integration

The frontend automatically resolves Google Secret Manager references during build/dev commands. If your `.env.*` files contain Secret Manager paths like:

```
VITE_RECAPTCHA_SITE_KEY=projects/391472102753/secrets/recaptcha-site-key/versions/latest
```

These will be automatically resolved when you run:

- `npm run dev:development`, `npm run dev:staging`, or `npm run dev:production`
- `npm run build:staging` or `npm run build:production`

**Authentication**: The secret resolution uses service account files located in the parent `api/` directory:

- `api/ken-e-dev.json` for development
- `api/ken-e-staging.json` for staging
- `api/ken-e-production.json` for production

If service account files are not available, the script falls back to Application Default Credentials.

**Note**: See [scripts/README-service-accounts.md](scripts/README-service-accounts.md) for detailed setup instructions.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Troubleshooting

### Common Issues

**Environment configuration not working:**

```bash
# Make sure the script is executable
chmod +x ./scripts/set_environment.sh

# Check if environment files exist
ls -la .env.*

# Manually check current environment
cat .env.local | grep VITE_ENVIRONMENT
```

**Port already in use:**

```bash
# Kill process on port 8080
npx kill-port 8080
npm run dev:[environment]
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

**API connection issues:**

- Ensure the backend API is running on port 8000 for local development
- Check that CORS is properly configured in the API
- Verify Firebase credentials match the selected environment

### Getting Help

- Check the [Issues](https://github.com/KEN-E-AI/KEN-E/issues) page for known problems
- Review the component documentation in `src/components/ui/`
- Ensure all dependencies are up to date with `npm update`

---

Built with ❤️ using modern web technologies for scalable data analytics.
