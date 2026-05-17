/**
 * AppStorage — Camada de persistência com localStorage.
 *
 * COMO USAR EM NOVOS MÓDULOS:
 * 1. Crie um namespace: const store = AppStorage.getNamespace('meuModulo');
 * 2. Salve estado: store.set('chave', valor);
 * 3. Restaure estado: const valor = store.get('chave', valorPadrao);
 * 4. No init do módulo, restaure o estado salvo antes de renderizar.
 *
 * Isso garante que o estado persiste entre refreshes de página.
 */
const AppStorage = {
  /**
   * Lê um valor do localStorage, fazendo JSON.parse.
   * @param {string} key - Chave de leitura.
   * @param {*} defaultValue - Valor retornado caso a chave não exista ou ocorra erro.
   * @returns {*} Valor deserializado ou defaultValue.
   */
  get(key, defaultValue) {
    try {
      const raw = localStorage.getItem(key);
      if (raw === null) return defaultValue;
      return JSON.parse(raw);
    } catch (e) {
      console.warn(`[AppStorage] Erro ao ler chave "${key}":`, e);
      return defaultValue;
    }
  },

  /**
   * Persiste um valor no localStorage via JSON.stringify.
   * @param {string} key - Chave de escrita.
   * @param {*} value - Valor a ser serializado e salvo.
   */
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      console.warn(`[AppStorage] Erro ao salvar chave "${key}":`, e);
    }
  },

  /**
   * Remove uma chave do localStorage.
   * @param {string} key - Chave a remover.
   */
  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      console.warn(`[AppStorage] Erro ao remover chave "${key}":`, e);
    }
  },

  /**
   * Cria um objeto de acesso com prefixo de namespace.
   * Ideal para isolar o estado de módulos distintos.
   *
   * @param {string} ns - Nome do namespace (ex: 'devPanel').
   * @returns {{ get: Function, set: Function, remove: Function }}
   *
   * @example
   * const store = AppStorage.getNamespace('minhaFeature');
   * store.set('aberto', true);
   * store.get('aberto', false); // → true
   */
  getNamespace(ns) {
    return {
      get:    (k, d) => AppStorage.get(`${ns}:${k}`, d),
      set:    (k, v) => AppStorage.set(`${ns}:${k}`, v),
      remove: (k)    => AppStorage.remove(`${ns}:${k}`),
    };
  },
};

window.AppStorage = AppStorage;
