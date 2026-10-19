import "./Panel.css";

// Scene-type -> "room" mapping (Art Direction section 05 / README "Art system
// -> app behaviour"). The design only names six rooms against six scene
// types (landscape/drama/movement/revelation/threshold/human figure); our
// classifier (backend/app/classifier.py) uses a different six-way split, so
// this is our own reasonable bridge between the two, not a 1:1 spec mapping:
//   landscape -> spires (exact match: LANDSCAPE)
//   drama -> window (exact match: DRAMA)
//   action -> corridor (closest match: MOVEMENT)
//   human_figures -> candle (exact match: HUMAN FIGURE)
//   text_heavy -> rose (a sign/letter being read plays as a REVELATION beat)
//   generic -> gate (THRESHOLD reads as the most neutral default room)
export const SCENE_TYPE_TO_ROOM = {
  landscape: "spires",
  drama: "window",
  action: "corridor",
  human_figures: "candle",
  text_heavy: "rose",
  generic: "gate",
};

const ROOM_LABELS = {
  spires: "The Spires",
  window: "The Belfry Window",
  corridor: "The Arches",
  rose: "The Rose Window",
  gate: "The Gate",
  candle: "The Candle",
};

function SpiresArt() {
  return (
    <>
      <div className="room-spires-sky" />
      <div className="room-spires-moon" />
      <div className="room-spires-moon-craters" />
      <div className="room-spires-skyline" />
      <div className="room-spires-glow-wrap">
        <div className="room-spires-window-main" />
        <div className="room-spires-window-l" />
        <div className="room-spires-window-r" />
      </div>
    </>
  );
}

function WindowArt() {
  return (
    <>
      <div className="room-window-bg" />
      <div className="room-window-floor-glow" />
      <div className="room-window-glass" />
      <div className="room-window-tracery" />
      <div className="room-window-rose" />
      <div className="room-window-figure" />
    </>
  );
}

function CorridorArt() {
  return (
    <>
      <div className="room-corridor-bg" />
      <div className="room-corridor-arch-1" />
      <div className="room-corridor-arch-2" />
      <div className="room-corridor-arch-3" />
      <div className="room-corridor-arch-4" />
      <div className="room-corridor-glow" />
      <div className="room-corridor-light" />
      <div className="room-corridor-figure" />
      <div className="room-corridor-floor" />
    </>
  );
}

function RoseArt() {
  return (
    <>
      <div className="room-rose-bg" />
      <div className="room-rose-window" />
      <div className="room-rose-sheen" />
    </>
  );
}

function GateArt() {
  return (
    <>
      <div className="room-gate-bg" />
      <div className="room-gate-ground-glow" />
      <div className="room-gate-bars" />
      <div className="room-gate-bars-top" />
      <div className="room-gate-rail-1" />
      <div className="room-gate-rail-2" />
      <div className="room-gate-detail" />
    </>
  );
}

function CandleArt() {
  return (
    <>
      <div className="room-candle-glow" />
      <div className="room-candle-stick" />
      <div className="room-candle-drip-l" />
      <div className="room-candle-drip-r" />
      <div className="room-candle-wick" />
      <div className="room-candle-flame" />
      <div className="room-candle-hatch" />
    </>
  );
}

const ROOM_ART = {
  spires: SpiresArt,
  window: WindowArt,
  corridor: CorridorArt,
  rose: RoseArt,
  gate: GateArt,
  candle: CandleArt,
};

/**
 * Faithful port of the design bundle's Panel component (comic-panel frame +
 * lettering overlay). When `image` is given, that real generated image
 * fills the frame and the CSS "room" art / print textures are skipped -
 * those are placeholder-only, per the design README ("keep the placeholder
 * art for empty, loading and demo states, and reuse the lettering overlay
 * for real scenes"). Lettering (caption/sfx/bubble/shot) always renders on
 * top either way.
 */
export default function Panel({
  scene = "spires",
  treatment = "ink",
  caption,
  line,
  speaker,
  sfx,
  shot,
  image,
  alt,
  ghostLabel,
}) {
  const RoomArt = ROOM_ART[scene] || ROOM_ART.spires;

  return (
    <div className="panel-frame">
      {image ? (
        <img className="panel-image" src={image} alt={alt || ""} />
      ) : (
        <>
          <div className={`panel-art-layer treatment-${treatment === "woodcut" ? "woodcut" : "none"}`}>
            <RoomArt />
            <div className="panel-texture-crosshatch" />
            <div className="panel-texture-halftone" />
            <div className="panel-texture-vignette" />
          </div>
          {treatment === "rose" && <div className="panel-rose-tone" />}
        </>
      )}
      {!image && ghostLabel && (
        <div className="panel-ghost">
          <span>{ghostLabel}</span>
          <span className="panel-ghost-room">{ROOM_LABELS[scene]}</span>
        </div>
      )}
      {caption && <div className="panel-caption">{caption}</div>}
      {sfx && (
        <div className="panel-sfx">
          {sfx}
        </div>
      )}
      {line && (
        <div className="panel-bubble">
          {speaker && <span className="panel-speaker">{speaker}</span>}
          <span className="panel-line">{line}</span>
          <div className="panel-bubble-tail" />
        </div>
      )}
      {shot && <div className="panel-shot">{shot}</div>}
    </div>
  );
}
