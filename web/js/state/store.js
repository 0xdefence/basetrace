export const store = {
  state: {
    activePanel: 'overview',
    summary: null,
    failures: [],
    taxonomy: {},
    graph: { nodes: [], edges: [], center: '' },
    graphView: { minTx: 1, direction: 'both', scale: 1 },
  },
  listeners: [],
  set(patch) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((fn) => fn(this.state));
  },
  subscribe(fn) {
    this.listeners.push(fn);
  },
};
