/**
 * Print history store.
 */

import { writable } from 'svelte/store';
import { api } from '../api';

export interface PrintJob {
	id: number;
	filename: string;
	started_at: string;
	completed_at: string | null;
	status: string;
	duration_seconds: number | null;
	lines_printed: number | null;
	total_lines: number | null;
	filament_used_mm: number | null;
	hotend_target: number | null;
	bed_target: number | null;
}

export interface HistoryStats {
	total_prints: number;
	completed: number;
	cancelled: number;
	failed: number;
	success_rate: number;
	total_hours: number;
	total_filament_m: number;
}

export const historyJobs = writable<PrintJob[]>([]);
export const historyTotal = writable<number>(0);
export const historyStats = writable<HistoryStats | null>(null);
export const historyLoading = writable<boolean>(false);

export async function fetchHistory(
	limit = 20,
	offset = 0,
	status?: string
): Promise<void> {
	historyLoading.set(true);
	try {
		const data = await api.getHistory(limit, offset, status);
		historyJobs.set(data.jobs || []);
		historyTotal.set(data.total || 0);
	} catch (e) {
		console.error('Failed to load history:', e);
	} finally {
		historyLoading.set(false);
	}
}

export async function fetchStats(): Promise<void> {
	try {
		const data = await api.getHistoryStats();
		historyStats.set(data);
	} catch (e) {
		console.error('Failed to load history stats:', e);
	}
}
