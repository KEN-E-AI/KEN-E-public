import { initializeApp, type FirebaseApp } from "firebase/app";
import {
  getAuth,
  connectAuthEmulator,
  GoogleAuthProvider,
  type Auth,
  type User as FirebaseUser,
} from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

// Test-only bypass: when VITE_AUTH_BYPASS=true, skip Firebase init entirely
// and inject a synthetic user so protected routes render. Used by the
// autonomous test team's VM image when no real Firebase credentials are
// available. Must never be set in any deployed environment.
// VITE_AUTH_BYPASS may never be true in a production build — guard here so an
// accidental mis-set of the variable in .env.production is a no-op.
export const authBypassEnabled =
  import.meta.env.VITE_AUTH_BYPASS === "true" &&
  import.meta.env.VITE_ENVIRONMENT !== "production";

// VITE_AUTH_BYPASS_ROLE=regular injects a non-super-admin user (non @ken-e.ai
// email) so the org-selection flow can be exercised. Defaults to super-admin.
const authBypassRole = import.meta.env.VITE_AUTH_BYPASS_ROLE;

const STUB_USER = {
  uid: "test-bypass-uid",
  email:
    authBypassRole === "regular"
      ? "test-bypass@external-test.com"
      : "test-bypass@ken-e.ai",
  emailVerified: true,
  displayName: "Test Bypass User",
  isAnonymous: false,
  providerData: [],
  getIdToken: async () => "test-bypass-token",
  getIdTokenResult: async () => ({ token: "test-bypass-token" }),
} as unknown as FirebaseUser;

const buildStubAuth = (currentUser: FirebaseUser | null): Auth =>
  ({
    currentUser,
    signOut: async () => {},
  }) as unknown as Auth;

let auth: Auth;
let app: FirebaseApp | null = null;
// True only when Firebase actually initialized successfully. Consumers that
// pass `auth` to top-level Firebase functions (onAuthStateChanged,
// signInWithPopup, etc.) must guard on this — those functions will throw if
// handed a stub.
let authInitialized = false;

if (authBypassEnabled) {
  console.warn(
    "[firebase] VITE_AUTH_BYPASS=true — Firebase init skipped, using stub auth with a synthetic test user. Never enable in deployed environments.",
  );
  auth = buildStubAuth(STUB_USER);
} else {
  try {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
    if (import.meta.env.VITE_USE_AUTH_EMULATOR === "true") {
      connectAuthEmulator(auth, "http://127.0.0.1:9099", {
        disableWarnings: true,
      });
    }
    authInitialized = true;
  } catch (err) {
    // Fail soft: let the app mount so non-auth pages render. Real auth flows
    // will fail at use time. Set VITE_FIREBASE_* for real auth, or
    // VITE_AUTH_BYPASS=true for tests.
    console.error(
      "[firebase] Initialization failed — using stub auth. The app will mount but sign-in will not work. Set VITE_FIREBASE_* env vars for real auth, or VITE_AUTH_BYPASS=true for tests. Original error:",
      err,
    );
    auth = buildStubAuth(null);
  }
}

const googleProvider = new GoogleAuthProvider();
googleProvider.addScope("profile");
googleProvider.addScope("email");

export { auth, googleProvider, authInitialized };
