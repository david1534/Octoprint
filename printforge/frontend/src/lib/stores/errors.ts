/**
 * Error log store - receives real-time error events via WebSocket.
 */

import { writable, derived } from 'svelte/store';
import { wsManager } from '../websocket';
import { toast } from './toast';

export interface ErrorEntry {
	id: number;
	severity: 'info' | 'warning' | 'error' | 'critical';
	category: string;
	title: string;
	message: string;
	description: string;
	fixes: string[];
	timestamp: number;
	dismissed: boolean;
	raw: string;
}

export const errorLog = writable<ErrorEntry[]>([]);

export const activeErrors = derived(errorLog, ($log) =>
	$log.filter((e) => !e.dismissed)
);

export const activeErrorCount = derived(activeErrors, ($active) => $active.length);

export const hasCriticalError = derived(activeErrors, ($active) =>
	$active.some((e) => e.severity === 'critical')
);

/** Initialize WebSocket handlers for error events. */
export function initErrorStore(): void {
	// New error logged in real-time
	wsManager.on('error_logged', (data: ErrorEntry) => {
		errorLog.update((log) => [...log, data]);

		// Show toast for errors and critical alerts
		if (data.severity === 'critical') {
			toast.error(`${data.title}: ${data.message}`);
		} else if (data.severity === 'error') {
			toast.warning(data.title);
		}
	});

	// Full error list on connect
	wsManager.on('error_list', (data: ErrorEntry[]) => {
		errorLog.update((log) => {
			// Merge — avoid duplicates by ID
			const existingIds = new Set(log.map((e) => e.id));
			const newEntries = data.filter((e) => !existingIds.has(e.id));
			return [...log, ...newEntries];
		});
	});

	// Clear on WebSocket disconnect (reconnect will re-send active errors)
	wsManager.on('_connection', (data: { connected: boolean }) => {
		if (!data.connected) {
			errorLog.set([]);
		}
	});
}

/** Dismiss an error locally (optimistic update). */
export function dismissErrorLocal(id: number): void {
	errorLog.update((log) =>
		log.map((e) => (e.id === id ? { ...e, dismissed: true } : e))
	);
}

/** Dismiss all errors locally (optimistic update). */
export function dismissAllLocal(): void {
	errorLog.update((log) => log.map((e) => ({ ...e, dismissed: true })));
}
