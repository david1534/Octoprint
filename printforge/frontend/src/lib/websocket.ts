/**
 * WebSocket connection manager with auto-reconnect.
 * Handles connecting to the PrintForge backend and dispatching messages
 * to the appropriate stores.
 */

type MessageHandler = (msg: any) => void;

class WebSocketManager {
	private ws: WebSocket | null = null;
	private url: string = '';
	private handlers: Map<string, MessageHandler[]> = new Map();
	private reconnectAttempt = 0;
	private maxReconnectDelay = 30000;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	private _connected = false;

	get connected(): boolean {
		return this._connected;
	}

	connect(url?: string): void {
		if (url) this.url = url;
		if (!this.url) {
			// Auto-detect URL based on current location
			const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
			this.url = `${protocol}//${window.location.host}/ws`;
		}

		this.cleanup();

		try {
			// Append API key as query param if configured
			let wsUrl = this.url;
			const apiKey = typeof localStorage !== 'undefined' ? localStorage.getItem('printforge:apiKey') : null;
			if (apiKey) {
				const sep = wsUrl.includes('?') ? '&' : '?';
				wsUrl = `${wsUrl}${sep}apikey=${encodeURIComponent(apiKey)}`;
			}
			this.ws = new WebSocket(wsUrl);

			this.ws.onopen = () => {
				this._connected = true;
				this.reconnectAttempt = 0;
				this.dispatch('_connection', { connected: true });
			};

			this.ws.onclose = () => {
				this._connected = false;
				this.dispatch('_connection', { connected: false });
				this.scheduleReconnect();
			};

			this.ws.onerror = () => {
				// onclose will fire after this
			};

			this.ws.onmessage = (event) => {
				try {
					const msg = JSON.parse(event.data);
					if (msg.type) {
						this.dispatch(msg.type, msg.data);
					}
				} catch {
					// Ignore malformed messages
				}
			};
		} catch {
			this.scheduleReconnect();
		}
	}

	disconnect(): void {
		this.cleanup();
		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}
	}

	private cleanup(): void {
		if (this.ws) {
			this.ws.onopen = null;
			this.ws.onclose = null;
			this.ws.onerror = null;
			this.ws.onmessage = null;
			if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
				this.ws.close();
			}
			this.ws = null;
		}
		this._connected = false;
	}

	private scheduleReconnect(): void {
		const delay = Math.min(
			1000 * Math.pow(2, this.reconnectAttempt),
			this.maxReconnectDelay
		);
		this.reconnectAttempt++;
		this.reconnectTimer = setTimeout(() => this.connect(), delay);
	}

	on(type: string, handler: MessageHandler): () => void {
		if (!this.handlers.has(type)) {
			this.handlers.set(type, []);
		}
		this.handlers.get(type)!.push(handler);

		// Return unsubscribe function
		return () => {
			const list = this.handlers.get(type);
			if (list) {
				const idx = list.indexOf(handler);
				if (idx >= 0) list.splice(idx, 1);
			}
		};
	}

	private dispatch(type: string, data: any): void {
		const list = this.handlers.get(type);
		if (list) {
			for (const handler of list) {
				try {
					handler(data);
				} catch (e) {
					console.error(`WebSocket handler error for '${type}':`, e);
				}
			}
		}
	}

	sendCommand(gcode: string): void {
		this.send({ type: 'command', data: { gcode } });
	}

	send(msg: object): void {
		if (this.ws && this.ws.readyState === WebSocket.OPEN) {
			this.ws.send(JSON.stringify(msg));
		}
	}
}

export const wsManager = new WebSocketManager();
