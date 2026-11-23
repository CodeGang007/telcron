// The web app's own Vite config, for the disposable journey stack (disposable-journey.sh).
// Only the dependency cache moves: a second dev server must not rewrite the cache the shared one on
// :3200 is serving from. The port and VITE_API_URL come from the command line and the environment.
import { fileURLToPath } from 'node:url';
import base from '../frontend/vite.config';

const frontend = fileURLToPath(new URL('../frontend', import.meta.url));

export default { ...base, root: frontend, envDir: '..', cacheDir: 'node_modules/.vite-e2e' };
