/**
 * WebSocket Client com reconexão automática (exponential backoff).
 */
export class WSClient {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.handlers = {};
    this.reconnectDelay = 1000;
    this.maxDelay = 30000;
    this._pingInterval = null;
    this._reconnectTimer = null;
    this._manualClose = false;
    this._connected = false;
  }

  connect() {
    this._manualClose = false;
    this._createSocket();
  }

  _createSocket() {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING ||
                    this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[WS] Conectado ao servidor.');
        this._connected = true;
        this.reconnectDelay = 1000; // reset backoff
        this._startPing();
        this._dispatch('_connected', {});
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const type = msg.type;
          const payload = msg.payload || {};
          this._dispatch(type, payload);
        } catch (e) {
          console.warn('[WS] Mensagem inválida:', event.data);
        }
      };

      this.ws.onclose = (event) => {
        this._connected = false;
        this._stopPing();
        this._dispatch('_disconnected', { code: event.code, reason: event.reason });

        if (!this._manualClose) {
          console.log(`[WS] Desconectado (${event.code}). Reconectando em ${this.reconnectDelay}ms...`);
          this._reconnectTimer = setTimeout(() => {
            this._createSocket();
          }, this.reconnectDelay);
          this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[WS] Erro na conexão:', error);
        this._dispatch('_error', { error });
      };

    } catch (e) {
      console.error('[WS] Falha ao criar WebSocket:', e);
      this._reconnectTimer = setTimeout(() => {
        this._createSocket();
      }, this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
    }
  }

  disconnect() {
    this._manualClose = true;
    this._stopPing();
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
    }
    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect');
    }
  }

  send(type, payload = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }));
      return true;
    }
    return false;
  }

  on(type, handler) {
    if (!this.handlers[type]) {
      this.handlers[type] = [];
    }
    this.handlers[type].push(handler);
    return this; // chainable
  }

  off(type, handler) {
    if (this.handlers[type]) {
      this.handlers[type] = this.handlers[type].filter(h => h !== handler);
    }
    return this;
  }

  _dispatch(type, payload) {
    const handlers = this.handlers[type];
    if (handlers && handlers.length > 0) {
      handlers.forEach(h => {
        try {
          h(payload);
        } catch (e) {
          console.error(`[WS] Erro no handler '${type}':`, e);
        }
      });
    }
  }

  _startPing() {
    this._stopPing();
    this._pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send('ping');
      }
    }, 30000);
  }

  _stopPing() {
    if (this._pingInterval) {
      clearInterval(this._pingInterval);
      this._pingInterval = null;
    }
  }

  get isConnected() {
    return this._connected && this.ws && this.ws.readyState === WebSocket.OPEN;
  }
}
