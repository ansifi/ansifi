export default function PaneResizer({ axis = "x", label, onPointerDown, onDoubleClick }) {
  return (
    <button
      aria-label={label}
      aria-orientation={axis === "x" ? "vertical" : "horizontal"}
      className={`pane-resizer pane-resizer-${axis}`}
      onDoubleClick={onDoubleClick}
      onPointerDown={onPointerDown}
      title={`${label} — drag to resize, double-click to reset`}
      type="button"
    >
      <span className="pane-resizer-grip" />
    </button>
  );
}
