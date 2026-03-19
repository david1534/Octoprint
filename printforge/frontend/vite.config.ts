import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/api': 'http://localhost:8000',
			'/ws': {
				target: 'ws://localhost:8000',
				ws: true
			}
		}
	},
	build: {
		// Separate Chart.js into its own cacheable chunk so it doesn't
		// bloat the main bundle on every deploy. Uses a function form
		// to avoid conflicts with SvelteKit's SSR externalization.
		rollupOptions: {
			output: {
				manualChunks(id) {
					if (id.includes('node_modules/chart.js')) {
						return 'chartjs';
					}
				}
			}
		}
	}
});
