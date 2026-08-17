// picogame editor -- undo/redo. The project is plain JSON data, so history is just a
// stack of deep-cloned snapshots. push() BEFORE a mutating action captures the state to
// return to; undo()/redo() hand back a snapshot the app installs as the live project.

(function (root) {
  "use strict";

  function History(limit) {
    this.limit = limit || 60;
    this.past = [];       // snapshots older than the current live state
    this.future = [];     // snapshots undone (available to redo)
  }

  // Record the CURRENT state before it changes. Clears the redo branch.
  History.prototype.push = function (project) {
    this.past.push(clone(project));
    if (this.past.length > this.limit) this.past.shift();
    this.future.length = 0;
  };

  // Undo: caller passes the current live project; gets back the previous snapshot (or
  // null if nothing to undo). The current state is pushed onto the redo stack.
  History.prototype.undo = function (current) {
    if (!this.past.length) return null;
    this.future.push(clone(current));
    return this.past.pop();
  };

  History.prototype.redo = function (current) {
    if (!this.future.length) return null;
    this.past.push(clone(current));
    return this.future.pop();
  };

  // Drop the most recent checkpoint WITHOUT touching redo -- for a mutation that turned
  // out to be a no-op (e.g. a click that didn't become a real drag).
  History.prototype.discard = function () { this.past.pop(); };

  History.prototype.canUndo = function () { return this.past.length > 0; };
  History.prototype.canRedo = function () { return this.future.length > 0; };
  History.prototype.clear = function () { this.past.length = 0; this.future.length = 0; };

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  if (typeof module !== "undefined" && module.exports) module.exports = { History: History };
  root.PGHistory = { History: History };
})(typeof window !== "undefined" ? window : globalThis);
