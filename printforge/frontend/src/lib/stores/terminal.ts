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

export function initTerminalStore(): void {
	wsManager.on('terminal', (data: { line: string; direction: string }) => {
		terminalLines.update((lines) => {
			const newLine: TerminalLine = {
				text: data.line,
				direction: data.direction as TerminalLine['direction'],
				timestamp: Date.now()
			};
			const updated = [...lines, newLine];
			if (updated.length > MAX_LINES) {
				return updated.slice(updated.length - MAX_LINES);
			}
			return updated;
		});
	});

	wsManager.on('command_result', (data: any) => {
		if (data.response) {
			for (const line of data.response) {
				terminalLines.update((lines) => {
					const newLine: TerminalLine = {
						text: line,
						direction: 'recv',
						timestamp: Date.now()
					};
					const updated = [...lines, newLine];
					if (updated.length > MAX_LINES) {
						return updated.slice(updated.length - MAX_LINES);
					}
					return updated;
				});
			}
		}
	});
}
