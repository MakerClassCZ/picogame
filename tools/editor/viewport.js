// picogame editor -- Viewport: the ONE place world<->screen mapping lives. Every
// hit-test, paint, and draw goes through this, so authoring a map far larger than the
// device screen is native (pan/zoom around a big world; the canvas is a window onto it).
//
//   world coords  = pixels in the level (0,0 top-left, grows right/down, can be huge)
//   screen coords = CSS pixels on the <canvas> element
//
//   screen = (world - cam) * zoom
//   world  = screen / zoom + cam
//
// applyTransform() sets the canvas ctx so callers draw in WORLD coords directly.

(function (root) {
  "use strict";

  function Viewport() {
    this.camX = 0;      // world coord at the canvas's left edge
    this.camY = 0;      // world coord at the canvas's top edge
    this.zoom = 2;      // screen px per world px (pixel-art likes >=1)
    this.w = 800;       // canvas CSS width  (kept in sync by the app on resize)
    this.h = 600;       // canvas CSS height
    this.dpr = 1;       // devicePixelRatio for crisp rendering
    this.minZoom = 0.25;
    this.maxZoom = 16;
  }

  Viewport.prototype.setSize = function (w, h, dpr) {
    this.w = w; this.h = h; this.dpr = dpr || 1;
  };

  // clamp zoom into range
  Viewport.prototype._clampZoom = function (z) {
    return Math.max(this.minZoom, Math.min(this.maxZoom, z));
  };

  // screen (canvas CSS px) -> world px (floats; caller floors for tile/pixel coords)
  Viewport.prototype.screenToWorld = function (sx, sy) {
    return { x: sx / this.zoom + this.camX, y: sy / this.zoom + this.camY };
  };

  // world px -> screen (canvas CSS px)
  Viewport.prototype.worldToScreen = function (wx, wy) {
    return { x: (wx - this.camX) * this.zoom, y: (wy - this.camY) * this.zoom };
  };

  // Set the canvas transform so subsequent draws are in WORLD coordinates. Accounts for
  // devicePixelRatio (canvas backing store is w*dpr x h*dpr for crispness).
  Viewport.prototype.applyTransform = function (ctx) {
    const s = this.zoom * this.dpr;
    ctx.setTransform(s, 0, 0, s, -this.camX * s, -this.camY * s);
  };

  // reset to identity * dpr (for screen-space overlay drawing)
  Viewport.prototype.resetTransform = function (ctx) {
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  };

  // pan by a screen-pixel delta (dragging the world under the cursor)
  Viewport.prototype.panScreen = function (dsx, dsy) {
    this.camX -= dsx / this.zoom;
    this.camY -= dsy / this.zoom;
  };

  // pan by a world delta (arrow-key nudge)
  Viewport.prototype.pan = function (dwx, dwy) { this.camX += dwx; this.camY += dwy; };

  // zoom by a factor keeping the world point under (sx,sy) fixed on screen (zoom to cursor)
  Viewport.prototype.zoomAt = function (sx, sy, factor) {
    const before = this.screenToWorld(sx, sy);
    this.zoom = this._clampZoom(this.zoom * factor);
    const after = this.screenToWorld(sx, sy);
    this.camX += before.x - after.x;
    this.camY += before.y - after.y;
  };

  Viewport.prototype.setZoom = function (z, sx, sy) {
    if (sx == null) { sx = this.w / 2; sy = this.h / 2; }
    this.zoomAt(sx, sy, this._clampZoom(z) / this.zoom);
  };

  // fit the whole world (worldW x worldH) into the canvas with a margin, centered
  Viewport.prototype.fit = function (worldW, worldH, marginPx) {
    const m = marginPx == null ? 24 : marginPx;
    const availW = Math.max(1, this.w - m * 2), availH = Math.max(1, this.h - m * 2);
    this.zoom = this._clampZoom(Math.min(availW / Math.max(1, worldW), availH / Math.max(1, worldH)));
    this.camX = worldW / 2 - this.w / (2 * this.zoom);
    this.camY = worldH / 2 - this.h / (2 * this.zoom);
  };

  // center the view on a world point (used by minimap click-to-jump)
  Viewport.prototype.centerOn = function (wx, wy) {
    this.camX = wx - this.w / (2 * this.zoom);
    this.camY = wy - this.h / (2 * this.zoom);
  };

  // the world rectangle currently visible on the canvas {x,y,w,h}
  Viewport.prototype.visibleRect = function () {
    return { x: this.camX, y: this.camY, w: this.w / this.zoom, h: this.h / this.zoom };
  };

  if (typeof module !== "undefined" && module.exports) module.exports = { Viewport: Viewport };
  root.PGViewport = { Viewport: Viewport };
})(typeof window !== "undefined" ? window : globalThis);
