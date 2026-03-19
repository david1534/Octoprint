/**
 * Terminal store - accumulates serial communication lines from WebSocket.
 */

import { writable } from 'svelte/store';
import { wsManager } from '../websocket';

export interface TerminalLine {
	text: string;
	direction: 'send' | 'recv' | 'system';
	timestamp: number;
}

const MAX_LINES = 1000;

export const terminalLines = writable<TerminalLine[]>([]);

function appendLines(newLines: TerminalLine[]): void {
	terminalLines.update((lines) => {
		const updated = [...lines, ...newLines];
		if (updated.length > MAX_LINES) {
			return updated.slice(updated.length - MAX_LINES);
		}
		return updated;
	});
}

export function initTerminalStore(): void {
	// Handle individual terminal lines
	wsManager.on('terminal', (data: { line: string; direction: string }) => {
		appendLines([
			{
				text: data.line,
				direction: data.direction as TerminalLine['direction'],
				timestamp: Date.now()
			}
		]);
	});

	// Handle batched terminal lines from the backend (new efficient path)
	wsManager.on('terminal_batch', (data: Array<{ line: string; direction: string }>) => {
		if (!data || !data.length) return;
		const now = Date.now();
		appendLines(
			data.map((d) => ({
				text: d.line,
				direction: d.direction as TerminalLine['direction'],
				timestamp: now
			}))
		);
	});

	// Handle command results — single batched update instead of N updates
	wsManager.on('command_result', (data: any) => {
		if (data.response && data.response.length) {
			const now = Date.now();
			appendLines(
				data.response.map((line: string) => ({
					text: line,
					direction: 'recv' as const,
					timestamp: now
				}))
			);
		}
	});
}
