/**
 * Printer state store - receives real-time updates via WebSocket.
 */

import { writable, derived, get } from 'svelte/store';
import { wsManager } from '../websocket';
import { toast } from './toast';

export interface PrinterState {
	status: string;
	port: string;
	baudrate: number;
	hotend: { actual: number; target: number };
	bed: { actual: number; target: number };
	position: { x: number; y: number; z: number };
	print: {
		file: string | null;
		progress: number;
		elapsed: number;
		remaining: number;
		currentLayer: number;
		totalLayers: number;
		currentLine: number;
		totalLines: number;
	};
	fan_speed: number;
	firmware: string;
	error: string | null;
	timelapse: {
		recording: boolean;
		frameCount: number;
		assembling: boolean;
	};
	bed_mesh: {
		grid: number[][];
		rows: number;
		cols: number;
		min: number;
		max: number;
		mean: number;
		range: number;
		active: boolean;
		timestamp: number;
	} | null;
}

const defaultState: PrinterState = {
	status: 'disconnected',
	port: '',
	baudrate: 115200,
	hotend: { actual: 0, target: 0 },
	bed: { actual: 0, target: 0 },
	position: { x: 0, y: 0, z: 0 },
	print: {
		file: null,
		progress: 0,
		elapsed: 0,
		remaining: 0,
		currentLayer: 0,
		totalLayers: 0,
		currentLine: 0,
		totalLines: 0
	},
	fan_speed: 0,
	firmware: '',
	error: null,
	timelapse: {
		recording: false,
		frameCount: 0,
		assembling: false,
	},
	bed_mesh: null
};

export const printerState = writable<PrinterState>({ ...defaultState });
export const wsConnected = writable<boolean>(false);

// Derived stores for convenience
export const isConnected = derived(printerState, ($s) => $s.status !== 'disconnected');
export const isPrinting = derived(printerState, ($s) => $s.status === 'printing');
export const isPaused = derived(printerState, ($s) => $s.status === 'paused');
export const isFinishing = derived(printerState, ($s) => $s.status === 'finishing');
export const hasError = derived(printerState, ($s) => $s.status === 'error');
export const statusBadge = derived(printerState, ($s) => {
	const map: Record<string, string> = {
		disconnected: 'badge-disconnected',
		connecting: 'badge-idle',
		idle: 'badge-idle',
		printing: 'badge-printing',
		paused: 'badge-paused',
		error: 'badge-error',
		finishing: 'badge-printing'
	};
	return map[$s.status] || 'badge-disconnected';
});

// Print completion detection
let previousStatus = 'disconnected';

// Reuse a single AudioContext to avoid hitting browser instance limits
let _audioCtx: AudioContext | null = null;

function playCompletionBeep() {
	try {
		if (!_audioCtx) _audioCtx = new AudioContext();
		const ctx = _audioCtx;
		const osc = ctx.createOscillator();
		const gain = ctx.createGain();
		osc.connect(gain);
		gain.connect(ctx.destination);
		osc.frequency.value = 880;
		gain.gain.value = 0.3;
		osc.start();
		gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
		osc.stop(ctx.currentTime + 0.5);
	} catch {
		// Audio not available
	}
}

function notifyPrintComplete(filename: string | null) {
	toast.success(`Print complete: ${filename || 'Unknown file'}`);
	playCompletionBeep();

	const enabled = localStorage.getItem('printforge:notifications') === 'true';
	if (enabled && typeof Notification !== 'undefined' && Notification.permission === 'granted') {
		new Notification('PrintForge', {
			body: `Print complete: ${filename || 'Unknown file'}`,
			icon: '/favicon.png'
		});
	}
}

// Initialize WebSocket handlers
export function initPrinterStore(): void {
	wsManager.on('state', (data: PrinterState) => {
		// Detect print completion: was printing/finishing, now idle
		const wasPrinting = previousStatus === 'printing' || previousStatus === 'finishing';
		const nowIdle = data.status === 'idle';
		if (wasPrinting && nowIdle) {
			// Read current filename before overwriting with new state
			const filename = get(printerState).print.file;
			notifyPrintComplete(filename);
		}
		previousStatus = data.status;
		printerState.set(data);
	});

	wsManager.on('_connection', (data: { connected: boolean }) => {
		wsConnected.set(data.connected);
		if (!data.connected) {
			// Reset to default state on disconnect to avoid showing stale
			// temperatures/progress that could mislead the user into thinking
			// the printer is in a safe state when it may not be
			printerState.set({ ...defaultState });
		}
	});
}
