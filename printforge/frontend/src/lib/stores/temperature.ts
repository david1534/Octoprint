/**
 * Temperature history store for charting.
 * Maintains a rolling buffer of temperature readings from WebSocket state updates.
 */

import { writable, get } from 'svelte/store';
import { printerState } from './printer';

export interface TempPoint {
	time: number; // timestamp in seconds
	hotendActual: number;
	hotendTarget: number;
	bedActual: number;
	bedTarget: number;
}

const MAX_POINTS = 300; // ~5 minutes at 1 reading/sec

export const tempHistory = writable<TempPoint[]>([]);

let lastUpdate = 0;

let unsubscribe: (() => void) | null = null;

export function initTempHistory(): () => void {
	// Prevent duplicate subscriptions (e.g. HMR re-init)
	if (unsubscribe) unsubscribe();

	unsubscribe = printerState.subscribe((state) => {
		const now = Date.now() / 1000;
		// Throttle to ~1 update per second
		if (now - lastUpdate < 0.9) return;
		lastUpdate = now;

		if (state.status === 'disconnected') return;

		// Create a new array instead of mutating in-place to preserve
		// reference identity for downstream subscribers
		tempHistory.update((history) => {
			const next = [...history, {
				time: now,
				hotendActual: state.hotend.actual,
				hotendTarget: state.hotend.target,
				bedActual: state.bed.actual,
				bedTarget: state.bed.target
			}];
			return next.length > MAX_POINTS ? next.slice(next.length - MAX_POINTS) : next;
		});
	});

	return unsubscribe;
}
